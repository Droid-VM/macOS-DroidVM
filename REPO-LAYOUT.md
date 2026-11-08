# macOS-DroidVM 仓库结构（2026-11-04）

本仓库（`~/crosvm/macos`，远端 `Droid-VM/macOS-DroidVM`，分支 `main`）在手机上的 DroidVM（crosvm + Gunyah）里跑 macOS 27.0.1（26A434）：
源码编译的 xnu-12377 内核 + 27 的内核缓存 kext、自己的板级 kext、Metal 插件（Turnip/metal2vulkan），以及配套的构建、部署、诊断脚本。

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
| `configs/` | 是 | 构建配置与固定版本 |
| `compat/` | 是 | 在 Linux 上跑 UniXNU/xnu 构建的兼容层 |
| `tests/` | 是 | `test_range_layout.py` |
| `docs/` | 否 | 方案与进展文档（见下） |
| `sources/` | 否 | 上游源码树（见下） |
| `artifacts/` | 否 | 从 IPSW 取出的苹果原始件（23G93、27.0.1）与启动输入 |
| `toolchains/` | 否 | Linux 上的苹果工具链：`linux/`（Darling 镜像、appleclang、cctools、apple-iig）、`sdks/`（MacOSX26.1.sdk、iOS SDK） |
| `out/` | 否 | 全部构建产物与临时文件（见下） |
| `research/` | 否 | 诊断代码、探针、测试框架（见下） |
| `tools/m2vsim/` | 否 | metal2vulkan + Turnip 的宿主模拟器（在手机上跑 Metal 调用回放） |

## k27/（macOS 27 主线）

| 文件 | 作用 |
|---|---|
| `build-kernel27.sh` | 编 k27 内核（`out/k27/xnu`，`XNU_KC=1 XNU_KEXT_CRYPTO=1`），补丁来自 `patches/xnu-12377` |
| `kc-build27.py`、`kc27-layout.py` | 用 27 的内核缓存 + 源码内核 + 自己的 native kext 链接 KC（`out/k27/kc-k27.bin`） |
| `try.sh` | 组 KC 并上机一次；`K27_NO_BOOT=1` 只编不启动 |
| `build-native-display.sh` | DroidVMDisplay（显示 + virtio-gpu 传输，上游源 `VGPU_REF=59ec0a8`） |
| `build-native-video.sh` | DroidVMVideo（VideoToolbox 半虚拟化，上游源 `VT_REF=706338e` + `patches/droidvm-video`） |
| `build-native-aes.sh` | NativeAES |
| `panic.sh`、`dbg-state.sh`、`cpu-stacks.py`、`sym.py`、`segaddrs.*` | 运行中/卡死的 VM：panic 文本、调试器状态、各 CPU 栈、符号化 |
| `TODO.md` | k27 的进度与待办（只在本地） |

## scripts/（主要的）

- **KC / 内核**：`kc-build.py`、`kc_native.py`（native kext 静态链接）、`kc_reloc.py`、`fileset_kc.py`、`kc-disasm.py`、`kc-vtable.py`、`vtable-abi-diff.py`、`kext-kernel-imports.py`、`gen-iomfb-abi.py`、`build-native-kext.py`、`build-native-ram-block.py`、`build-droidvm-gpu.py`、`build-darwinboot.py`、`ptrauth_disc.py`。
- **Metal / GPU 用户态**：`build-turnip-macos.py`（Turnip，源在 `sources/UniXNU-turnip`）、`build-metal-bridge-macos.py`（metal2vulkan bridge）、`build-metal-plugin.sh`（插件包 `out/metal/plugin/NativeAdrenoMetal.bundle`；`NO_STAGE=1` 只出包）、`build-metal-probe.sh`、`apple-ld.py`（Darling 里的 ld-classic）。
- **Data 盘与部署**：
  - `stage-gpu-plugin.py`：把插件装进 Data 卷，可选 `--log-stream`、`--top`、`--run`、`--probe`、`--file`。改已有 Data 必须用 `--base 种子 --store 存储`，**不能重新生成种子**。
  - `data_store.py`、`fold-overlay.py`：手机 Data 存储格式（种子 + SHNGDATA 覆盖层）。
  - `droidvm-app.py`：写 App 的 VM 配置、重建启动盘（`boot`）、`start`/`stop`、`store-patch`（把补丁块写回手机，自动备份 undo）。
  - `run-macos-vm.py`：生成 ADT/启动盘。
  - `make-*-seed.sh`、`make-macos-systemos.sh`、`make-trust-bundle.py`：生成种子、SystemOS 盘、信任缓存。
