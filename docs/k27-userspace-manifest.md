# k27 用户空间改动清单（2026-10-31）

k27 = xnu-12377 内核（patches/xnu-12377，40 个补丁，树 e4caa8c）+ macOS 27.0.1 原版 kext + 27.0.1 原版用户空间。
原则：**Apple 的用户态二进制一个字节都不改**；所有差异来自「多放进去的文件」「目录布局」「启动参数 / exec-env」「我们自己的驱动与 GPU 栈」。
内核侧改动看 patches/xnu-12377/README.md 和各补丁说明，本文不重复。

## 1. SystemOS 盘（scripts/make-macos-systemos.sh）

一个新的未封印 APFS 卷，由内核以只读 union 挂在 / 上：

| 内容 | 来源 | 为什么 |
|---|---|---|
| Cryptex1,SystemOS（dyld 共享缓存等） | IPSW 原样 | 也挂成 /System/Volumes/Preboot/Cryptexes/OS（→ /） |
| Cryptex1,AppOS（Safari） | IPSW 原样 | trust bundle 第 4 模块；Data 侧要相对链接（restage） |
| Data 模板里只读的 firmlink 目标（assets、CoreTypes、Speech、cups、snmp） | OS 镜像 /System/Library/Templates/Data | 不进 Data 卷 |
| 大块只读 /Library | 放 /System/Library/DroidVMData/Library | Data 种子链接过去，省 Data 空间 |
| 可写 firmlink 的空源目录（/private /Library /Users /Applications /Volumes /cores /opt /usr/local /System/Library/Caches /System/Volumes/Hardware）、/System/Volumes/Data 挂载点 | 新建 | k27 内核挂 Data 并建 firmlink（kern_exec.c native_owner_firmlinks_prepare） |
| cryptexd 状态目录 /System/Volumes/Preboot/com.apple.security.cryptexd/Cryptexes | 新建 | cryptexd 在只读根上 O_NOFOLLOW 打开 |
| **overlay/systemos-shims**：/sbin/fsck、/sbin/mount 两个 shell shim；原 mount 留为 /sbin/mount.real | 本仓库 | launchd 的 fsck / mount-phase 启动任务对只读容器不成立 |
| /private/{var,etc,tmp} 空目录 | 新建 | union 下 /var /etc /tmp 符号链接的落点 |

## 2. Data 种子（scripts/make-macos-data-seed.sh + DroidVMDataStore 覆盖层）

- 大小写不敏感，内容取自安装器模板 /System/Library/Templates/Data，按 macOS 真实布局（private/{var,etc,tmp}、Library、Users… 在卷根）。
- 运行期写入走 DroidVMDataStore 覆盖层（手机上的 data store）；scripts/fold-overlay.py 可把覆盖层折回 DBRDISK1 种子。
- **stage-gpu-plugin.py**（每次启动前生成种子副本，build-metal-plugin.sh / try.sh 链路调用）额外写入：

| 写入 | 选项 | 为什么 |
|---|---|---|
| /Library/GPUBundles/NativeAdrenoMetal.bundle | 必选 | IOGPU 查找 Metal 插件的第一个目录 |
| /var/db/.AppleSetupDone + 受管 SkipSetupItems + DroidVMInput 键盘类型 | --setup-done | 跳过语言选择（等 bluetoothd 卡死）、Setup Assistant、键盘助理 |
| /var/db/dslocal 本地管理员 uid 501 + 首登前建 home + .skipbuddy | --user | 不经 Setup Assistant 建用户；无 MiniBuddy 才会起 Dock/Finder |
| launchd disabled.plist（audiomxd、apsd…） | --disable-job / --disable-agent | 只在本板上空转/崩溃循环的守护进程 |
| 诊断 launchd 任务：metal-probe、log stream、top/zprint、定时命令 | --probe / --log-stream / --top / --run | 仅诊断，stderr-log=1 时进内核日志 |
| /Library/Preferences/Logging/Subsystems/*.plist | --log-debug | 仅诊断 |
| 任意文件 | --file SRC:DEST | 如 m2vsim 回放 trace |

## 3. 信任缓存（scripts/make-trust-bundle.py、make-owner-trust-bundle.py）

DarwinBoot 的 kernel.macho.trustcache 旁路文件：IPSW 原版 StaticTrustCache + Cryptex1,SystemTrustCache + AppTrustCache（Safari），
再加一个 owner 模块（我们自己的 Mach-O：Metal 插件、metal-probe 等的 CDHash）。非 trust cache 的第三方二进制仍因 AMFI↔amfid 不匹配失败（见记忆 macos-amfi-amfid-mig-abi-mismatch）。

## 4. GPU 用户态栈（全是我们自己的代码，装在 /Library/GPUBundles）

| 层 | 源 | 本仓库的改动 |
|---|---|---|
| Metal 插件 NativeAdrenoMetal.bundle | overlay/metal/NativeAdrenoMetalPlugin.mm + UniXNU NativeMetal frontend/bridge | NativeMetal 补丁在 UniXNU 子模块（bridge/patches/0021 等） |
| metal2vulkan | NativeMetal 固定的版本 | 板级补丁见 sources/UniXNU（patches/metal2vulkan-port 不参与构建） |
| Turnip（libvulkan_freedreno） | UniXNU 固定的 mesa + UniXNU 记录补丁 | **patches/mesa-macos/0001–0003**（构建时 apply、构建后撤回） |
| 内核 ABI 头 / DroidVMGpu kext | NativeAdreno 805c7e4 + UniXNU-droidvm bf7fc44 | patches/droidvm-gpu（本地分支 droidvm-macos 导出） |
| 链接用 IOGPU.tbd | overlay/metal/frameworks/IOGPU.framework | 仅链接期 |

## 5. 启动参数与 exec-env（scripts/droidvm-app.py）

- REQUIRED_ARGS：mac-amfi-launch-permissive=1、union-hide-lower=1、malloc-ranges-off=1、arm64_maxoffset=0x7FFE000000、ml-timeout-lock-scale=40
  （mac-sandbox-* 已于 bf9c9f4 去掉，k27 内核不再读）。
- GPU_ARGS：droidvm-gpu=1、droidvm-gpu-selftest=1、ca-triple-buffer=1、ca-free-wakeup=1。
- exec-env（内核在 exec 时给指定进程加环境变量，不改二进制）：
  - com.apple.WebKit.WebContent: GIGACAGE_ENABLED=no（39 位用户空间放不下 64 GiB Gigacage）
  - WindowServer: MallocZeroOnFree=0（GPU 模式；拖动帧率）
- SIP：MACOS_LP_SIP0=0x2（CSR_ALLOW_UNRESTRICTED_FS，launchd 才能映射共享缓存）；rootauth=0；boot-manifest-hash（27 的 Image4 要）。
- MACOS_DROP_ARGS=名字[,名字]：临时去掉上面任一参数。

## 6. 内核里「代替用户空间做的事」（便于对照，细节在补丁）

firmlink 与 Data 挂载、union 隐藏下层、deny-exec（mobileactivationd 等）、exec-env、k27_amfi_page_shift（AMFI GOT 改绑，kext 字节不改）。

## 7. 明确不改的

Apple 的所有用户态 Mach-O、dyld 共享缓存、launchd plist（只通过 overrides 禁用）、沙盒配置（27 Sandbox kext 原生吃 27 配置）。
