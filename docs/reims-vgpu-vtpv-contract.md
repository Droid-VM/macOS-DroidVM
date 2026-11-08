# reims-vgpu 的 vtpv 协议实测：对 k27 视频解码的启示

2026-11-04 整理。来源是 https://github.com/steelbrain/reims-vgpu 的 `docs/video/devices.md` 和 `docs/video/core.md`，原文副本在 `~/gotmp/reims-docs/`。本机 git clone 很慢，可以用 tavily_extract 抓 raw.githubusercontent.com。

reims-vgpu 是 QEMU 用的库，替代苹果的 ParavirtualizedGraphics。`crates/reims-vgpu-video-*` 实现了苹果 VideoToolbox 半虚拟化设备（PCI 106b:1a03，guest 驱动是 AppleVideoToolboxParavirtualization）的宿主端，后端有 VA-API、NVDEC 和 VideoToolbox。

我们的 `DroidVMVTHost` kext 在 guest 内核里扮演的就是这个宿主端，说的是同一套 vtpv 消息。reims 的文档在 M3 Max 上直接驱动苹果自己的宿主会话（`VTParavirtualizationHostSession`）做了实测，可以当协议规范用。

许可证是 GPL-2.0+ 或 LGPL-3.0+，只参考行为，不搬代码。

文中标注：**[实测]** 表示 reims 在苹果宿主或 guest 上跑过；**[读]** 表示从苹果二进制里读出来的；**[推断]** 是我们自己的推测。

---

## 1. 核心结论：出帧时序和苹果不一致

| | 苹果宿主 / reims | 我们（0011） |
|---|---|---|
| 出帧顺序 | **按解码顺序，每个 dfrm 出一帧**，码流里有重排序也一样 [实测]。重排序由 guest 的 VT 自己做 | msm_vidc 按显示顺序出帧，codec 会压着几帧做重排序 |
| 同步 dfrm（`,dfl 0`） | Dbuf→回复→Demt→回复→rels→**然后才回 dfrm**（`,err 0, ,inf 0`）[实测] | 收到就立刻回 `,inf 1`（`DroidVMVTHost.cpp` 里的 `case cc("dfrm")`） |
| 异步 dfrm（`,dfl 1`） | Dbuf 被回复后就回 dfrm（`,inf 1`），之后再发 Demt；**最多 3 帧在途**（Dbuf 0/1/2 先于 Demt 0）[实测] | 同上，一律立即回复 |
| guest 节奏 | guest 等到每个 dfrm 的回复才发下一帧 [读] | 播放器每秒灌 4000–5000 帧 |
| 航拍壁纸 | WallpaperAerialsExtension 开 3840x2160 Main10 会话，**同步解码**，15 个 dfrm 全是 `,dfl 0`；guest 按 30 fps 定步 [实测，26.7.1 x86_64 guest] | 灌满输入表，报 -12911，会话不断重建 |

### 这能解释的问题 [推断]

- **-12911、会话反复重开、MaxBacklog/ShedMs 按层砍帧、驱逐（makeRoom）**：根源都是 dfrm 不阻塞，播放器失去了自然的背压。
- **`os_unfair_lock_recursive_abort`**：起因是"帧拖太久才交出"，而帧被压住是因为显示序重排序。按解码序出帧，Demt 就不会在会话被放弃之后才到。
- **0006 背压导致黑屏**：在显示序下，第 N 帧要等后面的帧送进来才能输出，阻塞 dfrm 就成了自锁。所以之前"DecodeFrame 绝不能阻塞"的结论可能是误判，真正的问题是出帧顺序。

### 修复方向

1. **宿主**：确认 msm_vidc 能不能按解码序输出。V4L2 标准控件是 `V4L2_CID_MPEG_VIDEO_DEC_DISPLAY_DELAY_ENABLE=1` 加 `..._DISPLAY_DELAY=0`，venus/iris 把它映射成解码序输出。msm_vidc 下游驱动是否支持**未核实**，要先在手机上对 `/dev/video32` 跑 `VIDIOC_QUERYCTRL` 枚举，再用 `vidc-replay` 验证：解码序出帧、5 层 HEVC 是否完整、P010 的 CAPTURE 块数需求。
2. **kext**：改成苹果的语义。
   - 同步帧在 Demt 被回复之后才回 dfrm（`,inf 0`）。
   - 异步帧在 Dbuf 被回复后回 dfrm（`,inf 1`），最多 3 帧在途。
   - 每个 dfrm 恰好对应一个 Demt：有图像、FrameDropped、或者失败状态三选一。
   - 改完后 0011 里的 IdleDrain、Evict、MaxBacklog、Shed、MaxReplay 大多可以删掉。
   - 先在 `research/vthost-harness` 上跑 suite，再上机。
3. **吞吐风险**：reims 的航拍是 26.7.1 的片源；27 的锁屏片源是 4K 240fps（[[macos-k27-vt-paravirt]]）。同步逐帧能不能跟上要实测。Z0 跳掉 TID4 后只剩一半帧，msm_vidc 实测 P010 能到 209 fps。如果 27 的播放器确实每帧都同步等，帧率上限就是单帧往返时间。

