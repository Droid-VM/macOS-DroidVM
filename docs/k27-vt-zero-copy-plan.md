# k27 视频解码零拷贝方案（2026-11-03）

> **状态（11-04 晚）**：P0–P3 完成并已提交（crosvm b7960bae6、virtio-media d509294、macos 2f7c955/b6cc61b），锁屏航拍有画面（用户确认）。
> 现在解码段是 0 次 CPU 拷贝：msm_vidc 经 udmabuf 直写播放器的 IOSurface，kext 原样交出，丢弃帧不拷贝；码流只有几次 KB 级小拷贝。
> 显示段也已是零拷贝：P4 原型（WindowServer 原地读平面，macos 3623549）**11-04 晚核实已生效**——航拍播放时 WindowServer 没有任何
> 32–64 MiB 的 RGB 转换副本（11-03 CPU 转换时有 19×40 MiB），而是把 26.7 MB 的 P010 池 surface 直接导入成 GPU 纹理（41 块 16–32 MiB 用户块）。另外 P3 能工作还靠 0011 的 Apple vtpv 语义
> （解码顺序 + 同步 dfrm 等 Demt），见 k27-vt-p3-status.md。

## 为什么做

锁屏航拍壁纸（4K HEVC Main10，240 fps 码流）走 DroidVMVideo 硬解时，CPU 拷贝太多，宿主和 guest 内存都被吃满：
- 11-03 实测：两路 4K 会话一启动，宿主 dmabuf 3 秒内涨 2–3 GB，MemAvailable 跌到 1.5 GB，lmkd 开始杀桌面。
- 拷贝和内存账，按一帧画面经过的路径（每帧 4096×2160）：

| 位置 | 做什么 | 代价 |
|---|---|---|
| 宿主 c2.qti | 内部 UBWC TP10 参考帧（17.9 MB/块）转出一份线性 NV12（13 MB/块，CCodec 槽数 = output delay 22 + 4） | 每路约 340 MB 线性块 + 参考帧 |
| 宿主 crosvm | 把线性 NV12 逐行拷进 guest 的 CAPTURE 缓冲（android.rs 出帧路径） | 每帧 13 MB CPU 拷贝，丢弃帧也拷 |
| 宿主 crosvm | 分散的 guest 页每次 QBUF 重新 mmap/munmap（已用映射复用缓解，见下） | v_media_worker 95% CPU，68% 在内核 VMA 操作 |
| guest kext | copyFrame 把 CAPTURE 缓冲拷进 IOSurface，8 位扩成 16 位（x420） | 每显示帧约 20 ms，26 MB 写入 |
| guest kext | 自己的 CAPTURE 缓冲（可换页，物理分散） | 约 6 × 13 MB |
| guest 插件 | 4K YCbCr 在 CPU 上转成 RGBA 副本（NativeMetal a9531ab） | 每个池 surface 40 MiB，共约 1.2 GB GPU 内存 |

另一个硬限制：手机 /vendor/etc/media_codecs_kera_v*.xml 里 c2.qti.hevc.decoder 声明
`performance-point-3840x2160 = 60`，4K 每秒最多解 60 帧。240 fps 码流逐帧解，无论拷贝多少都追不上。
11-03 单路实测 40.8 fps（映射复用之后），已接近这个上限。

## 已有的、可直接复用的东西

- **kext 已经说 V4L2**：DroidVMVTHost.cpp 用标准 stateful 解码流程（SOURCE_CHANGE → G_FMT → REQBUFS USERPTR → QBUF），
  CAPTURE 给的是 guest 物理页的 SG 列表。
- **crosvm 已能把 guest 页做成 dmabuf**：guest_buf.rs `GuestBufferImport::dmabuf()`（udmabuf，惰性建，"for a backend that
  can consume one"）。Windows VM 的 BO 已经用 udmabuf over guest RAM 走通（memory: win3d-bo-backing-guest-ram-udmabuf），
  显示零拷贝也走通过（kms-display-no-guest-changes，msm_prime 套 mem_buf ops）。
- **virtio-media 解码设备与后端分离**：video_decoder.rs 只认 `VideoDecoderBackend` trait，android_codec_backend 是其中一个实现。
  换后端不动设备、不动 guest 协议。
