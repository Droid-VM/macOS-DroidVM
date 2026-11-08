# TODO：WindowServer 与 GPU（路线 B：客户机走 Droid-VM 驱动）

2026-10-24 定的路线：把 UniXNU 的 NativeAdreno / DroidVMGpu 内核驱动和 NativeMetal 插件移植到 macOS 27 客户机，主机侧用 DroidVM 现成的 crosvm `--droidvm-gpu` 设备（客户机的请求在手机自己的 KGSL 上执行）。其余守护进程（xprotectd、fskitd、digest-service、apsd、endpointsecurity、xpcproxy 78）暂不处理，只记录在 `docs/xnu-12377-port.md`。

## 参考

| 用途 | 来源 |
| --- | --- |
| GPU 驱动（内核 + Metal 插件 + 显示） | Droid-VM/UniXNU 分支 `wip/droidvm`（本地 `sources/UniXNU`，`git fetch origin wip/droidvm`）：`drivers/NativeAdreno`（约 6.6k 行）、`drivers/NativeMetal`（约 6.5k 行）、`drivers/NativeMobileDisplay`（约 1.2k 行）、`kits/AdrenoPM4`、`kits/AdrenoFirmware`、`patches/metal2vulkan`、`patches/xnu/offline-native-gpu-broker.patch` 等 |
| DroidVM 板级与 crosvm 对接 | Droid-VM/UniXNU-droidvm（本地 `sources/UniXNU-droidvm`）：`package/DroidVMGpu.cpp`（942 行，替换 NativeAdreno 里管硬件的部分：VM 地址空间、CP ring、计时器）、`package/DroidVMGpuWire.h`（wire 3，32 个客户端槽）、`scripts/build-droidvm-gpu.py`、`board.toml`（`droidvm-gpu=1`、`droidvm-gpu-metal=1`、`droidvm-gpu-clients=...`） |
| macOS 客户机怎么发现 GPU/显示 | medfa12/apple-silicon-anyos-project（只看接口，不搬代码：GPL-2.0 / LGPL-3.0） |
| 另一个参考 | xyyyds0106/ios-vermeer-lab `GPU-PORT.md`：UniXNU Adreno 代码的复用边界（加速器构造绑定原版 IOAccelerator 地址、插件里的 QuartzCore 钩子都是目标专用的） |

主机现状：手机上的 `crosvm` / `crosvm-mmio` 都带 `droidvm-gpu`（二进制里能搜到该字符串）。

## 已知事实（来自本次调查）

- KC 只保留 9 个 kext 时 WindowServer 第一步查 IOHIDSystem 就失败退出。加 `com.apple.iokit.IOHIDFamily`（`/tmp/keep4.txt`）后：WindowServer 打开 IOHIDSystem，接着查 `AppleDisplayManager` 返回 NotFound，然后不退出、一直等待。`AppleDisplayManager` 在 26.5 vma2 内核缓存里不存在。
- 诊断：`iokit-log=WindowServer`（IOUserClient.cpp：查找 / 通知 / 打开）；跑时关掉 `stderr-log`、`exec-log`，烟测 ≥340 s（WindowServer 约 2~3 分钟后才被拉起）。
- vma2 设备树的 GPU 是平台 MMIO：`arm-io/gfx`（`paravirtualizedgraphics,gpu`）、`arm-io/iosurface-mapper`（`paravirtualizedgraphics,iosurface`）。路线 B 不用它们，但可对照 macOS 的 IOGPU 发现流程。
- KC（kc265）里现成的相关 kext：IOGraphicsFamily、IOSurface、IOMobileGraphicsFamily、IOHIDFamily、AppleM2ScalerCSCDriver、AppleParavirtGPUIOGPUFamily、AppleParavirtIOSurface（IOGPUFamily 是否在、版本如何待查）。

## 当前状态（2026-10-24）

- 代码都已提交（macos `9122607`），文档只留本地。
- 下一步从第 0 步开始：查 `--droidvm-gpu` 的参数和设备树节点。开始前先用当前补丁版本完整重编 + 烟测一次（≥340 s，`iokit-log=WindowServer`），确认 WindowServer 仍停在 `AppleDisplayManager`。
- KC 保留列表要从 `/tmp/keep4.txt` 落到仓库（例如 `configs/` 或 `overlay/kext/keep.txt`），`kc-try.sh` 改为默认读它。

