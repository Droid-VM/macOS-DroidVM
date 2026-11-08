# k27 锁屏航拍：P3（vidc 直写）现状与待办（2026-11-04，晚间更新）

上接 `k27-vt-zero-copy-plan.md`（方案 Z0+Z2、P0/P2 结果、第一轮上机）。本文记录 11-03 晚到 11-04 的进展：哪些结论已经站住、哪些被推翻、代码和设备停在什么状态、下一步做什么。

## 一句话现状（11-04 晚更新：已解决）

- **锁屏航拍壁纸已有画面（用户 11-04 确认）**。根因不是会话泄漏本身，而是协议语义错了：kext 对 dfrm 一律立即回复（播放器每秒灌
  4000–5000 帧、无背压），msm_vidc 又按显示顺序扣帧；帧在播放器放掉会话后才 Demt，guest VT 在持解码器锁的回调里 Invalidate，
  再加同一把锁 → `os_unfair_lock_recursive_abort`（从 guest RAM 里扫出的崩溃报告证实）。
- 修法按 Apple 宿主语义（`reims-vgpu-vtpv-contract.md`）：crosvm 让 msm_vidc 按解码顺序出帧（display delay 0）；同步 dfrm 在该帧 Demt
  被回复后才回；异步 dfrm 在途 >3 帧时压住回复。见下文「11-04 晚：Apple 语义」。
- 下面 11-03/11-04 白天的记录保留作历史，其中"会话泄漏是主线"等判断已被取代。

## 已站住的结论

| 结论 | 证据 |
|---|---|
| 会话泄漏 | kext 计数 `vclose`=0（`dinv`/`-dec` 很少到达）；host 日志里 msm_vidc 会话一直到 VM 停才关；`refused` 出现在第 9 个会话 |
| 播放器结构 | WallpaperAerialsExtension 用 AVAssetReader（FigAssetReader/Boss）解码，再送进 VideoPlayerLayer（AVSampleBufferDisplayLayer），不是 AVPlayer；每段视频一个 reader、一个 VT 会话；"Ran out of samples… Moving to next" 约每 4 秒一次 |
| 会话都来自同一进程 | kext life 日志：`+dec`/`dsta` 全是 pid=WallpaperAerials，每次新 UUID，中间没有 `dinv`/`-dec` |
| 崩溃顺序 | 有一个会话 in 1813 / out 0 / pending 1800 → 播放器 `VTDecompressionSessionInvalidate`（kext 收到 `dinv`）→ 紧接着 `maybe_unrecoverable_exception_triage … WallpaperAerials` → SIGKILL；拷贝模式稳定复现，VM 起来约 20 s |
| 不是固件崩溃 | 这一轮关会话时 dmesg 没有 `invalid session`（早先几轮的 `invalid session` 都是 VM 停时批量关会话留下的） |
| 不是映射缓存造成的 | 撤掉 copyFrame 的 surface 映射缓存后照样崩 |
| msm_vidc 输出缓冲 | 后端报最小值 2、guest 只挂 4 块时 0 帧输出（但当时也在泄漏环境里，见下）；已改回驱动原值（12） |

## 已推翻 / 不能算数的判断

- **"提前占 14 个 surface 就黑屏，所以直连做不成"**：mode 6（拷贝进提前取的缓冲）深度 14 黑、深度 2 有画面，但两次都处在会话泄漏和内存紧张中。原因不明，不能据此否定直连。
- **"播放器报 `VideoPlayerLayer failed to create decoded pixel buffer` 是黑屏根因"**：能出画面的 mode 4 下也大量出现。它只说明有帧以空图像交给了播放器，不是黑屏原因。
- **"msm_vidc split 模式只排 2–4 块输出就够"**：上游 iris 源码支持这个推断，但实测 4 块时 0 帧。测试环境有干扰，结论待重测。
- **"每帧新建 udmabuf 造成 dmabuf 暴涨"**：crosvm 加 dmabuf 缓存后照样涨，涨的是没关的 msm_vidc 会话。缓存留着，没有坏处。