- **GPU 侧原地读平面已定方案**：k27-vt-paravirt-plan.md「壁纸纹理：着色器直接读 YCbCr 平面」（metal2vulkan PlanesInPlace，
  patches/metal2vulkan-macos/0001 是开关原型），着色器直接读 IOSurface 的平面，不再 CPU 转 RGBA。
- **外部先例**：Rungic PR #12（kevinzhow/Rungic）在同类高通手机上绕开 MediaCodec，直接用 msm_vidc V4L2（/dev/video32）解码：
  - CAPTURE 为导入的 DMA-BUF（来自 /dev/dma_heap/system），输出 NV12/P010，线性，msm_vidc 自己的布局；
  - 固件接受的顺序：OUTPUT 先 STREAMON，送一个 AU，等 SOURCE_CHANGE，再建 NV12/P010 的 CAPTURE；
  - 解出的帧留在解码器缓冲里，以 fd 交出，不拷贝；
  - 1080p H.264：82 → 239 fps；实时 1080p60 CPU 105%（MediaCodec 桥）→ 23%（V4L2）；MediaCodec 桥保留为后备。
- 手机上已核对：/dev/video32、/dev/video33 存在（system:camera 0660，u:object_r:video_device:s0）；/dev/udmabuf 0666。

## 候选方案（按成本从低到高）

### Z0 只减不改（不是零拷贝，但先做，任何方案都需要）
- **时间层跳帧**：240 fps 高帧率 HEVC 常按时间层编码，上层帧是 `_N` 型 NAL（TRAIL_N/TSA_N/STSA_N/RADL_N/RASL_N =
  子层非参考帧），不被同层或下层引用，可以不解直接丢。kext 已按 PTS 抽帧（0008），把“要丢的帧”里属于 `_N` 型的
  直接不送解码器、立即回 Demt+FrameDropped。若片子是这种结构，4K 解码量可降到显示需要的 30–60 fps，落进 60 fps 上限。
  先验证结构（P0），不是这种结构就没收益（只能整段送解）。
- 丢弃帧宿主不拷贝（MediaCodec 路线下 release_output 不填 CAPTURE）。

### Z1 宿主一次拷贝（MediaCodec 不动）
- kext 把 IOSurface 本身当 CAPTURE 缓冲 QBUF（预先用 Dbuf 向 guest 池要 surface），去掉 copyFrame 和 kext 自己的 CAPTURE 缓冲；
- crosvm 请求 P010 输出（10 位），P010 与 x420 布局一致（16 位，高 10 位有效），省掉 8→16 位扩展；按 IOSurface 的平面偏移写；
- crosvm 按段直写 guest RAM（helper 已映射整块 guest 内存），不建线性映射。
- 剩下：宿主每显示帧一次 CPU 拷贝 + c2 的线性块（每路约 340 MB）。改动：kext + crosvm。

### Z2 msm_vidc 直写 guest IOSurface（推荐，真零拷贝）
- crosvm 新增 `msm_vidc` 解码后端（实现 VideoDecoderBackend，用 virtio-media 已依赖的 v4l2r 访问 /dev/video32），
  android_codec_backend 留作后备（打不开设备、格式不支持、导入被拒时自动退回）。
- CAPTURE：guest 给的 IOSurface 页 → `GuestBufferImport::dmabuf()`（udmabuf）→ `VIDIOC_QBUF` V4L2_MEMORY_DMABUF。
  vidc 的硬件把线性 NV12/P010 直接写进 guest 的 IOSurface。
- OUTPUT：码流很小（P 帧几百字节，关键帧约 80 KB），拷进 vidc 自己的 OUTPUT 缓冲（dma_heap）即可，不必零拷贝。
- guest kext：同 Z1 的“IOSurface 当 CAPTURE”；像素缓冲属性对齐 vidc 布局（见 P1）。
- GPU：PlanesInPlace，着色器直接采样 IOSurface 平面。
- 结果：端到端 0 次 CPU 拷贝；宿主没有 c2 线性块和 CCodec 池，只剩 vidc 内部参考帧；guest 没有 kext CAPTURE 缓冲、
  没有插件 RGBA 副本。丢弃帧只是 IOSurface 还给池，没有任何拷贝。