---

## 2. 消息格式 [读+实测]

### 头部

vtpv 容器里所有标量都是大端：

| 偏移 | 大小 | 字段 |
|---|---|---|
| 0x0 | 4 | atom 大小（含头） |
| 0x4 | 4 | `vtpv` |
| 0x8 | 4 | 消息类型 FourCC |
| 0xc | 4 | flags |
| 0x10 | 16 | 会话 UUID |
| 0x20 | 8 | reply id |
| 0x28 | 8 | 保留，填 0 |

- **头部固定 48 字节**，参数作为它的兄弟 atom 跟在后面。
- 参数格式：`[u32 size][para][u32 key][u32 type][payload]`。
- 同一个 key 只取第一个。key 匹配但类型不对：-19093，不回复。缺失的参数按默认值处理（0、NULL、kCMTimeInvalid）。
- 各类型的长度校验：`=u32/=s32` 共 20 字节，`=s64` 24，`=tim` 40，`=uui` 32，`=ui+` 16+16n。

### flags

| 值 | 含义 |
|---|---|
| 0x1 | guest 请求，等宿主回复 |
| 0x2 | 宿主请求，等 guest 回复 |
| 0x4 | 宿主的回复 |
| 0x8 | guest 的回复 |
| 0x10 | 后面还有分片 |

- 回复沿用请求的类型、UUID 和 reply id。
- 两边各自从 100 开始编号。
- 超时返回 -19092；回复对不上任何未完成请求时返回 -19093。

### 分片

- 大值会切到多条消息里，除最后一条外都带 0x10。
- guest 解码器每条最多 0x200000 字节。
- 宿主只回复最后一个分片。

### sbuf 子 atom

顺序是 opts、stia、sdat、nsmp、ssiz、fdsc、crpt、satt/sat2/sary：

- stia：每个样本 72 字节（duration/pts/dts）。
- fdsc：只在和上一次不同时才带。
- **atom 头是大端，里面的标量是本机字节序**。

### surface

- 消息开头可以有一个 `subs` atom，固定 0x30 字节：头加 5 个 u64 映射 ID。
- 宿主会话为每个 guest surface 记一个弱引用 child。每次投递结束时把已经死掉的 child 以独立的 `rels` box 发回：`[u32 8+8n][rels][n×u64]`，不放在 vtpv 消息里。
- guest kext 只有在 rels 点名后才释放映射。

### 队列

- 队列 0：guest→宿主。写回部分是 4 字节状态（i32，宿主字节序）。readable 超过 16 MiB 时，reims 返回 -12904 不读。
- 队列 1：宿主→guest。guest 投 0x4000 字节的 buffer，宿主用环形缓冲写回。
- 苹果的队列最多 256 个描述符。

---

## 3. 解码会话 [实测，苹果 AVD]

### 打开会话

- `+dec` 参数：`,cod`（s32）、`,ver 6`、`,cid`（HostDecoderID）、`,gin {VTGuestBuildVersion}`。
- 回复：`,err`、`,ver 6`、`,hin`。
- 同一个 UUID 再发一次 `+dec`：-19093，不回复。未知 UUID：-19094。

### 串行队列

- 每个 `+dec` 有自己的串行队列：deliver 立即返回 noErr，handler 稍后回复。
- guest 的回复（0x8）不进队列。
- handler 等 guest 期间，**整个队列都在等**。

### Dpba

在 dsta 回复**之前**发出，内容是：

```
{PixelFormatType [...], Width, Height, IOSurfaceProperties {},
 BytesPerRowAlignment 64, PlaneAlignment 256,
 PreferRealTimeCacheModeIfEveryoneDoes 1}
```

- 像素格式：8 位 420v；**Main10 用 x420**；满幅范围分别用 420f / xf20。
- AVD 会额外带 ExtendedPixelsRight/Bottom，即编码尺寸的对齐余量，例如 1080p Main10 的 Bottom 是 8。reims 不带这两个键，也能工作。

### Dbuf / Demt

- **Dbuf**（flag 0x2，参数 `,frm`、`,pop`）：等 **1.1 s**，guest 回 `,err`、`,uui` 和 surface。
- **Demt**（flag 0x2，参数 `,frm`、`,err`、`,inf`、附件、`,uui`）：等 **10 s**。
- Demt 一直没有回复时，dfrm 的回复会被压住 10.0 s。
- 没有被 emit 就死掉的 buffer，每帧结束后的清理会发 `Dfub`（`,ui+`，不带 flags）通知 guest。
- guest 读不懂的 Demt，或者 UUID 未知的 Demt：guest 记错误，不回复。

### 其他消息的回复

| 消息 | 回复 |
|---|---|
| dfin | -12782（AVD 未实现）；reims 会先吐出剩余帧 |
| dinv | 0 |
| dcan | dsta 前为 0 |
| dsup | 13 项属性，含 OnlyTheseFrames、ReducedFrameDelivery 以外的 QoS 等 |
| dset RealTime | 0 |
| 未知属性 | -12900 |
| dset Paravirtualized | 宿主保留，拒绝且不回复 |

