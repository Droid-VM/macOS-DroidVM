# macOS-DroidVM 仓库结构（2026-11-16）

本仓库（`~/crosvm/macos`，远端 `Droid-VM/macOS-DroidVM`，分支 `main`）在手机上的 DroidVM（crosvm + Gunyah）里跑 macOS 27.2（26B8125，触屏 MacBook Pro 的版本）：
源码编译的 xnu-12377 内核 + 27 的内核缓存 kext、自己的板级 kext、Metal 插件（Turnip/metal2vulkan），以及配套的构建、部署、诊断脚本。

## 从 IPSW 到手机上的启动盘

产品的全部开关、内核参数和步骤在 `configs/product-k27.json`，入口是 `scripts/product.py`（每步调用已有脚本，环境变量由配置给出）。

| 阶段 | 多久做一次 | 命令 | 产物 |
|---|---|---|---|
| 1. IPSW 输入 | 换 macOS 版本 | `product.py inputs`（配置的 `inputs`：只按 HTTP 范围下载用到的成员并按苹果清单校验，解密 AEA，打信任缓存包，解出内核缓存；已有的跳过；需要 `ipsw` 工具，可用 `$IPSW` 指定） | `artifacts/27.2/`（`os.raw`、`dec/`、`app-cryptex/`、`kernelcache.release.vma2`、`boot/kernel.macho.trustcache`）、`out/kc/kc27.bin` |
| 2. 源码树 | 换固定提交 | `prepare-sources.py`（`configs/sources.lock.json`） | `sources/` |
| 3. 系统盘 | 新装一台 VM | `product.py disk DIR`（要 sudo），再 `droidvm-app.py install DIR`、`droidvm-app.py prepare` | 手机上的 Data 存储（单 APFS 容器：System/Data/Preboot/VM/Update/Hardware/xART）、`artifacts/27.2/disk/disk.json` |
| 4. 内核 | 改内核补丁 | `product.py kernel` | `out/k27/kernel-k27.macho` |
| 5. 板级 kext | 改 kext 源 | `product.py kexts`（配置里的 `kexts` 列表） | `out/x12377/native-kexts/` |
| 6. 内核缓存 | 4、5 或 `kc-keep.txt` 变了 | `product.py kc` | `out/k27/kc-k27.bin`（逐字节可复现） |
| 7. Metal 插件 | 改 GPU 用户态 | `product.py gpu [--deps]`（`--deps` 先编 Turnip 和 bridge） | `out/metal/plugin/NativeAdrenoMetal.bundle` |
| 8. 启动盘 | 6、7 或内核参数变了 | `product.py boot` | `out/product/k27/boot.img`、`manifest.json` |
| 9. 部署 | 每次 | `product.py install-plugin 用户@guest`（7 变了才需要）、`product.py deploy`，然后重启 VM | 手机 `boot.img`（上一份留作 `boot.img.prev`） |

日常只用 `product.py build`（6+7+8）加第 9 步；`product.py full` 是 4–8。`product.py status` 看手机上的启动盘是不是清单里那份，
`product.py verify [镜像]` 逐个载荷对比两份启动盘，`product.py env` 输出配置的环境变量（手动跑单个脚本前 `eval`）。

实测（2026-11-16，20 核开发机、家用宽带）：从空目录跑 `inputs` 约 5 分钟（OS 成员 10 GB 下载 205 s 占大头，网速波动时可到 500 s），
`disk` 1 分钟，`full` 8 分钟（bridge 7–8 分钟与内核 51 s、kext 77 s、KC 6 s、Turnip 62 s 并行，之后插件 11 s、启动盘数秒），合计约 14 分钟。
bridge 的时间几乎都在单线程的 fat LTO（codegen-units=1）上，这是有意的优化设置；`-Zthreads` 只快 16 s，关调试信息会改变生成的代码。
除内核（版本串带编译时间）外各产物逐字节可复现；Turnip 靠 `PYTHONHASHSEED=0`（Mesa 生成器遍历集合）。

输入来自两个 IPSW：系统、cryptex 和信任缓存来自触屏 MacBook Pro 的 27.2（`configs/macos-27.2-26B8125.json`），
内核缓存和设备树来自通用 27.2（`configs/macos-27.2-26B123.json`，触屏版没有 vma2 虚拟机的内核缓存）。