## 逆向得到的协议细节（VideoToolbox 27.0.1）

- **Dbuf** `0x44627566`：`VTDecoderSessionCreatePixelBufferWithOptions` 用普通 `CVPixelBufferPoolCreatePixelBuffer`，没有分配上限，不会阻塞；结果按新 UUID 存进解码器对象 +72 的待处理字典，回复带 `,uui`。
- **Demt** `0x44656D74`：按 `,uui` 查字典并移除；**查不到时不写日志，直接以空图像输出**。
- **Dfub** `0x44667562`：`,uu+` 数组，按 UUID 取出并遗忘。另一处调用来自多图输出消息。
- **dinv**（`ParavirtualizedVideoDecoder_Invalidate`）同步发送并等回复；**-dec**（`_Finalize`）异步发送，用同一个会话 UUID（对象偏移 32）。**dfin** = `FinishDelayedFrames`。
- `vtDecoderSessionEmitDecodedFrameCommon`：先按 frame 查帧记录；再经 `vtDecompressionSessionCreateDestinationImageBufferForEmittedFrameIfNecessary` 判断要不要转换。两个 pool 不同、或颜色属性不兼容时，会从目标 pool 另取缓冲做 VTPixelTransfer，失败则图像置空。**拷贝模式下 VT 是否每帧又转换一次，还没核实。**
- 播放器回调（WallpaperExtensionKit `sub_2A4BA92B4`）：`imageBuffer` 为空且未标丢帧时，打 "failed to create decoded pixel buffer"。

字符串定位：`ipsw dyld str <DSC> "…"`；DSC 在 `artifacts/27.0.1/systemos.img`（loop 只读挂载后 `/System/Library/dyld/`），系统盘 `os.raw` 的 APFS 容器偏移 `411648*512`，`vol=0`。

## 代码状态（11-04 晚已全部提交）

| 仓库 | 提交 | 内容 |
|---|---|---|
| external/virtio-media（droidvm-hackintosh） | d509294 | dma-buf 交给硬件、`MAX_SG_ENTRIES` 16384、DISPLAY_DELAY(_ENABLE) 控件 |
| external/crosvm（wip/macos-virtio-gpu） | fe24182b6 | MediaCodec 解码像素预算、priority/operating-rate、输入缓冲上限 2 MiB（DIAG 已删） |
| external/crosvm | b7960bae6 | `vidc=true` 后端（vidc.rs）、无映射 dmabuf + LRU、解码顺序、CAPTURE 4 块即 STREAMON |
| macos | 2f7c955 | 补丁 0004–0010、`MACOS_MEDIA_VIDC` |
| macos | b6cc61b | 补丁 0011（Apple 语义 + 会话生命周期）、rig-dmesg 批量读 |
| macos | 3623549 | WindowServer 原地读 YCbCr 平面原型（metal2vulkan-macos/0001 + 插件），**未在机上核实** |
| macos | 0855e2a | 启动修补（DroidVMEthernet NoBSDWait、boot-manifest-hash、App cryptex 信任缓存等） |

crosvm 已 rebase 到 Droid-VM wip/hackintosh c9e24ed54（11-04 晚，含打开文件数上限与手写笔两个提交；备份分支 backup/wip-macos-virtio-gpu-1104）。
kext 视频源 VT_REF 已换到上游 706338e（macos e2d0bf6）。

`research/`（vthost-harness、vidc-probe）被 .gitignore 排除，只在本地。手机上的 crosvm 是 b7960bae6 之前、带 DIAG 的同等版本（功能相同）。

## 设备上的状态（需要记得收尾）