## 步骤

### 0. 主机与设备树
- [ ] 查 crosvm `--droidvm-gpu` 的参数和 MMIO/中断布局（UniXNU-droidvm `board.toml` 的 `tool_args`、`make-droidvm-adt.py`），在 `scripts/run-macos-vm.py` / `droidvm-app.py` 的 VM 配置里加上它。
- [ ] `out/adt/make-droidvm-adt.py` 发布对应的 `/arm-io` 节点（和 UniXNU-droidvm 一致），确认 crosvm 提供的每个 virtio-mmio 设备都在 ADT 里（README：设备树里缺设备会让手机卡死重启）。

### 1. 内核驱动（native kext 进 KC）
- [ ] 列出 NativeAdreno + DroidVMGpu 实际链接的源文件（按 `build-droidvm-gpu.py`，不链 NativeAdrenoVm/Ring/Timer.cpp），用 `scripts/build-native-kext.py` 编成 arm64e 对象，写 `overlay/kext/DroidVMGpu.json`，用 `kc_native.py` 链进 KC。
- [ ] 依赖：IOGPUFamily / IOSurface / IOAccelerator 在 macOS 26.5 KC 里的实际类与 vtable；把 iOS 原版 IOAcceleratorES 构造器/析构器/元类地址的绑定（NativeAdrenoAccelerator 的 builder）改成按 macOS KC 符号解析（`kc_native.py` 的 vtable 检查）。
- [ ] 4 KiB 页：本内核就是 4 KiB，NativeAdrenoQueryCpu4K 的检查应直接通过；核对 udmabuf/IO-coherent 导入和 `native_pmap_user_mappings`（UniXNU `afb8db4` 的 XNU 补丁）等内核侧依赖，按需移植成我们的 xnu 补丁。
- [ ] 内核补丁：`patches/xnu/offline-native-gpu-broker.patch`、`zzw-native-adreno-sandbox-grant.patch`、`zzy-native-gpu-addon-mount.patch` 逐个评估是否需要。
- [ ] 验收：`droidvm-gpu-selftest=1` 的 CP_MEM_WRITE 自检通过，内核日志出现 `droidvm-gpu: ...` 正常进度。

### 2. Metal 插件（用户态）
- [ ] 弄清 macOS 27 Metal.framework 怎么发现设备和加载插件（IOGPU 注册表属性：MetalPluginName / MetalPluginClassName / 插件 bundle 路径），对照 iOS 上 `droidvm-gpu-metal=1` 注册 AGXAccelerator 的做法。
- [ ] 用 macOS SDK（arm64e）编 NativeMetal 插件 + metal2vulkan（带 UniXNU 的 patches）+ turnip（Mesa），它们走 NativeAdreno 的 user client。
- [ ] 插件里 iOS 专用的 QuartzCore / RenderBox 钩子换成 macOS 27 的对应做法，或先关掉。
- [ ] 部署：插件 bundle 放进 Data 种子或 SystemOS 覆盖层（参考 `add-gpu-plugin-data.py`），信任缓存 / AMFI 放行（参考 UniXNU `e8e49c1` "trust the Metal plugin"）。
- [ ] 验收：一个最小 Metal 探针（MTLCreateSystemDefaultDevice + clear + readback）在客户机里跑通。