- **guest 观察**：`rig-dmesg.py`（从宿主读 guest msgbuf，`--peek` 读内核变量）、`crash-symbolize.py`、`stackshot-*.py`、`xnu12377-smoke.sh`、`boot-cycle.sh`。
- **IPSW / APFS**：`ipsw-member.py`、`macos-fetch-member.py`、`macos-inputs.py`、`apfs-*.py`、`udif-expand.py`、`dsc-disasm.py`、`dsc-xref.py`。
- **构建环境**：`prepare-sources.py`、`import-linux-toolchain.py`、`start-linux-runtime.py`、`unixnu-linux.py`，以及 owner policy / 信任根相关的 `*-policy*.py`、`macos-root-*.py`。

## patches/

| 目录 | 打到哪里 | 说明 |
|---|---|---|
| `xnu-12377/` | `sources/xnu-12377` | 42 个 + README，`git format-patch ac9718f..k27` 导出；改内核后要重新导出。0041 来自未提交的工作树 diff，提交前别按区间重导（会被 0042 的提交顶掉），单独 `format-patch -1 --start-number` |
| `droidvm-audio/` | UniXNU-droidvm `e29d087` 的 DroidVMAudio 源 | 0001 不自己做模块加载、0002 开播垫 40 ms、0003 输出延迟加宿主 1536 帧；`k27/build-native-audio.sh` 构建 |
| `droidvm-video/` | UniXNU-droidvm `706338e` 的 VT 源 | 0001–0011（0006 已弃）；0011 = Apple vtpv 语义 + 会话生命周期 |
| `droidvm-display/` | UniXNU-droidvm 的 virtio-gpu 源 | 0001 |
| `droidvm-gpu/` | `NativeAdreno/`、`UniXNU-droidvm/` | DroidVMGpu（现只负责发布），由本地分支 `droidvm-macos` 的 format-patch 导出 |
| `mesa-macos/` | Turnip（mesa-work） | 0001 日志、0002 virtgpu 后端找 AGXAccelerator；构建时 apply、结束时 reverse |
| `metal2vulkan-macos/` | metal2vulkan（bridge） | 0001 WindowServer 原地读 YCbCr 平面 |
| `drivers/` | UniXNU 驱动 | ArmCpu 等 |
| `darwinboot-*.patch` | DarwinBoot | arm64e、512 MB 内核与内存回收 |

## overlay/

- `kext/`：板级 kext 源码与描述 JSON。DroidVMDisplay（IOMobileFramebuffer + virtio-gpu）、DroidVMVideo（VT 半虚拟化外壳）、DroidVMInput（触屏/键盘）、DroidVMEthernet（virtio-mmio 网卡）、DroidVMDataStore（Data 盘）、DroidVMGpuKext、NativeAES、ARMPlatformStandIn、NativeKextGlue、NativeUfsStoreStub 等。
- `metal/`：`NativeAdrenoMetalPlugin.mm`（插件入口：WindowServer 设置队列优先级、原地读 YCbCr 开关等）、`MetalProbePlugin.mm`、`metal-probe.mm`、`gpu-bench.mm`、`frameworks/`。
- `systemos-shims/`：SystemOS 盘里的替身程序。
- `droidvm/`：早期 PCI virtio 驱动和板级树脚本（14.6.1 时期）。

## configs/

`macos-27.0.1-26A434.json`、`macos-23G93.json`（IPSW 与成员固定版本）、`sources.lock.json`（`sources/` 的固定提交）、`kc-keep.txt`（KC 保留的苹果 kext）、`arm64e-apple-darwin.json`（Rust arm64e pauth target）、`linux-imports.json`。

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
| `UniXNU/` | Droid-VM/UniXNU（分支 `macos-droidvm`） | UniXNU 主树；`drivers/NativeMetal` 是独立仓库（Droid-VM/NativeMetal，本地分支 `macos-hackintosh` = `f4ce342` + `a9531ab`）；`drivers/NativeAdreno`；`.cache/gpu-reference/metal2vulkan` 是 bridge 的翻译器源码 |
| `UniXNU-turnip/` | UniXNU 的工作树，固定在 Droid-VM/UniXNU `wip/droidvm` `ef4486d` | 提供 Turnip 的 mesa（`.cache/mesa-work` = Droid-VM/mesa `cecc0e9` + 18 个补丁，手动 apply）和板级 `patches/metal2vulkan` 0011–0022 |
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
| `metal/` | `mesa-tu/`（Turnip dylib）、`bridge/`（`libnative_metal_bridge.a`）、`plugin/`（插件包）、`probe/`、`stage/`（**`scratch-data.img` = Data 种子**、`kernel.macho.trustcache`、`store-patch.*`） |
| `rig/` | 符号表等调试用产物 |
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
| 手机 `/data/media/0/DroidVM/MacOS/` | `boot.img`（启动盘）、`data-store.img`（Data 存储，17 GiB 稀疏）、`data-store.undo.*`、`edk2-macos.fd` |