规则：
- **启动盘和信任缓存每次从头生成**，不在旧镜像上打补丁。信任缓存 = 苹果原件 + 一个模块（插件包里各 Mach-O 构建出来时的 CDHash，
  链接器签名，不在 guest 里重签）。guest 里的插件必须就是构建出的那个包，所以换插件要先 `install-plugin` 再 `deploy`。
- 新开关、新内核参数写进 `configs/product-k27.json`，不要只在命令行上带；实验用的环境变量仍然可以临时覆盖。
- 上机调试（`k27/try.sh` 不带 `K27_NO_BOOT`、`xnu12377-smoke.sh`）是另一条路，不产出产品镜像。

约定：
- **入库**：脚本、补丁、kext/插件源码、配置。
- **只在本地**：文档（`docs/`、`TODO.md`、`k27/TODO.md`、本文件）、`sources/`、`out/`、`artifacts/`、`toolchains/`、`research/`、`tools/`（见 `.gitignore`）。
- 改动上游代码一律以补丁形式放 `patches/`，构建时打上；上游树（`sources/`）只固定提交，不直接改。

## 顶层

| 路径 | 入库 | 内容 |
|---|---|---|
| `README.md` | 是 | 早期 CI 说明（`device/`、`local/` 已不存在，内容过时） |
| `TODO.md` | 否 | 10 月的总体规划与阶段验收（23G93/14.6.1 时期） |
| `.github/workflows/` | 是 | `kernel.yml`（macOS runner 上 `unixnu build kernel`）、`mainline.yml` |
| `k27/` | 是 | **当前主线**：macOS 27 内核缓存的构建、上机、调试脚本（见下） |
| `scripts/` | 是 | 通用脚本：KC 链接、Metal/Turnip 构建、Data 盘、App 部署、guest 内存读取（见下） |
| `patches/` | 是 | 对各上游的补丁（见下） |
| `overlay/` | 是 | 自己写的源码：板级 kext、Metal 插件与探针、旧 DroidVM 板驱动 |
| `configs/` | 是 | 构建配置与固定版本；`product-k27.json` 是产品配置 |
| `compat/` | 是 | 在 Linux 上跑 UniXNU/xnu 构建的兼容层 |
| `tests/` | 是 | `test_range_layout.py` |
| `docs/` | 否 | 方案与进展文档（见下） |
| `sources/` | 否 | 上游源码树（见下） |
| `artifacts/` | 否 | 从 IPSW 取出的苹果原始件（`27.2/` 是当前的）、新装盘（`27.2/disk/`）与启动输入（`boot-inputs/`） |
| `toolchains/` | 否 | Linux 上的苹果工具链：`linux/`（Darling 镜像、appleclang、cctools、apple-iig）、`sdks/`（MacOSX26.1.sdk、iOS SDK） |
| `out/` | 否 | 全部构建产物与临时文件（见下） |
| `research/` | 否 | 诊断代码、探针、测试框架（见下） |
| `tools/m2vsim/` | 否 | metal2vulkan + Turnip 的宿主模拟器（在手机上跑 Metal 调用回放） |

## k27/（macOS 27 主线）

| 文件 | 作用 |
|---|---|
| `build-kernel27.sh` | 编 k27 内核（`out/k27/xnu`，`XNU_KC=1 XNU_KEXT_CRYPTO=1`），补丁来自 `patches/xnu-12377` |
| `kc-build27.py`、`kc27-layout.py` | 用 27 的内核缓存 + 源码内核 + 自己的 native kext 链接 KC（`out/k27/kc-k27.bin`） |
| `try.sh` | 组 KC 并上机一次；`K27_NO_BOOT=1` 只编不启动（`product.py kc` 就是这样调它） |
| `build-native-display.sh` | DroidVMDisplay（显示 + virtio-gpu 传输，上游源 `VGPU_REF=59ec0a8`） |
| `build-native-video.sh` | DroidVMVideo（VideoToolbox 半虚拟化，上游源 `VT_REF=706338e` + `patches/droidvm-video`） |
| `build-native-aes.sh`、`build-native-audio.sh` | NativeAES、DroidVMAudio（virtio-snd） |
| `build-platform-cpu.sh`、`build-platform-rtc.sh` | ArmCpu（SMP/SPI/MSI 亲和）、ArmDTPlatform（PL030 RTC） |
| `panic.sh`、`dbg-state.sh`、`cpu-stacks.py`、`sym.py`、`segaddrs.*` | 运行中/卡死的 VM：panic 文本、调试器状态、各 CPU 栈、符号化 |
| `TODO.md` | k27 的进度与待办（只在本地） |