### 3. 显示（WindowServer）——走 IOMFB（2026-10-24 定）
Apple Silicon 的正统显示栈是 IOMobileFramebuffer：真机 AppleCLCD2（DCP），vma2 是 AppleParavirtGPU + AppleParavirtDisplay（IOMobileFramebufferLegacy 子类）。我们照 vma2 写 **DroidVMDisplay**（IOMobileFramebufferLegacy 子类，帧缓冲先用 GOP）。IOFramebuffer（IOBootFramebuffer）只作备用/排障手段（`MACOS_IOFB=1`，见下文“IOFramebuffer 路线”），不进默认配置：它是 Intel 时代的兼容残留，Apple 在 arm64 上不用，呈现只能 CPU 拷贝，以后接不上 GPU 合成/零拷贝。
- [x] 弄清显示栈：IOMFB；用户态发现链见下文“WindowServer 的显示发现链”。`AppleDisplayManager` 缺失不致命。
- [x] DroidVMDisplay 阶段 0：ABI 头（`gen-iomfb-abi.py`）+ 9 个纯虚槽，虚表检查 473 槽 0 问题；IOMobileGraphicsFamily 依赖的 AppleARMPlatform 等用替身 `ARMPlatformStandIn` 顶上，链接通过。
- [x] 发现（代码完成，未上机）：ADT `/arm-io` 加 compatible `paravirtualizedgraphics,gpu` 的节点 + 名为 `AppleParavirtGPU`、带 `DisplayPortCount=1` 的服务，使用户态期望 1 个帧缓冲并注册 IOMobileFramebuffer 匹配通知（留意别的组件把它当 PVG）。
- [x] DroidVMDisplay 阶段 1（代码完成、KC 链接通过，未上机；照 APD 反汇编 `research/re/apd/*.s`）：`start`/`start_hardware`/`createDisplayAttributes`（发布 ProductAttributes、TimingElements、ColorElements、NativeFormat*、IOMFBMaxSrcPixels 等键）、`create_default_fb_surface`；`swap_begin_gated` 由 16 ms 定时器驱动；`program_hardware_gated`（槽 473，主表面 swap+2752、光标 swap+2760）把 IOSurface CPU 拷到 GOP（`PE_state.video`，0x13FC00000 1280x800 row 5120），再 `swap_complete_gated`；其余钩子按 APD 的简单实现返回（verify_swap=1、layer_map=0、unsupported 等，见进展）。
- [ ] KC：`MACOS_DISPLAY=1` 加入 DroidVMDisplay + ARMPlatformStandIn（闭包带进 IOMobileGraphicsFamily、IOAVFamily、IOSurface、AppleM2ScalerCSCDriver 等），上机确认能启动；`IOMobileFramebufferLegacy::start` 会等 `IOSurfaceRoot`。
- [ ] 验收：WindowServer 打开 IOMFB、不再空等，simplefb 上出现桌面。
- [ ] 以后：呈现改零拷贝（GOP 换成 crosvm 显示 blob / Adreno 合成），接 Metal（第 2 步）。

#### 阶段 1 实现要点（2026-10-24，静态）
- 文件：`overlay/kext/DroidVMDisplay/DroidVMDisplay.cpp`、`overlay/kext/DroidVMDisplay.json`。编译：`python3 scripts/build-native-kext.py DroidVMDisplay overlay/kext/DroidVMDisplay/DroidVMDisplay.cpp overlay/kext/NativeKextGlue.cpp -Ioverlay/kext/DroidVMDisplay`。离线建 KC：虚表检查 473 槽 0 问题，替身重绑 12 指针 + 8 branch。
- 开关 `MACOS_DISPLAY=1`：register/prepare（或 `droidvm-app.py boot`）时 make_adt 加 `/arm-io/display`（compatible `paravirtualizedgraphics,gpu`）；kc-try 加 ARMPlatformStandIn + DroidVMDisplay。
- 类：`AppleParavirtGPU`（IONameMatch 该 compatible，设 `DisplayPortCount=1` 后 registerService）→ `DroidVMDisplay`（IOProviderClass AppleParavirtGPU）。
- 逆向结论（都对 kc265）：
  - `Legacy::start` 用 `tbz w0,#0` 判 `start_hardware`（bool；gen-iomfb-abi.py 的 RETURNS 已改），`create_default_fb_surface` 返回值不看（找不到 `PurpleGfxMem` 只打日志）；`use-legacy-DART`/`iommu-parent` 都没有时跳过 IOMapper；`this+6288` = `OSDynamicCast(AppleARMIODevice, provider)`，我们这里为空，所以 PM 走 `getPlatform()->PMRegisterDevice(provider, this)`，`get_dot_pitch` 必须覆盖（Legacy 版会对它解引用）。
  - `Legacy::swap_begin_gated` 是空函数，出队/TAILQ 摘除/`update_swap_info_state_gated(swap,2)`/`program_hardware`/`dropSwap_gated` 全由子类做（照 APD）；`swap_layer_map`/`surface_layer_map`/`surface_layer_unmap` 的 Legacy 默认会做 DART 映射，必须覆盖成空操作。
  - 交换完成通知：`notify_swap_done_gated` 填 48 字节 SwapInfoBlob（6 项环，`this+6902` 非零时暂存），调 `Legacy::swap_info_notify_dispatch_gated`，后者对每个请求调 `do_swap_info_notify_gated` → `IOUserClient::sendAsyncResult64WithOptions`（protected，按符号名调）。
  - 宽高在 `this+6400/6404`，由 `set_digital_out_mode(颜色ID, 时序ID)` 写入并发布 `DisplayWidth/DisplayHeight/DPTimingModeId`；APD 在 `createDisplayAttributes` 结尾用第一个时序和颜色元素调它。
  - 时序：`IOAVVideoTimingElement::withData(data,2,4)`，80 字节数据每轴 32 字节（total+4、active+8、syncWidth+12、backPorch+16、frontPorch+20、syncRate+24）；APD 只填水平 active、水平 syncRate=刷新率×高、垂直 active、垂直 syncRate=刷新率。元素 +16 是 ID（时序 1000+i，颜色 100|i），+24 是分数。颜色：`IOAVVideoColorElement::withCapabilities(2, 位深, 0, 0, EDR?2:0, 16, false, 0,0,0,0)`。
  - 电源状态表 `{1,0,0,0}`、`{1,kIOPMDeviceUsable,kIOPMPowerOn,kIOPMPowerOn}`；`this+140`（IOMobileFramebuffer 最后一个字段）在 PMinit 前置 1。