- **手机 crosvm**：已换成带 dmabuf 缓存和关闭日志的版本，备份是 `usr/bin/crosvm.bak-1103`。
- **用户 Data**：已打 store-patch，加了 log-stream 启动项（`org.droidvm.log-stream`）。谓词是 Wallpaper* 进程全部、VTDecoderXPCService、coremedia 错误、WindowServer 错误。回滚用手机上的 `data-store.undo.bin`，或再打一次补丁去掉。种子 `1aa0a464ac13866f` 没变。
- **log-stream 的副作用**：msgbuf 很容易被刷满，kext 自己的日志会丢。
- **手机脚本**：
  - `hostmon2`（3 s 采样）仍在跑；
  - `dmamon` 已停；
  - `vidcmon.sh`（`dmesg -w` 过滤）**没生效**，抓到的文件是空的；
- **VM 配置**：`MACOS_MEDIA_VIDC=1`，解码走 msm_vidc。测试完要问用户是否改回 MediaCodec。
- **adb**：11-04 晚起用 tailscale 100.102.230.78:33445（用户指定）；连不上再试局域网 192.168.1.203:33445。
- **手机 crosvm（11-04 晚）**：带解码顺序支持的版本（备份 `usr/bin/crosvm.bak-1104`）；启动参数见下方常用命令（`droidvm-vt-direct=1`、`msgbuf=1048576`）。
- **宿主 watchdog**：`/tmp/vmwatchdog2.sh` 每秒查一次，可用内存低于 2.5 GB 就停 VM。VM 正常运行时手机余量只有约 3.3 GB，阈值不能再高。

## 宿主回放（11-04，不开 VM）

工具：`research/vidc-probe/vidc-replay.c`（复用 vidc-probe.c 的切分/dmabuf/ioctl，按 vidc.rs 的顺序开会话，CAPTURE 选线性 NV12/P010）。
按播放器节奏每 4 s 开一个 4K HEVC Main10 会话（gg4k.hevc，TemporalId ≤ 1），只给最新的送帧，旧会话按策略关闭。
默认所有会话的 CAPTURE 共用一块 memfd 上的 udmabuf（VM 里 CAPTURE 是早就占好的 guest 内存，宿主新增的只有驱动那份）。
手机上 `/data/local/tmp/vidc-replay gg4k.hevc --policy … [--stall-old]`，输出 `replay-*.txt`。

| 策略 | 结果 |
|---|---|
| leak（旧会话不关，照常收帧） | 第 8 个（编号 7）QBUF CAPTURE `Failed to map table, -12`，吃进 1 帧后再无输出；第 9 个起 STREAMON OUTPUT 被准入控制拒绝：`msm_vidc_check_core_mbpf: video overloaded. needed 311296, max 278528`（每个 4K 会话 34816 MB，上限 = 8 个） |
| leak + `--stall-old`（旧会话完全没人处理：CAPTURE 不还、OUTPUT 压着帧） | 6 个会话全部正常出帧：旧会话卡住不拖累新会话 |
| cap:2 / idle:1000 | 各 30 个会话，0 拒绝、全部出帧，首帧 65–400 ms，可用内存稳定（驱动每会话约 300 MB，关闭 8–60 ms） |

结论：
- msm_vidc 的限制是"8 个 4K 会话"的 mbpf 准入加上 IOVA/映射，和 VPU 调度无关；只要会话真的关掉，cap:2 或 idle:1000 在宿主上都没问题。
- **11-04 那次崩溃不是宿主侧问题**：crosvm 日志里只开了 5 个 msm_vidc 会话，CAPTURE 全部建好，没有拒绝，也没有报错；
  `msm_vidc closed` 全是崩溃那一刻（08:10:53）批量出现的，说明 **0010 的空闲关闭一个都没真正关掉**。崩溃的那个会话（`v4l2 4`，
  in 1813 / out 0）在宿主上是健康的，帧没出来的问题在 guest 侧：kext ↔ VT（崩溃后还有 `stage 30` Dbuf 无回复）或 virtio-media 事件回传。
