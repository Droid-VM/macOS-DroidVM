# k27 GPU 驱动 CPU 拷贝审计（2026-11-05）

范围：macOS 27 guest 的 GPU 栈
- 显示 kext：`overlay/kext/DroidVMDisplay/DroidVMDisplay.cpp`
- virtio-gpu 传输层与 3D：`out/k27/src/DroidVMVirtioGpu/`（UniXNU-droidvm `59ec0a8` + `patches/droidvm-display`）
- 加速器 user client：`sources/UniXNU/drivers/NativeAdreno/NativeAdrenoPublish.cpp`（+ `patches/droidvm-gpu/NativeAdreno`）
- Turnip：`sources/UniXNU-turnip/.cache/mesa-work/src/freedreno/vulkan/`（`tu_knl_darwin*.cc`）
- Metal 前端：`sources/UniXNU/drivers/NativeMetal/NativeBridgeMetalFrontend.mm`（行号是源文件的，构建时 `build-metal-plugin.sh` L29-87 会插行）
- metal2vulkan：`sources/UniXNU/.cache/gpu-reference/metal2vulkan`（+ NativeMetal `bridge/patches` 0001-0024 除 0020、板级 0011-0022、`metal2vulkan-macos/0001`）
- 宿主上屏：`external/crosvm/devices/src/virtio/gpu/virtio_gpu.rs`

方法：静态读代码，无上机测量。

## 结论

常态每帧路径基本没有大块 CPU 拷贝。剩余的 CPU 开销集中在少数几处，其中前两项有低成本的消除手段。

## 已经是零拷贝的部分

| 环节 | 机制 | 位置 |
|---|---|---|
| 上屏 | BGRA / RGhA 的 IOSurface 页做成 `VIRTIO_GPU_BLOB_MEM_GUEST` blob（guest handle），`SET_SCANOUT_BLOB` + 不带 fence 的 `RESOURCE_FLUSH`；guest 内无拷贝 | `DroidVMDisplay.cpp:824-930` |
| 宿主上屏 | 宿主把 blob 页做成 udmabuf，导入后 Vulkan blit 到 Android 窗口（GPU 拷贝，非 CPU）；导入失败才回退到 `flush_staging` CPU 拷贝 | `virtio_gpu.rs:640-760`、`1058-1120`；`gpu_display_android.rs:391` |
| 命令流 / BO | Turnip 直接写 `bo->map`；BO 是调用进程的 guest 页（`makeTaskPages`），物理段列表交宿主导入成 GEM，GPU 直接读；CPU 映射 write-back，GEM_NEW 带 `CACHED_COHERENT` | `tu_knl_darwin_virtgpu.cc:404-414`；`DroidVMVirtioGpu3D.cpp:526-536, 649-693` |
| IOSurface 导入 | 前端 `surfaceBuffer` → `nmb_buffer_new_no_copy_releasing` → `VkImportMemoryHostPointerInfoEXT` → Turnip `CREATE_BLOB_USER` 固定调用者页；纹理以 `InPlaceWrites` 建在页上（线性 VkImage） | 前端 1299-1324、4532-4555；`memory.rs:1720/2113`；`tu_knl_darwin.cc:935-980` |
| 4:2:0 视频 500/505 plane 0 | WindowServer 里着色器直接读平面（`METAL2VULKAN_YCBCR_PLANES_ONLY=1`） | `metal2vulkan-macos/0001`；`overlay/metal/NativeAdrenoMetalPlugin.mm:332-333` |
| Managed 资源 | 统一内存，无镜像；`didModifyRange` / `synchronizeResource` 空操作 | `managed.rs`；前端 1211、3083 |
| 呈现 | `presentDrawable` 只在完成回调里 `[drawable present]` | 前端 3462-3464 |

### 每次提交的小块拷贝链（<1 KiB，开销在往返不在字节）