- 呈现：IOSurface 主表面（swap+2752，swap+824 bit0）按行 `readBytes` 到 GOP 的写合并映射，再 `swap_complete_gated()`；不设 `CursorPlane`，光标由 WindowServer 画进主表面。首帧和像素格式变化时打印表面参数（宽高、行字节、偏移、格式）。
- 未做/待上机看：gamma 读取返回 unsupported；`ParavirtDisplayPrefs`、Luminance 未发布；`primary` 属性取值照 APD（显示序号 0）。

### 4. 收尾
- [ ] 每一步的代码按修复分组提交（内核补丁进 `patches/xnu-12377/`，kext 描述进 `overlay/kext/`），文档和本 TODO 只留本地。
- [ ] 记录授权：UniXNU 驱动为 MIT / BSD-2-Clause-Patent；anyos 只作接口参考，不复制代码。

## 进展（2026-10-24 下午，全部只做了静态/链接验证，未上机）

### 第 0 步：主机与设备树（代码完成，待上机）
- `MACOS_GPU=1`：`droidvm-app.py` 的 VM 模板加 `--droidvm-gpu`（换模板要重新 register + prepare，让 crosvm 重新 dump FDT），`boot_disk` 让 `run.make_adt(..., gpu=True)` 取 FDT 里最后一个 virtio-mmio 窗口作 `--gpu-mmio`（FDT 里还没有就报错，不会生成缺设备的 ADT），内核参数自动加 `droidvm-gpu=1 droidvm-gpu-selftest=1`。
- **wire 版本**：本地 crosvm（external/crosvm 分支 drm-droidvm-mmio，7d1e255）和 UniXNU-droidvm 本地检出（bf7fc44）都是 wire 1；但 UniXNU `wip/droidvm` 锁定的 NativeAdreno（b686b90，4 个客户端窗口）配套的是 UniXNU-droidvm `origin/wip/hackintosh`（wire 3，32 客户端槽，每客户端独立 KGSL context），对应 crosvm 是 `droidvm/wip/virtio-mmio`（WIRE_VERSION=3）。我们按 wire 3 构建。**上机前必须确认手机 crosvm 的 wire 版本**（不是 3 就要用 `wip/virtio-mmio` 重编 crosvm 再部署），否则驱动报 "unusable device facts"。