- 改动：crosvm 一个新后端 + kext（IOSurface 当 CAPTURE、预取）+ metal2vulkan（已有方案）。不动 virtio-media 协议、不动 guest 框架。

### Z3 UBWC 交给 GPU（原“档 C”，不做）
- 阻塞：Main10 的 TP10 UBWC 在 Vulkan/turnip 没有对应格式（8 位 NV12 UBWC 也只部分支持）；virtio-media 与 virtio-gpu
  之间没有 UUID 资源共享，要新做（参照 QEMU virtio-dmabuf、ARCVM）；VT 给 App 的 IOSurface 来自 guest 池、背后是 guest
  内存，改成 GPU 资源要动 IOSurface 私有实现。
- 相对 Z2 只多省带宽（线性 vs 压缩），不省 CPU 拷贝（Z2 已是 0），代价大一个量级。

## 选定：Z0 + Z2，Z1 作为 vidc 不可用时的后备

## P0 结果（11-03，research/vidc-probe，root 下直接跑，未开 VM）

探针：research/vidc-probe/vidc-probe.c（aarch64-linux-gnu-gcc -static），输入 research/vt-probe/out/gg4k.hevc
（锁屏航拍 Golden Gate 的前 2 秒，4096×2160 Main10，484 帧）。

- **片子是标准 5 层时间分层**（Z0 成立）：

  | TemporalId | NAL 类型 | 帧数 | 平均大小 | 只留到这一层的帧率 |
  |---|---|---|---|---|
  | 0 | IDR / TRAIL_R | 32 | 62 KB | 15 fps |
  | 1 | TSA_R | 31 | 1.3 KB | 30 fps |
  | 2 | TSA_R | 61 | 0.6 KB | 60 fps |
  | 3 | TSA_R | 120 | 0.3 KB | 120 fps |
  | 4 | TSA_N | 240 | 0.25 KB | 240 fps |

  SPS：profile_idc=2（Main10），sps_max_sub_layers_minus1=4。只留 TemporalId ≤ 1 的 63 帧，vidc 照常解出（0 错误）。
- **msm_vidc 直接 V4L2 可用**：驱动 msm_vidc_driver / msm_vidc_decoder。
  - OUTPUT：HEVC 4096×2176，sizeimage 8 847 360；**不支持 MMAP**（mmap 返回 ENODEV），要用 DMABUF（dma-heap system）。
    plane 长度小于 sizeimage 时 QBUF 返回 EINVAL（内核只打 `msm_vidc_qbuf: failed with -22`）。
  - CAPTURE：SOURCE_CHANGE 之前列 Q08C/NV12/NV21，之后（10 位流）只剩 **Q10C（UBWC）和 P010（线性）**；
    P010 单平面，bytesperline 8192，4096×2176（可见 4096×2160），sizeimage 26 738 688 = 8192 ×（2176 + 1088），
    即色度平面紧接在 2176 行亮度之后。V4L2_CID_MIN_BUFFERS_FOR_CAPTURE = 12。
  - 需要 V4L2_DEC_CMD_STOP 才吐出最后 4 帧。
- **udmabuf 被接受，像素正确**：CAPTURE 用 udmabuf over memfd（与 crosvm 的 guest 内存同类）时，逐帧采样哈希与 dma-heap 完全一致。
- **速度**：4K Main10 P010，全部 484 帧：dma-heap **209 fps**，udmabuf **178 fps**；TemporalId ≤ 1：207 / 187 fps。
  远高于 media_codecs 声明的 performance-point 60，也远高于 MediaCodec 路线的 40.8 fps——之前的瓶颈在 MediaCodec/拷贝路径，
  不在硬件。
- 待验证（P2 时）：udmabuf 用的是 crosvm 真正的 guest 内存（Gunyah 共享页）时是否同样可用。

## P2 实现状态（11-03，已编译，未上机）

- crosvm：`android_codec_backend/vidc.rs` 的 `HwDecoderBackend` 包在 MediaCodec 后端外面，`--virtio-media kind=decoder,...,vidc=true`
  才启用；HEVC/H264/VP9 先试 msm_vidc，打开失败就回退 MediaCodec（日志 warn）。OUTPUT 用 dma-heap 自分配，CAPTURE 用 guest
  USERPTR 缓冲的 udmabuf（`GuestMemoryRange::dmabuf` → `GuestBufferImport::shared_dmabuf`）；格式经 `DecoderEvent::CaptureLayout`
  报给 virtio-media（P010 bpl 8192、sizeimage 26738688）。media 辅助进程加 AID_CAMERA 附加组以打开 /dev/video32。
