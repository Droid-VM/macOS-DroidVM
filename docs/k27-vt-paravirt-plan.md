# k27 硬件视频编解码：VideoToolbox 半虚拟化移植方案（2026-11-02）

## 来源

上游 Droid-VM/UniXNU-droidvm wip/hackintosh 在 iPadOS 27 上已跑通（3df7c94、1479852、9d5a0ce、fab4fb1）：

- VideoToolbox 自带半虚拟化解码器/编码器（ParavirtualizedVideoDecoder/Encoder）。
  VideoToolboxParavirtualizationSupport.framework 一旦打开 `AppleVideoToolboxParavirtualizationDriver` 服务就会走这条路。
  guest 用户态零改动。
- guest 内核扮演"宿主"一侧：
  - `package/DroidVMVTParavirt.cpp`：传输层，用 Apple 的类名。
  - `package/DroidVMVTHost.cpp`：会话。解码 decs/+dec/dset/dsta/dfrm/Dbuf/Demt/dfin，编码 encs/esta/efrm/Eemt/ecfr。
  - `package/DroidVMVTWire.h`：协议格式，'vtpv' 48 字节原子 + 'para' 参数。
  - 会话跑在 crosvm 的 virtio-media 解码器/编码器上：`package/DroidVMVirtioMedia.c`，走 virtio-mmio，`/arm-io/virtio-media-N`，带 media-host-pool。
- 宿主端是手机的 MediaCodec（c2.qti.avc/hevc）。
- 上游实测（720p）：
  - H.264 解码 135–151 fps，HEVC 解码 159–170 fps；
  - H.264 编码 204 fps，HEVC 编码 292 fps；
  - UsingHardwareAccelerated* 报 1。
- 开关：`droidvm-vt-paravirt=1` 或 `kern.droidvm_vt_paravirt=1`。

## 前提核对（11-02）

- [x] macOS 27 的共享缓存有 VideoToolboxParavirtualizationSupport.framework（71.0.14），打开的服务名同为 `AppleVideoToolboxParavirtualizationDriver`。
  VTParavirtualizationGuestSupportSetUpWithHandlers 等 guest 侧符号都在。
  - 查法：`sudo mount -t apfs -o ro,loop artifacts/27.0.1/systemos.img /tmp/sysos`
  - 再 `ipsw dyld str /tmp/sysos/System/Library/dyld/dyld_shared_cache_arm64e NAME`
  - out/dsc 的 .02 分片是指向已删 /tmp 的坏链接。
- [ ] 宿主 crosvm：手机上 `usr/bin/crosvm`（11-01 22:31）没有 `--virtio-mmio-media`，也没有 `--pre-alloc media-host-mb`。
  - Droid-VM/crosvm 的 wip/hackintosh 有（d5c13c494），外加约 20 个 media 修复（解码顺序、输出槽位、编码暂存等）。
  - 本地 external/crosvm 在 wip/macos-virtio-gpu（18bac4592）。比上游多 23 个提交，其中 10 个上游已有等价补丁，13 个独有：KMS 接管、Windows 输入、EDID、栅栏隔离、half-float 扫描输出等。
  - 上游比本地多 99 个提交。试合并有 5 个文件冲突：input/mod.rs、cmdline.rs、config.rs、sys/linux.rs、sys/linux/gpu.rs。
  - 工作区另有 17 个文件未提交（+660/−795，含 simplefb_display.rs、Android.bp、Cargo.toml），来源未明，不能动。
- [x] App：vms.json 有 `vpu_enabled` / `vpu_guest_pool_mb` / `vpu_host_pool_mb`，三台 VM 当前都是 false。
  MediaCodec 辅助进程由 App 提供（Linux guest 已在用，见 meta-repo wip/vpu）。

## 进度（11-02）

- P0–P2 完成：crosvm rebase + --pre-alloc 合并（e3ce85e38）；droidvm-app.py media + ADT media 节点；DroidVMVideo kext（macOS 10efcda）。
- P3：720p H.264/HEVC 编码与解码都已通，VT 报硬件；壁纸未做。详见 k27/TODO.md。
- 与原方案的出入：
  - 不用 App 的 vpu_enabled（它不生成参数），改为 extra_options。
  - macOS 的 IOSurfaceRoot 服务名是类名，不是 IOCoreSurfaceRoot。
  - 上游内置的 64x64 测试流低于 c2.qti 的最小尺寸 96x96。

## 阶段

- **P0 宿主 crosvm**：在新分支上把 droidvm/wip/hackintosh 合进 wip/macos-virtio-gpu，解 5 个冲突，编译后部署。
  - 部署用同目录 rename，并备份旧 crosvm。
  - 先确认未提交的那 17 个文件是谁的、手机上的 11-01 版是不是含了它们。
  - 换 crosvm 影响所有 VM，Windows VM 需要回归。