### 第 1 步：DroidVMGpu 内核驱动（编译 + KC 链接通过）
- `scripts/build-droidvm-gpu.py`：按 UniXNU 的锁定提交导出 NativeAdreno/AdrenoPM4/ArmSmmu4K 到 `out/x12377/src-gpu`，直接执行 hackintosh 分支 `build-droidvm-gpu.py` 的 staging 部分（Publish/Memory 的改动原样复用），再用 `build-native-kext.py` 编成 9 个对象。`build-native-kext.py` 现在 `.c` 用内核 C 文件的编译参数。
- `overlay/kext/DroidVMGpuKext.cpp`：`DroidVMGpuStarter` 匹配 `/arm-io/gpu`（IONameMatch `droidvm,gpu`），start 里调原板级钩子 `sheng_gpu_power_probe()`；Metal 加速器（iOS AGXAccelerator 构造器）不编，桩掉；`native_gop_handoff_*`、`boot_log_export_put` 桩掉。描述 `overlay/kext/DroidVMGpu.json`。
- 内核补丁 0007 `native_pmap_user_mappings`（移植 UniXNU zzx-pmap-user-mappings，12377 的 pv 头接口基本一样，IOMMU 判断在 `PVH_FLAG_IOMMU` 下）。补丁 0008 是诊断。
- `kc-build.py`：native kext 头部预留 0x800→0x1000（`NATIVE_HEADER_RESERVE`）。`kc-try.sh` 在 `MACOS_GPU=1` 时自动加 DroidVMGpu。

### 第 3 步：显示（静态结论 + 骨架）
- vma2 上的显示：`AppleParavirtDisplay`（AppleParavirtGPUIOGPUFamily）继承 IOMobileGraphicsFamily 的 **`IOMobileFramebufferLegacy`**（实例 0x1af8，473 槽），基类实现交换队列/user client/通知，子类只覆盖约 30 个硬件钩子：`start/stop`、`start_hardware`、`stop_hardware_gated`、`swap_begin_gated`、`verify_swap`、`program_hardware_gated`(新增槽 473)、`swap_layer_map`、`surface_layer_map/unmap`、`notify_swap_done_gated`、`notify_crc_ready_gated`、`do_power_state_change_gated`、`set_display_device`、`set_digital_out_mode`、`get_dot_pitch`、gamma、color remap、`supported_frame_info`、`set_parameter`、`swap_set_color_matrix`、`are_timings_enabled`、`copyProperty`、`createDisplayAttributes` 等。所以 macOS 显示驱动按这个模式写，不用移植 iOS NativeMobileDisplay 的整套实现。
- `scripts/kc-vtable.py KC CLASS [--base CLASS]`：按槽列 KC 里的虚表（函数名 + PAC 判别值）。
- `scripts/ptrauth_disc.py`：clang 的 ptrauth 字符串判别值（SipHash-2-4）。**已验证**：arm64e 虚表槽判别值 = 引入该槽的类限定修饰名的哈希（Legacy 自己的纯虚表项例外地用了重声明名，子类用引入者的）。
- `scripts/gen-iomfb-abi.py KC OUT.h`：生成 `overlay/kext/DroidVMDisplay/IOMobileFramebufferABI.h`；每个槽的方法名和参数都是“在 KC 符号里找哈希等于 APD 该槽判别值的方法”得到的，签名是验证过的（ICF 别名不会误导）；返回类型修饰名里没有，默认 IOReturn，覆盖/调用的槽在 `RETURNS` 表里改。
- `overlay/kext/DroidVMDisplay/DroidVMDisplay.cpp` 阶段 0 骨架：只实现 Legacy 留空的 9 个纯虚槽。KC 链接后虚表检查 473 槽 **0 个问题**。
- 依赖：IOMobileGraphicsFamily 的闭包拉进 AppleARMPlatform（真机平台 kext，且其 `__TEXT` 被我们更大的内核 `__TEXT` 盖住）、AppleIISController、AppleAudioClockLibs（同样被盖）。`kc-build.py` 新增 native kext 的 `stands_in_for`：这些 kext 不进 KC，保留 kext 对它们的指针/branch 按符号名重绑到替身，plist 里的库依赖换成替身。替身 `overlay/kext/ARMPlatformStandIn.cpp`：AppleARMFunction::withProvider×2（返回空）、registerFunctionParent、AppleARMIODevice/AppleARMIISDevice 元类（无对象属于它们）、gAppleARMFunctionCall/gAppleARMPEFindCoproviderKey、AppleAudioClock::Utility::getSynchronousClockDomain。共 12 个指针 + 8 个 branch 重绑。
- 下一步：反汇编 APD 的硬件钩子，弄清 swap 交付（surface_layer_map 拿到 IOSurface）、完成通知（notify_swap_done_gated / swap_complete）、start_hardware 要发布的属性（createDisplayAttributes 的键）；帧缓冲用 PE_state.video（GOP），先 CPU 拷贝。

