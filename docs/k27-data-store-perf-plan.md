# k27 Data 盘性能优化方案（2026-11-11）

## 现状（11-11 实测，主实例，`out/storage-internal-2026-11-11/probe/diskbench.c`，1 GiB 文件，F_NOCACHE）

| 项目 | guest | 手机 /data 直测 |
|---|---|---|
| 顺序写 1 MiB | 308 MiB/s | 1.3 GB/s（带 fsync） |
| 顺序读 1 MiB | 262 MiB/s | 1.8 GB/s（清缓存后），命中缓存 4.3 GB/s |
| 4K 随机读 单线程 / 4 线程 | 16.2k / 17.9k IOPS | |
| 4K 随机写 单线程 / 4 线程 | 9.4k / 8.2k IOPS，最大 156 / 261 ms | |
| 4K 写 + 每次 fsync | 1.2k IOPS，平均 0.82 ms | |

瓶颈在 guest：
- `overlay/kext/DroidVMDataStore.c` 全局一把锁，一次只发一个请求（`DROIDVM_STORE_QUEUE 8` 只是环的大小），轮询等待；单个请求最多 32 页（128 KiB），数据还要经过一个跳板缓冲区。顺序读 1 GiB 用 3.9 s，折合每 128 KiB 请求约 0.48 ms。
- NativeRamBlock 直连模式下，整个请求都拿着磁盘锁；每次写都是"数据块 + 位图块"两个同步请求（写穿）。
- 4 线程和单线程的 IOPS 差不多，延迟却成倍增长：所有请求在同一把锁后排队。
- crosvm 的 virtio-block（`devices/src/virtio/block/asynchronous.rs`）用 `FuturesUnordered` 并发处理请求，宿主侧不是瓶颈。

## 上游已有的优化

| 来源 | 提交 | 内容 | 我们 |
|---|---|---|---|
| Droid-VM/UniXNU-droidvm `package/DroidVMDataStore.c` | 45052cd（11-05） | 等待改为先自旋 50 µs，再以 50 µs 为步长睡眠（原来是自旋 200 µs 后 IOSleep(1)，超过自旋时间的请求至少白等 1 ms，后面的请求全部排队）；加等待直方图 `droidvm_store_wait_hist`，自旋和步长可以 poke | 没有（我们的副本基于 670f95b） |
| UniXNU/RamBlock | aad2a16（11-08） | 直连 Data 存储改为写回：数据页走写缓存，位图位留在内存里，等 synchronize 或首次写后 5 s 的空闲定时器才落盘（先 sync 页，再写位图，再 sync）；需要后端提供 `native_ufs_store_write_cached`，`data-fua=1` 可退回写穿 | 没有 |
| UniXNU/RamBlock | 525abe5（11-09） | 直连模式下请求并发：读不拿锁；写持页区间锁 + 共享 flush 锁，提交位图时只拿一下短锁；flush 拿独占锁；8 个暂存缓冲池；没写过就不发 flush；带 `Test/concurrent.cpp`（TSan）和 `Test/writeback.cpp`（掉电模拟） | 没有 |
| UniXNU/RamBlock | 60a54ce / 8732b3e / 737f6da / 4be2d7e / d4d22d9 / 8c83f51 | reset 一次写清位图；报告固态；导入后归还 packed seed 内存；只在 Install/boot 时重建 store；gpu addon；启动参数去掉 `sheng-` 前缀（我们没用 `sheng-data-*`） | 没有；我们本地 `sources/UniXNU/drivers/NativeRamBlock` 和上游 7194961 逐字相同 |
| Droid-VM ipados27 `patches/VirtioMmioBlock/0002–0006` | — | NativeVirtioBlock（只读校验根盘）：16 个请求槽同时在途、传输提到 256 KiB、前 150 µs 每 2 µs 轮询、可选中断等待 | 方案可以照搬到 DroidVMDataStore；中断等待不采用（Gunyah INTx 会丢，见记忆 gunyah-intx-idle-vcpu-latency） |
| UniXNU/VirtioMmioBlock | 4e1013e | 只有校验策略头文件，无性能改动 | — |