- kext：patch 0010，P010 逐行直拷进 x420（不再 8→16 位展开）；Z0 按 hvcC numTemporalLayers + 输入时间步长算保留层，
  高层帧在 feedInput 直接 Demt FrameDropped，计数 `droidvm_vthost_frames_skipped`。
- 脚本：`MACOS_MEDIA=1 MACOS_MEDIA_VIDC=1 droidvm-app.py media` 给 decoder 加 `vidc=true`。
- 上机前手工：`echo 16384 > /sys/module/udmabuf/parameters/list_limit`（helper 是 app uid 写不了，默认 1024，重启复位）。
- 待验证风险：SELinux 是否允许 app 域开 /dev/video32 与 /dev/dma_heap/system；msm_vidc 在 CAPTURE 未 streaming 时 poll
  是否恒返 POLLERR（会空转）；每会话 14×26.7 MB guest wired（两路即 750 MB）；8 位 NV12 的色度偏移是否等于 bpl×G_FMT 高度。

## 第一轮上机（11-03）与 P3 实现

- 上机修掉的：kext/virtio-media SG 上限 4096→16384（4K P010 碎成 6528 段）；vidc 模式 CAPTURE 只建 udmabuf 不做宿主 mmap
  （`renew_dmabuf_for` / `GuestBufferImport::unmapped`，否则每缓冲 6528 次 mmap 撑爆 max_map_count、辅助进程 abort 致 VM 崩）；
  Z0 跳帧移到"有空闲 OUTPUT 缓冲"判断之前。
- 实测：msm_vidc 出 P010、Z0 每秒跳 4384 帧、显示约 100 帧/s（多会话合计）、guest 每帧拷贝 19.9 ms；但播放器不断另开会话，
  每会话 kext 常驻 14×26.7 MB，guest 分配失败（diag "no buffer"）→ -12911 → 再开会话，恶性循环。
- 逆向 VideoToolbox（/tmp/vtx，IDA）：guest 的 Dbuf 处理调 `VTDecoderSessionCreatePixelBufferWithOptions`，普通会话不看 `,frm`，
  从池取缓冲按新 UUID 存待定表；Demt 只按 `,uui` 取；Dfub（`,uu+` CFUUID 数组，类型 `=uu+`）释放待定缓冲。
- P3（patch 0010 内）：P010 时 CAPTURE 就是 Dbuf 预取的池 surface（withAddressRange 客户进程地址 + prepare 后建 SG），解完直接
  Demt 带该 UUID、槽位再 Dbuf 一个；被 0008 抽掉的帧保留原 surface；会话结束 Dfub 归还。Dpba 加 ExtendedPixelsBottom
  （猜对齐 32，SOURCE_CHANGE 后按实际高度重发）；布局不符（`surfaceFits`）回退拷贝模式并打日志。已编译，未上机。

## 阶段与止损点

- **P0 可行性（宿主独立探针，不开 VM）**：在手机上以 root 跑一个 C 探针（参照 Rungic codec-v4l2.c 的顺序）：
  1. 打开 /dev/video32，QUERYCAP、ENUM_FMT，确认 HEVC 输入、NV12/P010 线性输出。
  2. 用一段 4K Main10 HEVC（从 guest 的 idleassetsd/Customer/4KSDR240FPS 取前几个 GOP，或手机上自编一段）解 N 帧：
     CAPTURE 分别用 (a) /dev/dma_heap/system，(b) **udmabuf over memfd**（模拟 guest 页）。
  3. 记录：udmabuf 能否 QBUF 并解出正确像素（与 (a) 逐字节比）；G_FMT 给的 stride/scanlines/平面偏移；4K Main10 实际 fps。
  4. 解析该片子的 NAL 类型与 TemporalId 分布（Z0 能否成立）。
  - **止损**：udmabuf 被 vidc 拒（mem_buf/vmperm 检查等）→ 先试 msm_prime 那套 mem_buf ops 包装；仍不行就退 Z1。