### WindowServer 的显示发现链（2026-10-24，静态分析 dyld 缓存得出）
- 工具：`out/dsc/` 放了主缓存头、`.map`、子缓存 `.01`（SkyLight/CoreDisplay 等）和 `.03`（IOMobileFramebuffer.framework、QuartzCore 等），都是从 `artifacts/27.0.1/systemos.img` 用 `7z e` 单独取的（磁盘紧，用完可删）。`scripts/dsc-xref.py`（找 adrp+add/ldr 引用）、`scripts/dsc-disasm.py`（带字符串/库注解的反汇编）。共享缓存的符号在 1.6 GB 的 `.79.dyldlinkedit` 里，没取。
- `AppleDisplayManager` 查询来自**用户态 IOMobileFramebuffer.framework**（0x18fefe224：IOServiceMatching("AppleDisplayManager") → 找不到打印 "Didn't find ADM service" 返回错误），vma2 的 KC 里也没有这个类，不是阻塞点。
- `iomfb_populate_all_display_infos`（0x18ff0b3xx..0x18ff0b7f0）：遍历 `IORegistryEntryFromPath("/arm-io")` 的子节点，`compatible` 等于硬编码的 **`paravirtualizedgraphics,gpu`** 时，`IOServiceGetMatchingServices(IOServiceMatching("AppleParavirtGPU"))`，把每个服务的 **`DisplayPortCount`**（32 位数）累加成期望帧缓冲数；期望 > 已枚举时起 `iomfb_populate_thread` 注册 `IOMobileFramebuffer` 匹配通知并等待（runloop 30 s，超时打印 "Timeout: expect: %d current: %d"）。
- 我们的 ADT 没有这种节点 → 期望 0 → 不等待、也不注册通知，与 iokit-log 看到的“查完 ADM 后再无任何 IOKit 匹配”一致。WindowServer 之后大概率是在零显示器状态下空等（待 `sample-name=WindowServer` 确认）。
- **方案**：照 vma2 的发现链：ADT `/arm-io` 加一个 compatible `paravirtualizedgraphics,gpu` 的节点；一个类名就叫 `AppleParavirtGPU`（KC 里不放 Apple 的 AppleParavirtGPUIOGPUFamily，不冲突）、带 `DisplayPortCount=1` 的服务；再由它（或独立）发布 DroidVMDisplay（IOMobileFramebufferLegacy 子类）。注意 compatible 一样可能让别的用户态组件（Metal/IOGPU、VideoToolbox）以为是 PVG，后面要留意。
- 内核诊断新增 `sample-name=<进程名>`（每个周期按名字找进程采样，补丁 0008）。下次上机加 `sample-name=WindowServer sample-period=30`，确认它的等待点。