1. `tu_cs_entry` → `NativeAdrenoAbiSubmitBuffer`（24 B/IB，`tu_knl_darwin.cc:1168-1176`）
2. → `NativeAdrenoAbiSubmit`（416 B，:1364-1368）
3. → 栈上 ccmd 804 B、压缩、加 execbuffer 头（`tu_knl_darwin_virtgpu.cc:433-476`）
4. → `vg_call` 加隧道头（:137-139；>512 B 时 malloc/free）
5. → `IOConnectCallStructMethod` inline copyin（≤828 B，永远 <4096，不走 OOL）
6. → 内核 `post()` memcpy 进 16 KiB 小槽（`DroidVMVirtioGpu.cpp:281`）+ 清 response（:286）
7. → `wr(0x50,0)` 通知（MMIO，一次 VM exit）

每次最多 16 个 IB；按一帧约 107 个 IB 估算是 7 次往返。热点是调用次数。OOL 路径（`NativeAdrenoPublish.cpp:532-545` 的 `readBytes`，`hugeRequest` 1 MiB）这版 Turnip 不会触发。

## 仍存在的 CPU 拷贝 / CPU 开销（按影响排序）

### 1. 每次提交与完成的整块 surface cache 刷新 —— 大概率可去掉

- 位置：前端 `flushSurfaces` 1530-1544，调用点 3563（`-submit`）、3499（`-finish`）；开关 1523-1527。
- 内容：对每个绑定过的 IOSurface 的 `IOSurfaceGetAllocSize` 整个范围调用 `sys_dcache_flush`；还要先 `IOSurfaceGetBaseAddress`（首次映射）和排序。
- 量级：每次 commit 一次、每次完成再一次；1080p RGhA 约 16 MB/张，渲染目标与采样 surface 都算。
- 现状：iOS 构建已关（注释：iPadOS 27 上 `sys_dcache_flush` 只是 `dsb ish; ret`，内核已保证导入一致性）；macOS 构建 `kSurfaceFlush=true` 仍开。
- 能否消除：BO 是 write-back + 宿主 IO-coherent 导入，CPU 侧不需要维护。验证：guest 建 `/private/var/ngpu/debug/no-surface-flush`，A/B 拖动帧率与遥测 `J surface cache n=… bytes=… us=`，确认无花屏/残影后把 macOS 的 `kSurfaceFlush` 也设 false。
- 未定：macOS 27 arm64 的 `sys_dcache_flush` 是否逐行 DC CIVAC 需实测。

### 2. 非 500/505 的大 YCbCr 纹理 CPU 转换 —— 可消除

- 位置：前端 `convertYCbCr` 766-793、`convertedYCbCrTexture` 794-872，入口 4539；`refreshConvertedYCbCr` 874-884（每次 `texture:index:stage:` 绑定都调用，2622）。
- 条件：仅 WindowServer；2 平面、plane 0、>1 Mpx、usage 只含 ShaderRead/PixelFormatView。500/505 已被 H3 接走，剩 502/503/506/507/520-523/540-545（例如登录窗口 `444f`=503、`x420` RGB10_420_2P=543）。
- 量级（4K）：读 Y 8.8 MB + CbCr 4.4 MB（4:4:4 为 26.5 MB，10-bit 翻倍），写 35 MB 中间 `std::vector`，再 `replaceRegion` 35 MB；后者进 Turnip `tu_CopyMemoryToImageEXT` → `fdl6_memcpy_linear_to_tiled`（`tu_clear_blit.cc:2805/2822`）又是一次 CPU 线性→分块。每次内容变化（seed/`lumaSum` 变）一次；每次绑定还要抽样读 `lumaSum`（758-764）。
- 存在原因：runtime 自带 YCbCr 纹理每张约 100 MiB（RGBA16F + staging），4K 壁纸会把 4 GiB guest 推进 jetsam（注释 738-751）。
- 能否消除：把"着色器直接读平面"从 500/505 扩展到 4:2:2/4:4:4 与 10-bit 543 等（改采样坐标与位宽）。目前日志未见 `converted to a`，先确认真实负载再做。
- 非 WindowServer 进程里 543 会被直接拒绝（`dmesg-now3.txt`：`WallpaperAerialsExtension: surface texture refused: 4096x2160 YCbCr format 543 converts on the CPU`）。
- 备注：`build-metal-plugin.sh` L30 注释说"runtime 在 CPU 上转换"与代码不符，runtime `ycbcr.rs` 是 `vkCmdCopyBuffer` + compute。

