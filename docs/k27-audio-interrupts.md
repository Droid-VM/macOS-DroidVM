# macOS virtio-snd 完成中断

2026-11-12，P4。保留 virtio-mmio，音频使用 FDT 对应的电平 SPI 47。

实现见 `patches/droidvm-audio/0005-completion-interrupts.patch`，
ADT 生成器从 sound MMIO 窗口对应的 FDT 节点写入 `gic-spi`。
中断入口先 ACK InterruptStatus，再唤醒控制等待者和完成线程；入口不获取 PCM mutex。
四个队列均启用 used-buffer 通知，事件队列预投递 16 个八字节缓冲。

控制命令在检查 used index 前登记等待，使用两秒截止时间，移除一毫秒睡眠轮询。
完成线程仅在中断通知后运行，回收 TX，收集 RX 到就绪槽队列，统计并补回事件缓冲。
播放和录音引擎只提交 PCM 或取走已就绪的录音槽，PCM mutex 保护引擎与完成线程共享的索引。
HAL 的 48 kHz 时钟和每 240 帧（5 ms）调度保留；无运行音频流时引擎退出。
HAL 在 transport 准备完成后才设置时钟起点。

STOP 只暂停 crosvm 流，不保证归还全部描述符。因此停止时发送 STOP、RELEASE，
再按完成通知等待已提交描述符全部返回；下次启动发送 PREPARE、START。
这替代了输出 200 次一毫秒回收扫描和输入固定等待 20 ms 后直接重置索引。
控制命令不持有 PCM mutex，避免完成线程被命令等待阻塞。

## 定向验证

沿用 Data，正常关闭系统并确认卸载及 CPU halted 后才更新启动镜像。
音频原生构建和 KC 链接通过，`K27_NO_BOOT=1`，未启动构建脚本的自动验收。
未计算 SHA、未做烟测、未添加仓库测试代码。

真实 Core Audio 播放使用系统 `afplay` 和系统提示音；录音使用临时 AudioQueue 输入程序，
仅计数、不保存音频内容。Android 原本未授予 DroidVM 麦克风权限，初次 PREPARE 被宿主拒绝，
API 仍返回静音，故不能仅凭 AudioQueue 回调认定真实录音成功。
临时授予权限后的复测确认驱动 RX 实际回收 1100 个周期、264000 帧，
控制超时、PCM 状态错误、内核 debugger entry 均为零。

首次部署还发现 Android AudioTrack 回调等待优先级提升超时：AAudio 的 requestStart 异步返回后，
平台回调尚未开始消费，guest 已开始推进，造成 TX 队列满和端点丢弃日志。
这与完成 IRQ 是否收到是不同问题，不能用零命令超时替代音质验收。
宿主 `android_audio` 随后改用 `AAudioStream_waitForStateChange` 等待输出端点进入 STARTED，
才返回成功。等待状态通知，不增加周期探测线程；启动失败或两秒未完成时沿用启动失败返回。
宿主使用 `/home/qiuqiu/crosvm/build_crosvm.sh` 构建。

guest 中断版的空闲定向采样跨约 89.6 秒，SPI 47、TX/RX 周期、HAL 周期增量均为零，
错误和超时也未增长。
宿主修正版已部署，首轮播放 Hero、Glass 后，再连续六次 Hero 启停，共八次播放，
驱动 TX 2768 个周期、播放 HAL 648960 帧；录音 RX 1016 个周期、243840 帧，
临时 AudioQueue 程序收到 242688 帧并正常停止。
TX 丢弃、RX 空读、PCM 错误、控制超时、内核 debugger entry 均为零。
HAL late 累计 1 次，未把它伪称为调度完全没有迟到。
宿主日志没有再出现 endpoint took nothing 或 PCM_PREPARE failed。
这些计数证明队列完成、启停及数据推进，不替代人工听音的爆音/音质判断。

宿主启动等待修复提交：crosvm `14084603f`；guest 实现见本文开头的补丁路径。
构建保留了工作区原有 `0004-ring-wrap.patch`，该文件仍为原作者未提交改动，本次未代为提交。

原始采集仅保留本地，不纳入版本控制；关键结果汇总于本文。
事件队列已接入，但本次未观察到设备事件，因此不宣称真实 XRUN 事件注入或事件类型全部验收。

## 空闲后恢复及最终状态

宿主修正版空闲采样跨 85.5 秒，SPI 47、TX/RX、HAL 周期增量均为零。
随后恢复录音和播放，RX 增加 1005 周期、TX 增加 367 周期，
错误、控制超时、TX 丢弃和内核 debugger entry 均为零；RX 空读增加 2 次，
HAL 按已有行为为未就绪周期填静音，不宣称录音周期完全无欠载。
最终累计 TX 3135 周期、RX 2021 周期。
本轮 SSH 命令超时，故不以命令退出状态作为通过依据；实际计数证明两方向恢复及停止。
Android RECORD_AUDIO 权限已恢复到验证前的未授予状态；以后使用麦克风须在 App 中授权。
收尾时 VM 为 SUSPENDED，保持该状态。

P4 的中断迁移、队列回收、启停和空闲后恢复验证完成；提示音人工听音已确认正常，录音听感及真实设备事件仍未验收。
P5 按原计划保留合成 VBL 定时器，等待宿主真实呈现反馈，不以 GPU 完成中断替代刷新时刻。

## 用户听音验收

2026-11-12，guest 已处于 RUNNING。通过系统 afplay 顺序播放 Hero、
0.2 倍速 Hero、0.2 倍速 Submarine 和 Glass，命令正常完成。
用户在被询问有无爆音、断续或开头缺音后确认“声音正常”。
本次仅覆盖提示音和变速播放，不宣称长时间音乐播放或录音听感已验收。

本轮 TX 提交增加 3588 周期，HAL 播放增加 853440 帧；
控制超时、PCM 错误及内核 debugger entry 增量均为零。
TX 丢弃增加 2 周期（10 ms），HAL late 增加 17 次；
宿主另有一次 endpoint took nothing for 10ms、丢弃 192 帧的警告。
因此用户听感正常不等于播放路径完全无丢帧，也不据此宣称持续负载无欠载。
麦克风权限保持未授予，本轮没有开启录音。原始日志及计数仅留本地，未提交。