### IOFramebuffer 路线（2026-10-24 静态核实；**只作备用**，主路线是 IOMFB）
- CoreDisplay（arm64e）`CGXDisplayDriverInitialize`（0x18352b9a4）**无条件**调 `CGXMappedDisplayStart`（0x1834fdda0，内联 GPUController）：`useGPUWrangler`（偏好，标志 0x1e44c4e88，由 InitializeUserDefaults 读）为真时先走 GPUWrangler，"System has no accelerator" 不致命，找不到 MappedDisplay 就打印 "GPUWrangler is disabled due to no MappedDisplay" 清标志；然后 `IOServiceGetMatchingServices("IOFramebuffer")` 逐个 `IOFramebufferOpen`。即 arm64 的 WindowServer 会枚举并打开 IOFramebuffer。
- kc265 的 `com.apple.iokit.IOGraphicsFamily`（CFBundleVersion 600，依赖 IOPCIFamily）是完整 arm64e 实现（`IOFramebuffer::open` 5.5 KB、`IOFramebufferUserClient`、`IODisplayWrangler`、**`IOBootFramebuffer`**）。开源 apple-oss-distributions/IOGraphics 标签 IOGraphics-600 与之同版本（源码的 `#ifdef TARGET_CPU_X86_64` 在 arm64 上也成立，因为宏定义为 0）。
- `IOBootFramebuffer`：probe 只要 provider 有 `AAPL,boot-display` 属性且 `getConsoleInfo` 的 `v_baseAddr != 0`（arm64e 反汇编与源码一致）；模式/像素信息/aperture 全来自 `PE_state.video`。DarwinBoot 已给 boot_args Video：base 0x13FC00000（物理）、1280x800、row 5120、32 bpp、display=1。kc265 里没有它的 personality（x86 在 IONDRVSupport），需要自己加。
- 最小方案（零 C++）：ADT `/arm-io` 加节点（compatible 如 `droidvm,framebuffer`，带 `AAPL,boot-display`）；personality `IOClass IOBootFramebuffer`、`IOProviderClass IOPlatformDevice`、`IONameMatch droidvm,framebuffer`、`CFBundleIdentifier com.apple.iokit.IOGraphicsFamily`；keep 列表加 IOGraphicsFamily（会带上 IOPCIFamily）。
- 风险：① 非 x86 上 `kIOFBMapCacheMode = kIOMapInhibitCache`（IOFramebuffer.cpp:105），显存映射是 Device 内存，用户态非对齐 memcpy 会对齐错误 → 届时改成自写 IOFramebuffer 子类（RAM 影子缓冲 + 内核定时拷到 GOP）。② Apple 在 arm64 上没实际跑过这条路，可能有别的 arm 特有问题。③ 无 VBL 中断；Metal/合成需要加速器是两条路线共有的问题，不是这条路的额外代价。
- 已实现（未上机）：`overlay/kext/DroidVMFramebuffer.json` 是无代码 bundle（kc-build 新支持：native 描述没有 `objects` 就只写 plist 条目），personality 见上；`scripts/run-macos-vm.py` 的 make_adt 在 MACOS_KERNEL 下给 ADT 加 `/arm-io/framebuffer`（compatible `droidvm,framebuffer`，`AAPL,boot-display`=1）；都只在 `MACOS_IOFB=1` 时生效（ADT 节点在 register/prepare 时、bundle 在 kc-try 时），默认不加。离线建 KC 通过：保留 20 个 kext（多了 IOGraphicsFamily、IOPCIFamily），plist 里有无代码条目。
- 用它时要看：ioreg 里 `IOBootFramebuffer` 挂在 `/arm-io/framebuffer` 下并且 start 成功；`IODisplayWrangler`、`IODisplayConnect`/`AppleDisplay` 出现；WindowServer 日志里的 "MappedDisplay Driver"/"IOFramebufferOpen failed"/"GPUWrangler is disabled"；有无 WindowServer 对齐错误（Device 内存，风险①）。

## 上机 run 3-5（2026-10-24 晚）
- run 3/4：WindowServer 未启动。根因是基线（UniXNU 合并）里 4K 内核拼 16K slide 页的代码：持有源页及 copy 对象里的 top_page 占位页时去 fault 同窗口邻页，两个 fault 落在同一 16K 窗口即 ABBA 死锁（logd 等 0x433d000、另一线程等 0x433f000）；xpcproxy 的 `auth_remap → copy_delayed` 随后永等 paging，后续 exec 全排在 `vm_shared_region_start_address`。修复=补丁 0008（先拷贝并释放源页再读邻页）。
- `DroidVMGpuStarter` 类分配失败：kc_native 每个目标文件各出一个 `__mod_init_func`，OSRuntimeInitializeCPP 只跑第一个。已改为同名节合并（提交 1edf517），run 4 起 GPU self-test 通过、published。
- run 5：WindowServer（pid 115）起来并常驻（主线程 mach_msg2_trap，slide 0x14908000），iokit-log 只有 IOHIDSystem + AppleDisplayManager 三条，没有查 AppleParavirtGPU；DroidVMDisplay 无 swap 日志。下一步：确认 WindowServer 为何没走 iomfb_populate_all_display_infos（sc-trace=WindowServer，或读其用户栈）。