## scripts/（主要的）

- **KC / 内核**：`kc-build.py`、`kc_native.py`（native kext 静态链接）、`kc_reloc.py`、`fileset_kc.py`、`kc-disasm.py`、`kc-vtable.py`、`vtable-abi-diff.py`、`kext-kernel-imports.py`、`gen-iomfb-abi.py`、`build-native-kext.py`、`build-native-ram-block.py`、`build-droidvm-gpu.py`、`build-darwinboot.py`、`ptrauth_disc.py`。
- **Metal / GPU 用户态**：`build-turnip-macos.py`（Turnip，源在 `sources/UniXNU-turnip`）、`build-metal-bridge-macos.py`（metal2vulkan bridge）、`build-metal-plugin.sh`（插件包 `out/metal/plugin/NativeAdrenoMetal.bundle`）、`build-shader-cache-app.py`（上游 Shader Cache App → guest `/Applications/Shader Cache.app`，root worker 把系统 Metal 库编进 `/Library/GPUBundles/NativeAdrenoMetal.cache`，其他进程只读这一层；两个可执行文件随插件进信任缓存）、`build-metal-probe.sh`、`apple-ld.py`（Darling 里的 ld-classic）。
- **产品入口**：`product.py`（见上）。
- **系统盘与部署**：
  - `make-macos-disk.py`：生成单 APFS 容器新装盘与空种子；`grow-data-store.py` 扩容；`make-trust-bundle.py`：从 IPSW 生成苹果信任缓存。
  - `droidvm-app.py`：写 App 的 VM 配置（`register`/`net`/`pcie`/`usb`/`snd`/`media`/`disks`）、装新盘（`install`）、`start`/`stop`/`status`；
    `build_boot` 从头生成启动盘（`product.py boot` 用它；`droidvm-app.py boot` 是生成后直接推送的调试用法）。
  - `run-macos-vm.py`：生成 ADT、内核参数行和启动盘的函数库。
  - `stage-gpu-plugin.py`：`cdhash`/`trust_bundle` 供 `product.py` 用；它自己的 `main`（把插件和诊断任务写进 Data 种子，`--store`/`--disk`）
    和 `droidvm-app.py store-patch`、`data_store.py`、`fold-overlay.py` 属于旧的“种子 + SHNGDATA 覆盖层”Data 模型，新装盘不用。
    `build-metal-plugin.sh` 默认只出包，`STAGE=1` 才走旧的 stage。
- **guest 观察**：`rig-dmesg.py`（从宿主读 guest msgbuf，`--peek` 读内核变量）、`crash-symbolize.py`、`stackshot-*.py`、`xnu12377-smoke.sh`、`boot-cycle.sh`。
- **IPSW / APFS**：`ipsw-member.py`、`macos-fetch-member.py`、`macos-inputs.py`、`apfs-*.py`、`udif-expand.py`、`dsc-disasm.py`、`dsc-xref.py`。
- **构建环境**：`prepare-sources.py`、`import-linux-toolchain.py`、`start-linux-runtime.py`、`unixnu-linux.py`，以及 owner policy / 信任根相关的 `*-policy*.py`、`macos-root-*.py`。

## patches/

| 目录 | 打到哪里 | 说明 |
|---|---|---|
| `xnu-12377/` | `sources/xnu-12377` | 47 个补丁 + README，`git format-patch ac9718f..k27` 导出；已重建为仅单容器布局，所有补丁重放后的最终源码树与已验证内核一致。 |
| `droidvm-audio/` | UniXNU-droidvm `e29d087` 的 DroidVMAudio 源 | 0001 不自己做模块加载、0002 开播垫 40 ms、0003 输出延迟加宿主 1536 帧；`k27/build-native-audio.sh` 构建 |
| `droidvm-video/` | UniXNU-droidvm `706338e` 的 VT 源 | 0001–0011（0006 已弃）；0011 = Apple vtpv 语义 + 会话生命周期 |
| `droidvm-display/` | UniXNU-droidvm 的 virtio-gpu 源 | 0001 |
| `droidvm-gpu/` | `NativeAdreno/`、`UniXNU-droidvm/` | DroidVMGpu（现只负责发布），由本地分支 `droidvm-macos` 的 format-patch 导出 |
| `mesa-macos/` | Turnip（mesa-work） | 0001 日志、0002 virtgpu 后端找 AGXAccelerator；构建时 apply、结束时 reverse |
| `metal2vulkan-macos/` | metal2vulkan（bridge，固定在 555b13d） | 打在 AdrenoMetal 累积补丁 0046 之上：0003–0005 反射与 swizzle 修正、0006 内存池块上限 16 MiB、0007 内存压力下不预留 + 按空闲清理（NativeMetal 935c468 的 bridge 要用）；列表在 `build-metal-bridge-macos.py` 的 `PATCHES` |
| `shader-cache/` | Shader Cache App 的 worker（复制出的 `PrimeShaders.h`） | 0001 函数级多线程编译、去掉每管线 20 ms 停顿、QoS 改 UTILITY；`build-shader-cache-app.py` 打 |
| `drivers/` | UniXNU 驱动 | ArmCpu 等 |
| `darwinboot-*.patch` | DarwinBoot | arm64e、512 MB 内核与内存回收 |