- kext 的两个缺口：
  - `workerMain` 的空闲关闭要求 `sessionQuiet`（输入队列空、无事件）。旧会话只要还有排队的输入或事件就永远不关；
  - `MediaEvtError` 只 `failed(70)`，会话继续收帧、`pendingFrames` 继续涨（宿主出错时就会变成"只进不出"）。
- crosvm 的缺口：`HwDecoderSession::start` 在 msm_vidc 拒绝时静默回退 MediaCodec，而 MediaCodec 用的是同一个 VPU、受同一个 mbpf 上限约束；
  worker 出错后线程退出，之后每次 `decode` 都返回 EIO。

## kext 用户态测试框架与修复 0011（11-04）

`research/vthost-harness/`：`DroidVMVTHost.cpp` 原样编译成 Linux 程序（`xnu_stub.h`/`stub.cpp` 用 pthread 实现 IOLock、计时、线程、IOKit 对象），
接上假的 virtio-media 解码器（`fake_media.cpp`，参数来自 vidc-replay 实测：单 VPU 4 ms/帧、SOURCE_CHANGE 150 ms、最小 12 块、扣 4 帧、
8 个会话上限，可注入映射失败/设备报错）和假 VT（`harness.cpp`：guest→host 发送持传输锁，host 请求由一个接收线程串行处理，
Dbuf 生成 IOSurface 并经假 IOSurfaceRoot 查找，按会话记录待出帧）。播放器按航拍节奏：每 4 s 一个会话，240 fps 时间戳、5 层时间分层，
400 帧/s 送入，片尾 dfin，最后统一 dinv/-dec。

- 构建与运行：`research/vthost-harness/build.sh`（ASan/UBSan；`SAN=thread` 换 TSan；`KEXT=路径` 换源码，`kext/DroidVMVTHost.cpp.0010` 是基线），
  `./suite.sh [场景...]`，每个场景的输出在 `out/suite-<名>.txt`，kext 日志在 `.log`。
- 检查项：设备会话同时 ≤2；不被设备拒绝；每个会话至少显示 N 帧；dinv 时待出帧 ≤64；dinv 在 250 ms 内应答；不对没给过或已交还的帧发 Demt；
  dinv 应答后没有 Demt；设备会话随 VT 会话全部关闭；fast 轮询计数归零。
- 内存模型 `--guest-mem-mb`：按 4K 等效记账（kext 缓冲加存活的 pixel buffer），超过预算时 Dbuf 晚于 2 s 才回复。
  `mem900` 复现了真机特征：会话 2–6 一帧不出、待出帧涨到 2400、设备会话开到 6 个不关、dfin 超时、stage 30/31。

| 场景 | 0010 | 0011 |
|---|---|---|
| base（正常节奏） | PASS | PASS |
| stall（Dbuf 卡 2.5 s） | 重复 Demt | PASS |
| overlap / mem（片段重叠） | PASS | PASS |
| mem900（内存不足导致 Dbuf 卡住） | 设备会话 6 个、会话无画面、待出帧 2400；另有一次 ASan use-after-free | PASS |
| noz0（不跳层，全部解码） | 重复 Demt | PASS |
| error（设备会话中途报错） | 之后再无画面 | PASS |
| refuse（设备只给 1 个会话） | 设备会话泄漏 | PASS |
| invmid（积压中途 dinv） | 重复 Demt | PASS |
| direct（P3 直连） | PASS | PASS |

0011 两轮全部通过；TSan 下只剩诊断计数器的非原子自增（0010 就有）。`k27/build-native-video.sh` 已用真机工具链编译通过，未链接 KC、未上机。