## 上机 run 9-18（2026-10-24）
- run 9/11 的 `ArmCpu: IRQ drain exceeds 128` 是板级 `armcpu-diagnostics=1` 的诊断断言，macOS 内核默认 drop。
- WindowServer 卡主线程的整条链：无网卡 → `IOTimeSyncClockManager::findTimeSyncTimeClockID`（start 时一次性 `getMatchingServices(IOEthernetInterface)`，优先 IOBuiltin）断言 → 不 registerService → clocksyncd 等 FirstMatch 不回 XPC → QuartzCore `TSDClockManager.shared` 同步 XPC 卡死。
- 修：`overlay/kext/DroidVMEthernet`（en0，MAC 02:44:56:4d:00:01，IOBuiltin=true，同步 registerService 后 publishResource("DroidVMEthernet")），KC 用 `patch_personalities` 给 IOTimeSyncRootService 加 `IOResourceMatch DroidVMEthernet`。不能早于 IOBSD 匹配（ifnet 分配会卡住整个 IOKit 匹配，根盘都等不到）。头文件要 `__PRIVATE_SPI__`（26.5 的 IONetworkController 用了保留槽 2-5）。
- kc-build 坑：stand_in() 曾把“重映射到新内核的指针”误当作指向被替身 kext 的指针（新内核地址与旧 kext 平移后的区间重叠）→ `stand-ins lack`；而 kc-try 的管道吞了退出码，静默启动旧 KC（run 15 白跑）。两处都已修。
- run 18：`Using interface IOEthernetInterface en0`，clocksyncd 正常，WindowServer `open DroidVMDisplay` 两次、map_display_type 成功；随后 SkyLight abort：**"No suitable Metal devices present after 30 seconds."**（SkyLight+0x2286e4）。下一步就是第 2 步 Metal 设备发现/插件。

## Metal 发现链（2026-10-24，run 19-25，已上机验证）
- macOS 27 的链：Metal.framework 监听 `IOServiceMatching("IOAccelerator")` → IOGPU `+[IOGPUMetalDevice registerAcceleratorService:]` 读 `MetalPluginName` → libsystem_sandbox `gpu_bundle_find_trusted` 依次找 `/Library/GPUBundles/<名>.bundle`、`/System/Library/Extensions/<名>.bundle`（第三项仅内部版），要求是目录且 `rootless_check_trusted_class(path,"KernelExtensionManagement")`（lp-sip0=0x2 时 csr_check 放行）→ `[NSBundle bundleWithPath:]`（macOS 布局 Contents/MacOS、Contents/Info.plist）→ 取 `MetalPluginClassName` 的类，**必须是 IOGPUMetalDevice 子类**，否则静默放弃 → `[[cls alloc] initWithAcceleratorPort:port]` → `MTLAddDevice`。失败都只进 os_log/NSLog，stderr 看不到。
- 内核：DroidVMGpu 的 `AGXAccelerator : IOAccelerator`（IOGraphicsFamily，272 槽），personality 挂在 `NativeAdrenoGpuPublished` 上，open 转 `native_adreno_new_user_client`。
- 用户态工具链：llvm-21 clang 编 arm64e；链接只能用 Darling 里的 Apple ld-classic（`scripts/apple-ld.py`；cctools ld64-711 无 TAPI、ld64.lld 不支持 arm64e auth 重定位、ld-prime 要新 libc++）。IOGPU 私有框架用 `overlay/metal/frameworks/IOGPU.framework/IOGPU.tbd` 桩按库链接（`-U` 走 flat lookup 在 IOGPU 未加载的进程里失败）。
- 部署：`scripts/stage-gpu-plugin.py`（Data 种子 `.data/Library/GPUBundles` + owner trust 模块），启动时 `MACOS_DATA_SEED`/`MACOS_TRUSTCACHE`；`--probe` 加 launchd 任务 metal-probe（dlopen + MTLCopyAllDevices，stderr-log 可见）。`scripts/build-metal-probe.sh` 一键。
- run 25 结果：WindowServer `loaded` → `initWithAcceleratorPort:` → 'AG' open 返回 0。
- 诊断：`sc-trace=<进程>`（失败 syscall 带路径；`sc-trace-all=1` 全部，fcntl/mmap 等噪声调用被跳过）；`~/gotmp/ipsw dyld disass … --cache out/dsc/27.a2s`（符号缓存 1.6 GB，/tmp 放不下）。
- 下一步：真插件 = NativeMetal 前端（UniXNU drivers/NativeMetal，基类从 _MTLDevice 换成 IOGPUMetalDevice、init 不走父类的 IOGPU 打开）+ metal2vulkan（Rust，arm64e-apple-darwin 是 tier 3，要 nightly build-std）+ turnip（Mesa darwin KMD，pin 85fda3b3 + patches/mesa）。磁盘只剩约 3 GB，Mesa/Rust 构建前要腾空间。
