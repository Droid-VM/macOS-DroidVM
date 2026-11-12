# virtio-media 命令及事件中断

2026-11-12，迁移计划 P3。保留 virtio-mmio，未迁 PCI/MSI-X。

## 实现

ADT 从 FDT 的对应 virtio-mmio 节点导出 gic-spi；本次 decoder/encoder 分别为 SPI 48/49。
两个队列均启用 used-buffer 中断。中断处理函数 ACK InterruptStatus，在 GIC EOI 前清除电平源，
唤醒命令等待者及事件线程，继续使用宿主现有 resample 路径。

命令串行锁仍跨一次命令持有，等待者在检查 used index 前登记等待，以免检查和睡眠之间丢失唤醒；
保留原有 5 秒超时。事件线程有 pending 标记，无任务时无限期睡眠，取消 1 ms/50 ms 扫描及 fast 状态。
事件线程在传输锁下复制事件并补回 DMA 缓冲，释放传输锁后才调用会话 sink。
这样会话持锁发起命令时，事件回调不会持有传输锁反向等待会话锁。
会话原有 drain、停止及空闲资源回收期限保留。

源由 `k27/build-native-video.sh` 导出，补丁为
`patches/droidvm-video/0013-media-completion-interrupts.patch`；提交 `d079a8e`。

## 启动时序修复

加入视频 SPI 后，首次启动暴露 PCI 向量早于 GIC 初始化注册的问题：
根盘的 SPI 97 挂接返回 NotReady，系统停在根盘前。
ArmCpu 现在在注册线程等待 GIC 就绪，并用互斥锁串行修改 SPI 表及共享 distributor 配置。
锁在可分配内存的设备注册线程初始化；GIC 初始化只发布 ready，不能在关中断上下文分配锁。
首次修正将分配放在 GIC 初始化，触发 zalloc 关中断断言；已移出并重新构建部署。
最终启动恢复桌面和根盘 I/O，debugger entry 为 0。对应修复提交 `fe000b4`。

## 定向验证

显示及视频驱动、内核和 KC 构建通过；未运行 cargo check、烟测、摘要计算，未新增持久测试代码。
正常停机的部署先确认 APFS 卸载及 CPU halted；失败启动尚未挂载根盘，或已 panic，停止 App 后替换镜像。
启动镜像沿用已验收的输入 MSI-X 和异步光标，Data 未重建。
guest 直连 SSH 当时不可达，使用宿主 192.168.1.203:2223 转发完成验证。

复用已有 `research/vt-probe`，解码输入为其内嵌的两段 HEVC 素材。
编码沿用同一探针的 vtEncodeProbe 函数，以临时入口依次调用 H.264/HEVC，各 640×360、30 帧，
没有添加常驻或入库测试。guest 临时文件位于 `/private/var/tmp/vt-irq-*`。

| 场景 | 输出 | 失败 |
| --- | --- | --- |
| Main10 720p → 420v | 30 帧 | 0 |
| Main10 720p → x420 | 30 帧 | 0 |
| HEVC 4096×2160 → 420v | 480 帧 | 0 |
| HEVC 4096×2160 → x420 | 480 帧 | 0 |
| H.264 硬件编码 | 30 帧 | 0 |
| HEVC 硬件编码 | 30 帧 | 0 |

编码探针同进程的计数累计，因此 HEVC 行显示 60 frames out（含前面的 H.264 30 帧），
不是 HEVC 单独输出 60 帧。内核累计输入/输出均为 1080 帧，2376 条媒体命令，
2166 个 DQBUF、10 个 EVENT、0 个 ERROR；传输超时、会话错误和 debugger entry 均为 0。
4K 420v 路径出现既有的 Metal YCbCr surface texture refused 提示并转 CPU 格式转换，
最终 480 帧全部输出；不把这次验证当作渲染加速或性能提升证明。

原始记录：[解码](../research/video-interrupts-2026-11-12/decode.log)、
[编码](../research/video-interrupts-2026-11-12/encode.log)、
[解码后计数](../research/video-interrupts-2026-11-12/after-decode.json)、
[编码后计数](../research/video-interrupts-2026-11-12/after-encode.json)。

空闲两次采样相隔约 92.2 秒，SPI 48/49、媒体命令和帧计数的增量均为 0。
随后重新创建 H.264/HEVC 编码会话，各输出 30 帧、失败 0；最终累计输入/输出均为 1140 帧，
2556 条命令，传输超时、会话错误及 debugger entry 仍为 0。
本次验证覆盖新会话启动、工作、停止及空闲后再启动；不声称已覆盖所有编解码器或长时播放。
见[空闲前](../research/video-interrupts-2026-11-12/idle-before.json)、
[空闲后](../research/video-interrupts-2026-11-12/idle-after.json)、
[恢复编码](../research/video-interrupts-2026-11-12/resume.log)、
[恢复后计数](../research/video-interrupts-2026-11-12/after-resume.json)。