0010 里找到的问题（0011 全部已修）：
1. 拷贝模式下 worker 同步等 Dbuf（2 s）。VT 一卡，流水线就冻结，输入无限堆积，会话永远不"安静"，空闲关闭从不触发（对应真机"一个都没关"）。
2. dfin 到期后把剩余帧当失败交还，但不清理流水线，这些帧之后又被解出来，**重复 Demt**。真 VT 查不到帧时会输出空图像，"failed to create decoded pixel buffer" 很可能就来自这里。
3. `dropOutstanding` 逐帧同步等 Demt 回复：真机每帧约 40 ms，1800 帧要 72 s；guest 线程在 selector 3 里等 worker 时，回复也根本发不出来。
4. Dbuf 失败（超时或被拒）的帧**既不 Demt 也不报错**，VT 会永远等下去。
5. `startSession` 在设备会话打开之后失败（例如 STREAMON 被拒），设备会话不关，泄漏到 dinv。
6. `MediaEvtError` 被忽略，会话继续收帧但永远没有输出。
7. **内核 use-after-free**：VT 的回复路径不持锁查会话链表，其他 guest 线程上的 `-dec` 可能正在释放这个会话。上游 UniXNU-droidvm 也有这个问题。

0011 的做法（`patches/droidvm-video/0011-session-lifecycle.patch`，补丁头有逐条说明）：
- 新会话 `makeRoom`：其他会话里已有 2 个开着时，淘汰最久没收到帧、且空闲 ≥500 ms 的那个；已有 4 个时不论是否空闲都淘汰。dsta 被设备拒绝时强制淘汰最旧的再试一次。
- 会话被放开（空闲、被淘汰、设备报错）：剩余帧按丢弃交还，补答 dfin，等下一个关键帧（HEVC IRAP / H.264 IDR）再开设备会话；恢复被拒时 1 s 后再试。
- 空闲关闭不再要求会话安静；积压超过 32 帧就丢掉，从关键帧继续；Dbuf 失败的帧按丢弃交还，超时后暂停 Dbuf 500 ms；只对 VT 还在等的帧发 Demt。
- 会话链表加 `listLock`；`lastInputAt`/`finished` 改在锁内写。

注意：`research/debug-2026-11-03/build.sh` 会在补丁之后再跑两个诊断脚本做文本替换，它们是按 0010 的源码写的，0011 之后不一定还能套上。

## 11-04 晚：Apple 语义（0011 最终版）

- crosvm：virtio-media 新增 `V4L2_CID_MPEG_VIDEO_DEC_DISPLAY_DELAY(_ENABLE)`，vidc 后端在 STREAMON 前设 delay 0。vidc-replay 实测：
  同步送帧 + 解码顺序 1:1 出帧、0 错误、约 270 fps；同步送帧 + 显示顺序会死锁。
- kext：startSession 设 delay 0，成功才进入"解码顺序"模式（失败=MediaCodec/旧 crosvm，回退为立即回复 + 旧的治标机制）。
  - 同步 dfrm（`,dfl` 无 bit0，缺省也算）：Dbuf→回复→Demt→回复后再回 dfrm（`,inf 0`）。
  - 消息线程上不能等 guest 回复（回复也走这条线程，只会 2 s 超时）：Z0/resync 丢帧发 Demt 不等，Demt 回复到达时在回复分发里回 dfrm；
    hostRequest 被 evict 打断时同理。挂起的 dfrm 只在 dinv/-dec/client 关闭时兜底回 -12903（不能放 teardown，resume 会调它）。
  - 异步 dfrm：在途帧（未交出 + Demt 已发未回复，超 2 s 不计）>3 时压住回复。只按 kext 侧计数不够，guest 的 Demt 队列会落后。
  - IdleDrain / 淘汰前 drain / 积压放弃时间层只在显示顺序下运行。
- 测试框架：16 个场景全过（新增 async、nodelay、同步 dfrm 不得早于 Demt、异步在途上限）。
- 真机：航拍会话混用 `,dfl 0` 与 `,dfl 9`（异步+1xRealTime）；进程不再重启；宿主每约 2 分钟开一个 4K 会话、连续播约 30 s；
  计数 in 1884 / out 1842 / dropped 42 / errors 0。开机后头两个会话只预读首帧就被 dinv，真正播放在开机约 290 s 才开始，原因未查。

## 下一步

