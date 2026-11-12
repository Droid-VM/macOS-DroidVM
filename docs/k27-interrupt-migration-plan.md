# macOS 剩余轮询路径的中断迁移计划

日期：2026-11-12。范围：App 虚拟输入、GPU/光标、视频、音频和 VBL。
已有 PCI 块设备、网卡和 xHCI 保持当前中断路径。

目标是减少无工作时的周期唤醒和完成延迟，按设备决定是否迁移 PCI/MSI-X。
不把接入中断等同于 GPU 运算加速，也不预先承诺性能提升数字。
遵循用户约束：不计算 SHA，不进行烟测，不添加非必要测试或防御性代码；
每阶段仅做相关定向验证，确认修复后分组提交，保留无关工作区改动。

## 决策依据

- [Virtio 1.2 §4.1/§4.2](https://docs.oasis-open.org/virtio/virtio/v1.2/virtio-v1.2.html)：
  MMIO 支持 used-buffer/config 中断，通过 InterruptStatus/InterruptACK 处理；
  PCI MSI-X 支持队列到向量映射，减少 ISR 访问，并允许向量分散到 CPU。
- [Linux Virtio 文档](https://docs.kernel.org/driver-api/virtio/virtio.html)：
  设备协议与 PCI/MMIO 传输独立，队列完成通过传输注册的中断回调处理。
- [Linux virtio-gpu](https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/virtio/virtgpu_kms.c)
  分别注册 control/cursor 完成回调；
  [virtio-snd](https://github.com/torvalds/linux/blob/master/sound/virtio/virtio_card.c)
  为控制、事件、播放和录音队列注册回调。
- [MSI 驱动文档](https://docs.kernel.org/PCI/msi-howto.html)：独立 MSI-X 向量可配置不同 CPU。

## P1：虚拟输入 PCI MSI-X（首先实施）

现状：四个 IOPCIDevice 上的 DroidVMInput 各有 4 ms 轮询线程；
保留 Apple multitouch/HID 描述符和输入报告协议。

实施：每个 PCI function 请求一个 MSI-X 向量，event queue 映射到 table entry 0；
未使用的 status queue 和 config 中断保持 NO_VECTOR。
IOInterruptEventSource 在 work loop 中批量回收 used ring、报告 HID 事件并补回缓冲；
PCI 路径不启动周期轮询线程、不读取 INTx ISR。
启动时通过同一 work loop 补收切换通知前已完成的缓冲。
原始 ECAM 启动模式继续使用现有轮询，不为 MSI-X 失败增加静默轮询回退。
补齐中断、work loop 及 DMA 资源在启动失败和停止时的清理。

定向验收：四类输入绑定成功，PCI capability 的 MSI-X enable/table/queue vector 正确；
实际键盘、相对鼠标、绝对指针、多点触屏有报告，空闲时没有 4 ms 输入轮询；
对应 SPI 及目标 CPU 计数随输入增长，停止输入后停止持续增长，无队列积压或内核异常。
如设备断连，先完成可审阅的代码、构建及 KC 链接，部署和真实输入验收标记待完成。

## P2：GPU 完成及独立光标

先保留 virtio-mmio，接入设备 SPI：正确实现电平中断、status/ACK 与 Gunyah resample；
当前 DroidVMGicMsi 是 MBI 边沿控制器，不能直接套用到 MMIO 电平线路。
控制队列完成统一回收，按 ticket/fence 唤醒等待者；移除常驻完成轮询，
保留提交时已完成结果的直接检查。
光标队列通过完成通知回收命令存储，改为可合并位置更新的异步提交；
释放图像资源前仍须保证相关命令完成。
核对现有 Metal fence 的等待对象，区分 virtqueue 完成与宿主共享内存中的 GPU fence，
后者若无完成队列通知，需要补充通知协议，不能仅切换队列 IRQ 就宣称全部解决。

定向验收：桌面/Metal 工作、光标位置与边缘、图像切换正常；有工作时完成中断增长，
空闲时无周期 fence 等待；验证空闲后首次提交及连续提交没有丢唤醒。
涉及 GPU 的实施记录统一写在 `/home/qiuqiu/crosvm/win3d/docs`，本计划只链接记录。
之后依据 IRQ 频率、完成延迟、CPU 开销决定是否另迁 PCI/MSI-X，
如迁移则分离 control/cursor 向量，并核对实际 SPI 是否独立。

## P3：视频编解码

保留 virtio-mmio，命令完成和事件队列接入 SPI，移除工作时 1 ms、空闲时 50 ms 轮询。
会话工作线程继续基于条件等待，确认事件已发布再唤醒；停止/排空会话时保证资源生命周期。
定向验收已有播放/编解码路径、会话停止及空闲后首次任务；无事件时不周期扫描队列。
只有单 IRQ 分发成本或队列竞争成为实际瓶颈时，才考虑 PCI/MSI-X。

## P4：音频

保留 virtio-mmio，控制、事件及 PCM 完成队列通过 SPI 回收和通知。
音频 HAL 的时钟及周期推进单独评估，不将其全部视为可删除的轮询。
定向验收播放/录音、开始/停止、欠载及空闲后恢复，无新增爆音或持续空闲唤醒。
暂不迁移 PCI/MSI-X。

## P5：VBL

保留当前定时器。只有宿主提供可用于显示节奏的真实刷新/呈现反馈时，才替换合成 VBL。
GPU 命令完成不能直接作为 VBL；MSI-X 本身不提供屏幕刷新时刻。

## 部署规则与进度

更新沿用当前独立光标及 USB 存储支持。构建 KC 必须设置 `K27_NO_BOOT=1`；
正常关闭 guest，确认卸载完成及 CPU halted，再停止 App 并确认 STOPPED 后替换启动镜像。
不重建或覆盖 Data 种子，不在 U 盘写测试文件。SPI 编号和 CPU 以当次启动为准。

| 阶段 | 状态 |
| --- | --- |
| P1 输入 MSI-X | 四路绑定及空闲验证通过，用户确认触摸正常；相对鼠标/绝对指针仍待单独操作验收 |
| P2 GPU/光标 | P2a/P2b 已部署，用户确认鼠标、拖动、四边及换形状全部正常；用户态 seqno/WAIT_ANY 检查保留 |
| P3 视频 | 已部署验收：1020 帧解码、两轮合计 120 帧编码通过；空闲 SPI 不增长，恢复任务无丢唤醒 |
| P4 音频 | SPI 47 已部署；播放/录音、重复启停及空闲后恢复已验证，用户确认提示音正常；录音听感与真实设备事件待验收 |
| P5 VBL | 保留定时器 |

### P1 当前实施记录

已将 PCI 路径的 4 ms 轮询替换为每个 function 一个 MSI-X 向量和 IOWorkLoop。
首次部署发现队列向量在 DRIVER_OK 后写入，被 crosvm 已激活队列拒绝；
已调整为完成向量映射及中断安装后才发布 DRIVER_OK，不修改宿主队列实现。
修正版启动日志确认 mouse、tablet、keyboard、touch screen 四个 function 的 vector 0 启用；
IORegistry 四个 DroidVMInput 均为 active，InputNotificationMode=MSI-X，
AppleMultitouchDevice 继续取得显示 UUID，8 个 CPU ready，内核 debugger entry 为 0。
原始采集仅保留本地，不纳入版本控制。
本次启动 mouse/touch/tablet/keyboard 分别使用 SPI 83/93/92/82；
空闲两次采样四路中断增量均为 0。
用户随后确认“触摸正常”。操作后 touch SPI 93 累计 194 次，全部在 CPU 2；
keyboard SPI 82 累计 12 次，在 CPU 1；kernel debugger entry 仍为 0。
触摸已通过真实操作验收；相对鼠标/绝对指针本次 SPI 计数仍为 0，不据此宣称两条路径已验收。

P2 的实现及验证记录见 [GPU 完成中断迁移](../../win3d/docs/presentation/macos-gpu-interrupts-2026-11-12.md)。
P3 见 [视频完成中断记录](k27-video-interrupts.md)。

P4 见 [音频完成中断记录](k27-audio-interrupts.md)。