关键缺口：上游 RamBlock 的并发要后端也能并发才有用。UniXNU 的后端是 NativeUfs（直接驱动手机 UFS），我们的后端是 DroidVMDataStore，仍然是一次一个请求。

## 方案

### P0 计量（先做，零风险）
- 移植 45052cd 的等待直方图，再在 NativeRamBlock 里统计每个请求的锁等待、设备时间和字节数（上游 aad2a16 已带 "time, gate wait and bytes"）。
- 用 diskbench 跑基线，加一个 4K 读 x16 的并发档；数据由 `scripts/rig-dmesg.py --peek` 读出。

### P1 移植 DroidVMDataStore 45052cd（小改动）
- 预期：消除"超过 200 µs 就睡满 1 ms"的长尾，fsync 和小写延迟下降。

### P2 NativeRamBlock 跟上游 RamBlock 737f6da
- 用上游 NativeRamBlock.cpp / PersistOverlay.h / DirectDisk.h 替换本地这几个文件（SparseDisk.h、SeedDisk.h 没有差别）。
- `scripts/build-native-ram-block.py` 的字符串补丁要逐条核对锚点：在 IOBSD 匹配后再发布、内置 SSD 特性（和上游 8732b3e 重叠，二选一）、删 OSInternal 的线程、NativeRamBlockPartition。
- DroidVMDataStore 补上 `native_ufs_store_write_cached`：virtio-blk 没有 FUA，crosvm 写完页缓存就回复，所以它和 `write` 是同一条路径；`native_ufs_store_sync` 继续用 VIRTIO_BLK_T_FLUSH。有了它，RamBlock 就会走写回，随机小写不再每次额外写一个位图块。
- 掉电语义：上游保证"盘上的位一定指向已落盘的页"，崩溃最多丢最近一次 flush 之后的写；和现在宿主页缓存 + 5 s flusher 的语义同级。

### P3 DroidVMDataStore 多请求在途（主要收益）
- 照 ipados27 0002 的结构：16 个槽，每槽 3 个描述符、自己的请求头/状态和暂存缓冲；锁只保护环和槽位掩码；等待方放下锁，轮询自己的槽，顺便回收所有已完成的槽。
- 队列大小提到 64 个描述符；暂存缓冲改为 IOMallocContiguous（16 × 256 KiB = 4 MiB），或者继续用静态区。
- 配合 P2 的并发 RamBlock：多个线程的读写可以同时在途。

### P4 更大的传输
- 单个请求 128 KiB → 256 KiB（RamBlock 的 kStagePages 和 DataStore 的暂存缓冲同时改）；一个大请求拆成若干块同时发出（参考 0002 的 batchLimit 8）。

### P5（可选）去掉跳板拷贝
- 对页对齐的请求，用 IOMemoryDescriptor::prepare + getPhysicalSegment，把调用方缓冲区的物理段直接做成 virtio 描述符链（guest 物理地址 crosvm 可以直接访问）。只有 P3/P4 之后 CPU 拷贝仍是瓶颈时才做。

### 不做
- 中断等待：Gunyah 对 WFI 状态的 vCPU 会丢 INTx（记忆 gunyah-intx-idle-vcpu-latency），保持"短自旋 + 短步长轮询"。

## 验证与安全
- 主机侧先跑上游 `Test/concurrent.cpp`（加 -fsanitize=thread）和 `Test/writeback.cpp`。
- 先在 `MACOS_INSTANCE` 克隆实例上测，不碰主实例的 data-store.img。每个阶段跑 diskbench、正常开关机两次，再做一次强杀 VM 后重启，检查 fsck 和桌面。
- 目标：顺序读写 ≥ 800 MiB/s；4K 读 x4 ≥ 40k IOPS；4K 写 ≥ 15k IOPS；写的最大延迟不比现在差。