### 3. 显示 kext stage-1 CPU 拷贝 —— b3a8 可消除，其余是容错

- 位置：`DroidVMDisplay.cpp:932 copySurface`（逐行 memcpy 读 → 查表转换 → memcpy 写 GOP framebuffer）。
- 量级：1080p RGhA 实测 54 ms/帧（读 33.8 ms、转换 19.9 ms）；无新 swap 时还会在 `kRefreshTicks` 的若干 tick 上重拷。
- 触发：格式 `b3a8`（`scanOut` 只认 BGRA/RGhA，:889-891）、无 virtio-gpu、扫描连续失败 8 次（:916）。
- 现状：WindowServer 用 RGhA，日志 9950 次 swap 仅 1 次 CPU copy。
- 能否消除：b3a8 可让宿主支持该格式，或 guest 只扫描颜色平面（10-bit BGR，plane 0）。其余两种保留作兜底。

### 4. 新 BO 清零

- 内核 `makeTaskPages`（`DroidVMVirtioGpu3D.cpp:526-536`）首次触碰按页清零；回退路径 `guestPages` 显式 `bzero`（:457/471/506）。每次 BO 缓存未命中一次，整个 BO 大小。安全要求，不能去。
- 物理段列表 16 B/段（pageable 页基本每页一段，约 BO 大小的 0.4%，21 MiB ≈ 87 KiB），超过 16 KiB 走大槽/`hugeRequest`。可通过分配更连续的页减少。
- 用户态 `tu_knl_darwin.cc:846-847`：缓存命中且 `TU_BO_ALLOC_INTERNAL_RESOURCE` 时 `memset` 整个 BO。可改 GPU 填充，收益小。
- **正确性问题**：缓存复用给应用内存时不清零（:845 注释），但驱动声明了 `zeroInitializeDeviceMemory`（`tu_device.cc:417/918`），两者矛盾。

### 5. VK_EXT_host_image_copy（API 语义，不能消除）

- `tu_clear_blit.cc:2749-2816 / ~2988-3050 / 3365-3500`：`replaceRegion` / `getBytes`（如 Core Image 读回，`tu_knl_darwin_virtgpu.cc:555-558`）时 CPU 线性↔分块互转，整区域（2048×2732×4 ≈ 22 MiB）。
- 可选优化：大图改走 staging + GPU 拷贝；不走 host-copy 时 runtime 已有此回退（`texture.rs:5507-5570`，有时同步等提交）。

### 6. 页导入失败兜底（容错）

- `buffer_descriptor.rs:523-557` + `copied.rs:122,187-195`：每次 commit 整块比较拷入、每批完成后 merge back，O(bytes)。只在导入失败（OOM/Vulkan 错误）时触发；日志未见 `copied-host-pages`。

### 7. setBytes 双拷（量小，不值得做）

- 前端 2671-2677 开 encode thread 时先拷进 `std::vector`（WindowServer 强制开），再 `argument_table.rs:769-810` → `upload.rs:234` 拷进 upload arena。≤4 KiB/次。

### 其余小块 / 一次性 / 条件性