## overlay/

- `kext/`：板级 kext 源码与描述 JSON。DroidVMDisplay（IOMobileFramebuffer + virtio-gpu）、DroidVMVideo（VT 半虚拟化外壳）、DroidVMInput（触屏/键盘）、DroidVMEthernet（virtio-mmio 网卡）、DroidVMDataStore（Data 盘）、DroidVMGpuKext、NativeAES、ARMPlatformStandIn、NativeKextGlue、NativeUfsStoreStub 等。
- `metal/`：`NativeAdrenoMetalPlugin.mm`（插件入口：WindowServer 设置队列优先级、原地读 YCbCr 开关等）、`MetalProbePlugin.mm`、`metal-probe.mm`、`gpu-bench.mm`、`frameworks/`。
- `droidvm/`：早期 PCI virtio 驱动和板级树脚本（14.6.1 时期）。

## configs/

`product-k27.json`（产品配置：开关、内核参数、kext 构建列表、GPU 与启动盘路径）、`macos-27.2-26B8125.json`、`macos-27.2-26B123.json`（当前的两个 IPSW）、`macos-27.0.1-26A434.json`、`macos-23G93.json`（IPSW 与成员固定版本）、`sources.lock.json`（`sources/` 的固定提交）、`kc-keep.txt`（KC 保留的苹果 kext）、`arm64e-apple-darwin.json`（Rust arm64e pauth target）、`linux-imports.json`。

## docs/（只在本地）

| 文件 | 内容 |
|---|---|
| `xnu-12377-port.md` | 内核移植记录 |
| `k27-userspace-manifest.md` | 用户空间清单 |
| `k27-virtio-gpu-3d-plan.md` | GPU 迁 virtio-gpu 3D 方案 |
| `k27-vt-paravirt-plan.md` | VT 半虚拟化方案（含 PlanesInPlace） |
| `k27-vt-zero-copy-plan.md` | 视频零拷贝方案（Z0+Z2，P0–P4 状态） |
| `k27-vt-p3-status.md` | 锁屏航拍 P3 进展、0011、代码状态、常用命令 |
| `k27-audio.md` | 音频（virtio-snd）根因（CoreAudio 24 MHz、宿主线程调度）、代码状态、待办 |
| `reims-vgpu-vtpv-contract.md` | Apple vtpv 宿主协议实测规范（reims-vgpu 整理） |
| `TODO-gpu.md`、`log-2026-10.md`、`p1-linux-2026-10-22.md` | 早期 GPU 待办、10 月日志、Linux P1 记录 |

## sources/（只在本地，上游树）

