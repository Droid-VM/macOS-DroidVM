# macOS GPU 完成中断迁移

本记录对应 [P2 计划](../docs/k27-interrupt-migration-plan.md)。

## P2a：virtio-mmio 完成中断

显示和 Metal 3D 使用 `DroidVMVirtioGpu.cpp` 的同一个控制队列。
带 fence 的提交由宿主在 GPU fence 完成后归还 used ring；因此这类完成可以直接由队列中断通知。
此处的源通过 `k27/build-native-display.sh` 导出，再应用 `patches/droidvm-display`；
`overlay/droidvm/drivers/NativeVirtioGpu` 是另一条 PCI 路径，不是本次正在运行的显示传输。

ADT 从 FDT 对应 MMIO 节点的 interrupts 导出 gic-spi，当前为 INTID 46。
ArmCpu 将它配置为电平触发；顶半部先 mask SPI 再通知 IOWorkLoop，
工作循环 ACK Virtio InterruptStatus、回收控制队列、唤醒等待者，然后重新启用 SPI。
保持宿主现有电平线路及 resample，不复用 PCI 的边沿 MBI 控制器，不需要更新 crosvm。

控制队列、Metal waitFence、客户端 drain/待提交上限以及显示 copyLoop 的 GPU 等待，
改为完成序号和带超时的条件睡眠。检查条件前取得序号，睡眠前在同一把传输锁下复查，
避免完成恰好发生在检查与睡眠之间时丢失唤醒。回收 done slot 时也通知等待空位的提交者。
保留提交时读取内存 used ring 的直接检查，不再以 100 微秒定时器驱动这些等待。

光标队列同样启用完成中断；P2a 中先保留同步等待归还，随后 P2b 将 MOVE 改为异步。
64×64 裁剪、桌面/物理显示坐标换算与独立 Surface 路径保持现有实现。

## 验证与剩余工作

构建显示驱动和 KC 链接通过，正常卸载 APFS 并停机后部署启动镜像；Data 未重建。
启动日志确认 level SPI 46 completion notifications enabled，WindowServer 与 AGXAccelerator 恢复。
两次采样 GPU 完成命令从 884 增到 8055，SPI 46 同期增加 6401；
错误、超时、stray used-ring 条目及内核 debugger entry 均为 0，采样时 in-flight 均为 0。
桌面仍有实际命令提交，这组数据不能当作 GPU 完全空闲时的中断测试或性能对比。

原始记录：[启动摘录](../research/gpu-interrupts-2026-11-12/boot.log)、
[初次采样](../research/gpu-interrupts-2026-11-12/initial.json)、
[后续采样](../research/gpu-interrupts-2026-11-12/later.json)。

下一批工作是光标异步提交及移动合并，完成前不能复用命令缓冲或释放相关图像资源。
还需检查 Mesa/Metal 用户态的共享内存 ccmd seqno 等待，不能将其与带 fence 的队列完成混为一谈。
保留现有 VBL 定时器。实际光标边缘、位置、换形状和桌面交互仍需操作验收。

## P2b：光标移动异步提交

MOVE_CURSOR 返回时不等待 used ring；一个命令缓冲在设备占用期间保持不变，
另保留一个尚未发送的最新位置。新位置可覆盖尚未发送的位置，不能覆盖 DMA 中的命令。
工作循环收到完成后检查 cursor used index，再发送待处理位置。
UPDATE_CURSOR 和隐藏仍同步等待，先排空旧 MOVE，再提交图像/隐藏并等其完成，
保留既有停止路径先隐藏后释放资源的跨队列顺序。
光标的坐标、裁剪和大小未调整。

本批还补齐 abandon 已完成 slot 时的空位通知；关闭客户端释放 slot 后，
等待空位的提交者能及时醒来。

共享内存检查结果：实际 Darwin 用户态后端为
`sources/UniXNU-turnip/.cache/mesa-work/src/freedreno/vulkan/tu_knl_darwin_virtgpu.cc`。
`vg_ccmd` 先通过无 fence 的 EXECBUFFER 同步调用内核，内核 `submitCommand` 已等待控制队列归还，
随后用户态仍检查共享内存 seqno，超过短暂自旋后以 50 微秒间隔检查，次数有上限。
本批保留这段响应确认，没有替换用户态 dylib；Vulkan WAIT_ANY 的 200 微秒检查也仍存在。
这两段不能列作已删除，但也没有无任务时常驻扫描的线程。

P2b 的显示驱动及 KC 构建通过，已部署。首末两次采样完成命令为 3325/14210，
错误、超时、stray 及内核 debugger entry 均为 0，in-flight 均为 0。
日志确认 64×64 光标、2 次图像更新；截至采样时 MOVE 仍为 0，故异步移动和合并仍待实际操作验收。
记录：[异步版启动](../research/gpu-interrupts-2026-11-12/async-boot.log)、
[显示日志](../research/gpu-interrupts-2026-11-12/async-display.log)、
[初次采样](../research/gpu-interrupts-2026-11-12/async-initial.json)、
[后续采样](../research/gpu-interrupts-2026-11-12/async-later.json)。

初版 P2a 提交为 `959c3f5`。部署没有更新 Metal 用户态库或 crosvm，
未计算摘要，未进行烟测或新增测试代码。重新运行 ADT 生成路径确认同一 FDT 能导出 SPI 46；
当前部署在原启动树上仅补充该属性，保留现有 CPU/时间基准等设置。

## 用户操作验收

用户对鼠标移动、点击、窗口拖动、屏幕四边及指针换形状回复“全部正常”。
操作确认后的采样累计完成 72905 条 GPU 命令，错误、超时、stray、内核 debugger entry
仍全部为 0，in-flight 为 0，SPI 46 累计 67755 次。
见[验收后采样](../research/gpu-interrupts-2026-11-12/user-verified.json)。
用户操作验收通过；本次提取到的最近光标日志仍为 0 moves，未据此量化 MOVE 合并次数或性能提升。
P2b 提交为 `62d65a2`。下一阶段是 P3 视频完成及事件队列中断；
用户态 seqno 和 WAIT_ANY 检查仍保留，后续需单独评估。