| 位置 | 内容 | 说明 |
|---|---|---|
| 前端 `newBufferWithBytes` 4502-4507 → `buffer_descriptor.rs:409-436` | 拷进映射内存或 staging | API 语义，一次性 |
| 前端 `replaceRegion` 1477-1505 / `getBytes` 1506-1513 → `texture.rs:5405/5585` | 按行 memcpy 或 host image copy | API 语义 |
| 前端 PVRTC 1357-1403、1493-1502、3049-3054 | CPU 解码成 RGBA8 | Adreno 无 PVRTC，仅 PVRTC 内容 |
| 前端 `newTextureWithBytesNoCopy` 4474-4489 → 4161-4197 | 名义 NoCopy，实为逐 level replaceRegion | 块压缩格式，一次性 |
| `two_planes.rs:191-213` | 2 平面 XR 纹理 replace/getBytes 拆并 texel | 条件性 |
| `decoded_twin.rs`、`pvrtc.rs`、`astc.rs` | 不可采样格式的 CPU 解码孪生纹理 | Adreno 原生 ETC2/ASTC LDR/BC，基本不触发 |
| `host_shadow.rs` | MoltenVK 缺陷用 | Turnip 不走 |
| ICB / indirect（`indirect_command_buffer.rs` 等） | CPU 搬运或读回 | 条件性，小 |
| `tu_cmd_buffer.cc`、`tu_descriptor_set.cc`、`tu_shader.cc:2913`、`tu_clear_blit.cc:3674` | 描述符、shader 上传、`vkCmdUpdateBuffer` | 上游固有，小 |
| 前端诊断 `dumpSurfacesOnce`（~2163）、3233、3269 | dump surface | 默认关 |
| `HostMetalCommandServer.mm`、`OfflineMetal*`、`GpuScanoutPresenter.h` | 跨进程序列化 / iOS 扫描 | 未编进本构建 |

## GPU 拷贝（不占 CPU，占带宽）

- **影子纹理**（`shadow.rs`）：行距非 64 字节倍数（`Pitch`）、tile store 越过行尾、平面行共享字节、旋转纹理（板级 0011 用 2D 引擎）、`b3a8` 两平面 XR。每 pass/encoder copy in/out。实际情况看 `<cache>/m2v/shadow.log`。
- **runtime YCbCr**（`ycbcr.rs:911/938/1191/1208/1254`）：≤1 Mpx、非 WindowServer 或 usage 有其他位的 YCbCr 纹理；每张 4K 约 100 MiB。
- **replaceRegion staging→image**（`texture.rs:5507-5570`），**两平面 buffer↔image**（`two_planes.rs:509/540/857`、`ycbcr_device.rs:853`）。

## 建议顺序

1. guest 建 `no-surface-flush`，A/B 拖动帧率与 `J surface cache` 耗时；无回归就关掉 macOS 的 `kSurfaceFlush`。代价最低、最可能有收益。
2. 日志 grep `converted to a`、`surface texture refused`、`shadow.log`、`virtio-gpu scanout of format`、`copying from now on`、`copied-host-pages`，确认第 2、3 项和影子纹理是否真实出现，再决定是否扩展原地读平面的格式。
3. 提交路径不必再压字节；值得做的是减少往返（每次最多 16 个 IB，一帧约 7 次）。这不属于拷贝问题。
4. 修 `zeroInitializeDeviceMemory` 与缓存复用不清零的矛盾。

## 运行时核对信号

- 日志：`converted to a … texture for format N`、`surface texture refused: … converts on the CPU`、`read in place`、`copied-host-pages`、`virtio-gpu scanout of format`、`copying from now on`、`copies mean`
- 遥测：`J surface cache … bytes= us=`、`TB`（未对齐纹理影子）、`N no-copy … surface …`
- 文件：`<cache>/m2v/shadow.log`

## 未核实

- 宿主 virglrenderer / drm2kgsl 内部是否再拷贝；宿主是否真以 IO-coherent 导入（只有 guest 侧注释）。
- 内核处理 `CREATE_BLOB_USER` 的源码不在本地源码树里，"内核侧零拷贝"凭 ABI 注释（`DroidVMVirtgpuABI.h:65-71`）。
- macOS 27 上 `sys_dcache_flush` 的实际行为。
- `.cache/mesa-work` 未打 `turnip-gmem-mutable-swap`、`turnip-render-mode-for-attachment-memory`；`mesa-macos/0001-0002` 构建时临时打、结束时撤回（只改日志和 service 名，不涉及拷贝）。