| 目录 | 来源 | 用途 |
|---|---|---|
| `xnu-12377/` | apple-oss-distributions/xnu | 内核；分支 `k27`（当前）、`k27-unlayered`（旧史）、`x12377-*` |
| `UniXNU/` | Droid-VM/UniXNU（分支 `macos-droidvm`） | UniXNU 主树；`drivers/NativeMetal` 是独立仓库（Droid-VM/NativeMetal，本地分支 `macos-hackintosh` = `805ea2b`：Droid-VM `wip/hackintosh` 935c468 + AdrenoMetal main 9a9da56 的合并）；`drivers/NativeAdreno`；`.cache/gpu-reference/metal2vulkan` 是 bridge 的翻译器源码 |
| `UniXNU-turnip/` | UniXNU 的工作树，固定在 Droid-VM/UniXNU `wip/droidvm` `0f7b62a` | 提供 Turnip 的 mesa（`.cache/mesa-work` = Droid-VM/mesa `cecc0e9` + `adreno-compiler-inputs.json` 记录的 33 个补丁，手动 apply）；其板级 `patches/metal2vulkan` 针对板子自己的翻译器栈，bridge 不用 |
| `UniXNU-droidvm/` | Droid-VM/UniXNU-droidvm | 板级源：VT（`VT_REF`）、virtio-gpu（`VGPU_REF`）；本地分支 `droidvm-macos` 供 DroidVMGpu 导出补丁 |
| `edk2/`、`GunyahBootPkg/` | edk2-gunyah、unixnu-droidvm-ci | 固件（GOP、`edk2-macos.fd`） |
| `IONetworkingFamily/` | apple-oss-distributions | DroidVMEthernet 用的头文件 |
| `apfsprogs/`、`linux-apfs-rw/`、`lzfse/` | linux-apfs 等 | 在 Linux 上读写 APFS（种子、Data 卷） |
| `macos-UnifiedLogs/` | mandiant | 解析统一日志 |

## out/（只在本地，构建产物）

| 目录 | 内容 |
|---|---|
| `k27/` | `kc-k27.bin`（上机用的 KC）、`kernel-k27.macho`、`kc-k27.nm`/`natives.json`（符号）、`src/`（导出并打好补丁的 kext 源，如 `src/DroidVMVideo`）、`obj/`、日志 |
| `x12377/` | 内核构建树与 native kext 目标文件（`native-kexts/`） |
| `metal/` | `mesa-tu/`（Turnip dylib）、`bridge/`（`libnative_metal_bridge.a`）、`plugin/`（插件包）、`probe/`；`stage/` 是旧 Data 模型的产物，已不用 |
| `rig/` | 符号表等调试用产物 |
| `product/k27/` | `product.py boot` 的产物：`boot.img`、`kernel.macho.trustcache`、`manifest.json`（提交号、KC/启动盘哈希、信任的 CDHash、内核参数） |
| `tmp/` | 临时文件（本机 `/tmp` 配额小，统一用 `TMPDIR=$PWD/out/tmp`）；`data-store.img` 是最近一次拉回的手机 Data 存储副本 |
| 其他 | 23G93/早期路线的产物（`app`、`darwinboot`、`kc`、`osfiles` 等） |

## research/（只在本地）

- `vthost-harness/`：DroidVMVTHost 用户态测试框架（假 virtio-media + 假 VT，16 个场景；`./build.sh && ./suite.sh`）。`kext/` 下是打好补丁的源码和 `.0010` 基线。
- `vidc-probe/`：手机上直接测 msm_vidc（`vidc-probe`、`vidc-replay`、`vidc-ctrls`）。
- `vt-probe/`、`vt-ab/`：guest 内 VT 编解码探针、A/B 测试。
- `debug-2026-10-27` … `debug-2026-11-03`：当时的诊断补丁和脚本（针对旧代码，不一定还能套上）。
- `re/`、`ref/`：逆向笔记与参考数据；`runs/`：早期上机记录；`x12377-mainline/`：内核主线移植留档。

## 本仓库之外的相关部分

| 位置 | 内容 |
|---|---|
| `~/crosvm/external/crosvm` | crosvm（分支 `wip/macos-virtio-gpu`，rebase 在 Droid-VM `wip/hackintosh` 上）：msm_vidc 解码后端 `devices/src/virtio/media/android_codec_backend/vidc.rs` 等 |
| `~/crosvm/external/virtio-media`、`external/rust/crates/v4l2r` | 分支 `droidvm-hackintosh`（跟 Droid-VM `wip/hackintosh`） |
| `~/crosvm/build_crosvm.sh` | 编 crosvm；产物在 `out/soong/.intermediates/external/crosvm/crosvm_device_only/...` |
| 手机 `/data/data/cn.classfun.droidvm/` | App 数据：`usr/bin/crosvm`（换文件要 chown + chcon）、`cache/`（`daemon.log`、`console_<VM>_{serial1,stderr}.log`） |
| 手机 `/data/media/0/DroidVM/MacOS/` | `boot.img`（启动盘，`boot.img.prev` 是上一份）、`data-pcie.img`（系统盘，GPT/APFS，virtio-blk PCI）、`edk2-macos.fd`、`generated.dtb`（crosvm 导出的 FDT，生成 ADT 用）；`data-store.img` 是转换前的旧存储，留作回退 |