- **P1 VM 配置与 ADT**：
  - macOS VM 打开 `vpu_enabled`。
  - extra_options 加 `--virtio-mmio-media`（crosvm 把它放在声卡之后；macOS VM 无声卡，所以在 net/gpu 之后，窗口顺序要核对）。
  - run-macos-vm.py 的 make_adt 加 `/arm-io/virtio-media-N` 节点和 media-host-pool，参照上游 make-droidvm-adt.py 的 `--media-mmio`。
  - 重导 FDT。
- **P2 guest kext**：参照 k27/build-native-display.sh 导出上游源码的做法，把四个文件编成 native kext：
  - DroidVMVirtioMedia.c
  - DroidVMVTParavirt.cpp
  - DroidVMVTHost.cpp
  - DroidVMVTWire.h

  macOS 上的差异要逐个核对：
  - IOSurfaceRootUserClient 的选择子和锁结果布局。上游按 iPadOS 27 的 IOSurface.framework 偏移读，macOS 27 要重新核对。
  - 解码进程：macOS 是 VTDecoderXPCService，iPadOS 是 videocodecd。注意：对 VTDecoderXPCService 跑 spindump 会让 guest panic。
  - 沙箱：用 Apple 类名能否被 macOS 的 VTDecoderXPCService 配置文件放行。
  - macOS 原生的 AppleVideoToolboxParavirtualizationDriver kext 是否在 KC 里，会不会抢匹配。
- **P3 验证**：
  - 探针：macOS 版 vtdecode/vtencode，可借用上游 gfxprobe 或自写 metal-probe 任务。
  - 然后是锁屏航拍壁纸：4K HEVC Main10，要看手机 c2 解码器对 10-bit 的支持。
  - 最后回到推迟的壁纸抽动问题。

## 壁纸纹理：着色器直接读 YCbCr 平面（11-03 定）

问题：锁屏航拍壁纸的 4K 视频帧（x420，格式 505/543）在 WindowServer 里由插件 CPU 转换成 RGBA 副本，每个视频池 surface 一份 40 MiB，
共约 1.2 GB GPU 内存，把 guest 内存挤空，DroidVMVideo 的硬件会话因此分配失败、退回软件解码，壁纸抽。

现状（metal2vulkan 上游）：
- PlanesInPlace（texture/ycbcr_image.rs、ycbcr.rs「Planes read in place」）：集成 GPU 上，格式 500/505 的纹理在 plane 0、无 swizzle 时，
  只 sample（nearest/linear，无比较/各向异性/min_lod_clamp）或读尺寸的槽绑定 uniform texel buffer 直读平面，着色器按 Metal 算法转换与滤波，精确。
  设备线性平铺支持 sampler YCbCr 时还能走 ycbcr_planes.rs 的设备转换。
- 但 new_converted_texture 总是调用 converted_storage：建 RGBA16F 转换图 + ShadowSource::Converted 的平面暂存（4K 约 100 MB），
  原地读的槽并不需要它们。WindowServer 每帧新建纹理，于是插件拒 >1 Mpx 并改 CPU 转换（NativeMetal a9531ab/97cec24）。

步骤：
1. metal2vulkan：转换图与暂存改为按需。只有 read/gather/渲染/不满足原地条件的槽第一次用到时才分配；纯原地读的纹理零分配。
   以 patches/metal2vulkan 新补丁提交（check-metal2vulkan-pin.py 校验）。
2. 插件：格式 500/505 撤掉 >1 Mpx 拒绝和 CPU 转换（convertedYCbCrTexture），交给运行时；503/543 等暂留 CPU 转换兜底，后续扩展原地读格式。
3. 验证：m2vsim 宿主模拟（4K x420 采样正确性、GPU 时间）；上机看 WorkCounts（ycbcr_textures_in_place、ycbcr_images_kept_*）、
   WindowServer 的 droidvm_virtgpu_client_memory、VTHost 会话是否建得起来、锁屏是否还抽。

风险：CoreAnimation 着色器对这些槽若有 read/gather，仍会走转换图（步骤 3 实测）；20×20 MiB 的块来源待查。

## 风险

- 壁纸是 4096x2160 HEVC Main10，240 fps 码流。上游只测过 720p 8-bit，10-bit 输出格式（P010）和 4K 的拷贝开销都是未知数。
- 内核侧要把解码帧拷进 guest 的 IOSurface（NV12）。4K 每帧 12 MiB，60 fps 时约 0.75 GB/s 的 guest 内存拷贝。