1. ~~P4：WindowServer 去掉 CPU 转换~~ **11-04 晚核实 3623549 已生效**：航拍播放中 WindowServer 无 32–64 MiB 转换块，
   P010 池 surface 直接导入（41 块 16–32 MiB 用户块）。工具 `/tmp/k27-gpumem.py`（PHONE=…）。端到端已是零拷贝。
2. （可选）CPU 基线：要用 `stage-gpu-plugin.py --top` 打 Data 补丁，需 VM 停机约 10 分钟。11-04 晚尝试时拉 Data 期间 VM 被重新启动，
   快照不一致，补丁已作废（out/tmp/store-patch.*.inconsistent，未写入手机）。
3. 查开机后 290 s 才开始播放是否正常（锁屏行为还是 kext 问题）。

## 收尾清单

- [x] 撤掉 Data 里的 log-stream 启动项（11-06 已撤：它在转发 audiomxd 登录前死循环的错误，占约 1.4 核）。
- [x] 0010 无诊断代码；`droidvm-vt-direct` 默认 1（直连）。
- [x] 清理 android.rs 的 DIAG 代码。
- [x] 提交 crosvm/virtio-media 改动和补丁 0004–0011。
- [ ] 重命名 0005（实际是 4096 帧，不是 1024）。
- [ ] 处理 guest 磁盘将满的警告。
- [x] 更新记忆。
- [ ] 手机上旧脚本（hostmon2、/tmp/vmwatchdog2.sh）是否还在跑，未核实。

## 常用命令

```
# kext 改动先跑测试框架，再生成补丁、编 kext + KC
(cd research/vthost-harness && TMPDIR=$PWD/out/tmp ./build.sh && ./suite.sh)
bash k27/build-native-video.sh   # 只用 patches/droidvm-video，不再用 research/debug-2026-11-03
K27_NO_BOOT=1 MACOS_DISPLAY=1 MACOS_GPU=1 MACOS_VIDEO=1 bash k27/try.sh 0
# 启动盘（先核对种子：手机存储头 block1+24 的 8 字节 == 1aa0a464ac13866f）
PHONE=100.102.230.78:33445 MACOS_MEDIA=1 MACOS_MEDIA_VIDC=1 MACOS_DISPLAY=1 MACOS_KERNEL=$PWD/out/k27/kc-k27.bin MACOS_TAG=27.0.1 \
  MACOS_GPU=1 MACOS_VIRTIO_GPU=1 MACOS_NET=1 MACOS_DATA_SEED=$PWD/out/metal/stage/scratch-data.img \
  MACOS_TRUSTCACHE=$PWD/out/metal/stage/kernel.macho.trustcache MACOS_LP_SIP0=0x2 MACOS_BOOT_MANIFEST_HASH=1 \
  python3 scripts/droidvm-app.py boot --kernel-arg=-v --kernel-arg=vm_compression_limit=1572864 --kernel-arg=rootauth=0 \
  --kernel-arg=droidvm-vt-paravirt=1 --kernel-arg=stderr-log=1 --kernel-arg=droidvm-vt-direct=1 --kernel-arg=msgbuf=1048576
PHONE=100.102.230.78:33445 MACOS_TAG=27.0.1 python3 scripts/droidvm-app.py start   # failed 就多试几次
# 日志
bash research/vt-probe/collect.sh 600          # guest msgbuf → /tmp/k27-all.txt
adb shell "su -c 'grep -a msm_vidc /data/data/cn.classfun.droidvm/cache/console_3307dca0-8a10-59af-8abf-1a1501cd5b40_stderr.log'"
# Data 打补丁（不换种子）
rm -f out/metal/stage/store-patch.*; 拉 data-store.img → out/tmp/
python3 scripts/stage-gpu-plugin.py [--log-stream PRED] --base out/metal/stage/scratch-data.img --store out/tmp/data-store.img out/metal/plugin/NativeAdrenoMetal.bundle
MACOS_MEDIA=1 python3 scripts/droidvm-app.py store-patch
```