- **P1 布局对齐（静态 + guest 探针一次）**：vidc 线性布局已实测（P0）：P010 亮度 8192 B/行 × 2176 行，色度紧随其后 8192 B/行 × 1088 行。在 kext 的 pixelBufferAttributes 里用 BytesPerRowAlignment、
  PlaneAlignment、ExtendedPixelsBottom 让 CoreVideo 分配出同样布局的 IOSurface；用 research/vt-probe 在 guest 里打印实际平面偏移核对。
  对不上就由后端按 IOSurface 实际偏移用 V4L2 的多平面/data_offset 告诉 vidc，或退 Z1。
- **P2 crosvm 后端**：
  - msm_vidc 后端（v4l2r），设备打开：helper 进程是 app uid，打不开 0660 的 system:camera 节点 → 由 root 的 crosvm 主进程打开、
    SCM_RIGHTS 传给 helper（或给 helper 加组/SELinux 规则，二选一，P0 时确认 crosvm 域能否打开 video_device）。
  - 固件顺序按 Rungic：OUTPUT STREAMON → 一个 AU → SOURCE_CHANGE → CAPTURE。
  - 后备：任一步失败退 android_codec_backend，日志写明原因。
  - DecodeBudget 继续限制同时的 4K 会话数。
- **P3 kext**：IOSurface 当 CAPTURE（Dbuf 预取 = CAPTURE 数量；帧出来后 Demt 带对应 uuid；丢弃帧把 surface 还池）；
  Z0 时间层跳帧；撤掉 0007 的 8→16 位扩展（P010 直出）；保留 0008 PTS 抽帧和 0009。
- **P4 GPU**：按 k27-vt-paravirt-plan.md 的 PlanesInPlace 步骤 1–2。
  - 11-04：原型 3623549（metal2vulkan-macos/0001 + 插件 METAL2VULKAN_YCBCR_PLANES_ONLY）已生效（/tmp/k27-gpumem.py 看 WindowServer 无 35 MiB 转换块）。CPU 基线未量。
- **P5 验证（一次上机）**：壁纸帧率、宿主 v_media_worker CPU、dmabuf 峰值（按 exporter 汇总）、guest WindowServer 内存、
  会话不再反复重开；Windows VM 回归（crosvm 换了后端选择逻辑）。

## 风险

- vidc 对 udmabuf 的导入是最大未知（libcamera 文档提到 udmabuf 不一定适合与设备零拷贝共享；我们在 GPU/显示上靠 msm_prime 包装过）。P0 先验。
- Gunyah：guest 页给 vidc 的 IOMMU 映射，受保护 VM 下必须是已共享的页（HostAccessPolicy 照旧检查）。
- 与 Android 自己的视频业务共用 vidc 会话数；手机前台播视频时可能抢不到，需后备。
- 片子若不是时间层结构，240 fps 仍超出 4K 60 fps 上限：此时只能降低播放需求（例如只解关键帧附近的子序列）或接受慢放/软解兜底。
- 换 crosvm 影响所有 VM；Windows VM 的视频走同一个后端选择，需回归。

## 参考

- Rungic PR #12：Hardware video decoding and encoding straight through msm_vidc V4L2, MediaCodec bridge v2 as fallback
  （https://github.com/kevinzhow/Rungic/pull/12 ，详细说明在其 docs/108-codec-bridge-buffers.md；本机访问 GitHub 失败，细节来自搜索摘要，P0 前需再读原文）
- V4L2 DMABUF 导入：https://docs.kernel.org/userspace-api/media/v4l/dmabuf.html
- Iris 解码器缓冲对齐：https://gbmc.googlesource.com/linux/+/01c93aa01c75e7a43f7f53229bcbecffac75eb84/drivers/media/platform/qcom/iris/iris_buffer.c
- HEVC 子层非参考帧可丢弃：https://docs.rs/cros-codecs/latest/cros_codecs/codec/h265/parser/enum.NaluType.html
- QEMU virtio-dmabuf（Z3 才需要）：https://patchew.org/QEMU/20230626073426.285659-1-aesteve@redhat.com
- udmabuf 用于设备共享的限制（libcamera）：https://patchwork.libcamera.org/patch/20150/