### 状态机

- 没有成功的 dsta 时（之前从未 dsta、dsta 被拒、或者 dinv 之后），dfrm 立即回 `,err 311, ,inf 0`，不发 Dbuf/Demt。
- **第二次及以后的 dsta 一律 -12909**，会话保持第一次的配置。
- 换格式要在 sbuf 里带新的 fdsc（avcC/hvcC），从那一帧起重新配置。

### 尺寸限制

- AVD 的 H.264/HEVC 编码尺寸任一边小于 64 时，dsta 返回 -12911，不发 Dpba。
- 以前记过的"c2 最小 96x96"属于另一回事。

### dfrm 回复里的 `,inf`

- 异步帧恒为 0x1，同步帧恒为 0，与解码成败无关。
- 例外：RASL 帧被丢时为 0。
- `kVTDecodeFrame_DoNotOutputFrame` 对 AVD 不起作用，照样输出图像。

---

## 4. 错误与丢帧 [实测]

- **空样本或要丢的帧**：发 Demt，带 `kVTDecodeInfo_FrameDropped`，不给 buffer。我们的 Z0 已经这么做。
- **解码失败的帧**：顺序是 Dbuf→Demt（-12909，不给 buffer）→Dfub→rels，然后 dfrm 回 noErr。
  - H.264：后续每一帧都回 -12909，直到某个 I 帧成功解码。
  - **HEVC：要等到一个 IRAP（IDR/CRA/BLA）成功解码才恢复**。非 IRAP 的全 I 帧不算。IRAP 自己坏了也不算。
  - 结束失败状态的那个 CRA 会被当作 BLA 处理，它的 RASL 帧要丢弃。
- **丢弃的 RASL 帧**：Demt 带 -17694（kVTVideoDecoderReferenceMissingErr），`,inf 0xa`。
- **丢包**（码流里少了帧）：AVD 照样逐帧给出图像和 noErr；reims 用最后一个参考帧顶替缺失的帧。
- 对照我们的 msm_vidc：drain 之后会有 3–6 帧带 ERROR（[[macos-k27-vthost-harness-0011]]）。按上面的规则，这些帧应该作为失败帧交出，并把会话标成"等 IRAP"；航拍片源只有首帧是同步样本，要注意这一点。

---

## 5. 超时与会话关闭 [读+实测]

### guest 侧的等待时间

| 请求 | 等待时间 |
|---|---|
| 默认 | 1.1 s |
| 编解码操作：同步 dfrm、dtil、efrm、ecfr、mepf、mcfr | 10 s |
| 异步 dfrm | 1.1 s |

- 25G241 的 arm64 guest 因为 fcvtzs 饱和，实际只等 2.147 s。
- **macOS 27 用 64 位寄存器换算，实际等满 10 s**。

### guest 已经放弃的帧

- 标志：同步模式下，宿主手里那帧还没完，后面已经排着下一个 dfrm，说明 guest 已经超时放弃了它。
- guest 会丢弃这帧的 Demt（"Unrecognised VTVideoDecoderFrame token"）。连续多次之后，guest 会不再回复 Dbuf。
- reims 的做法：**照样解码以保住参考链，回复 dfrm，但不发 Dbuf/Demt**。效果是航拍会话的寿命从 99 s 降到 30 s，且没有 Dbuf 超时。

### 关闭会话（`-dec`）

- 苹果的 `-dec` 要等队列里正在处理的那条消息。如果 handler 正在等 Dbuf/Demt，就要白等 1.1 s 或 10 s，设备在此期间卡住。
- reims 先取消这些等待，效果相同但更快。会话失效后什么都不再发。
- 对照我们：0011 的递归锁 abort 发生在 Demt 回调里触发 Invalidate。改成解码序、同步回复之后，这个窗口应该基本消失。

---

## 6. 零拷贝的参考 [实测，core.md]

- reims 把 guest surface 的页拼成 udmabuf，一页一段。超过 udmabuf 限制时按行切成条带，每个平面一个 dma-buf，最多 64 条。和我们的 `list_limit` 问题是同一类。
- 节省的是 4K 每帧 1–3 ms 的 CPU 拷贝。在 guest 里，同步 4K 解码快了 14%–75%；航拍每帧的线程 CPU 时间从 3.61 ms 降到 0.56 ms。

---

## 7. 不打算采用的部分

- **代码**：许可证是 GPL/LGPL，而且没有 msm_vidc 后端。只参考行为。
- **改用苹果原生 kext 加 crosvm 模拟 106b:1a03**：需要让 AppleVirtIO 的 PCI 传输在我们的 ADT 平台上工作，改动太大。如果以后 kext 维护成本过高，可以再评估。reims-vgpu-video-core 本身和宿主、QEMU 都无关，它的消息顺序可以直接当对照。

相关文档：`k27-vt-paravirt-plan.md`、`k27-vt-zero-copy-plan.md`、`k27-vt-p3-status.md`。
