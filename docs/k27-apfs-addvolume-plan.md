# 宿主侧往已有 APFS 容器加卷（计划，2026-11-10）

目的：让镜像生成流程（docs/k27-real-disk-layout-plan.md P6）不再依赖一台在跑的 macOS。宿主上直接把 IPSW 的 os.raw 容器（只有一个原版密封 System 卷）改成真机结构：System + Data（同一卷组）+ Preboot + xART，可选 Hardware、VM。之后再用 Linux apfs-rw 填内容，打包成种子和 store。

## 现成项目调研（11-10）

没有任何开源工具能往已有容器里加卷：

| 项目 | 能力 | 能借用的部分 |
|---|---|---|
| linux-apfs/apfsprogs（sources/apfsprogs） | mkapfs 只在新容器里建一个卷，不能设角色和卷组；apfsck 能做整容器一致性检查 | 用 mkapfs 生成正确的空卷对象；用 apfsck 验证结果 |
| linux-apfs/linux-apfs-rw（sources/linux-apfs-rw） | 内核驱动，能读写已有卷（`vol=N`），有完整的分配、omap、B 树、checkpoint 写入；不能建卷 | 填 Data 和 Preboot 的内容 |
| ironpark/zapp pkg/macfs/apfs（Go） | 从零写一个单卷容器，不能改已有容器 | 无 |
| libyal/libfsapfs、deploymenttheory/go-apfs、apfs-fuse | 只读 | 无 |
| Paragon APFS for Linux | 闭源读写驱动，不能建卷 | 无 |

格式依据：
- Apple File System Reference（developer.apple.com/support/downloads/Apple-File-System-Reference.pdf）：`apfs_volume_group_id`、`APFS_FEATURE_VOLGRP_SYSTEM_INO_SPACE`、`UNIFIED_ID_SPACE_MARK`、`FIRMLINK_EA_NAME`、卷角色。
- jtsylve.blog 的 APFS Volume Superblock 一文：卷组里 Data 的对象号从 0x10 起，System 的从 0x0FFFFFFF00000010 起。
- 已在用的 scripts/grow-data-store.py：容器扩容、spaceman 布局按 APFS 的 spaceman_sanity_check 校验，已实测 macOS 能挂。

## 已核实的事实

- os.raw 容器只有一个卷：“Macintosh HD”，System 角色，不在卷组里，密封。
  - 它的 inode 号已经在 System 段（`/System` 是 0x0FFFFFFF00000017 一类），和现在 diskutil 建的 DroidVMSystem 一样。所以入组不用改任何 inode，只改卷超级块：组 UUID 加 VOLGRP 特性位。
  - 它自带全部 firmlink（目录上有 `com.apple.fs.firmlink`），源目录为空，`var`/`etc`/`tmp` 链接齐全，`/System/Cryptexes/*` 指向 Preboot。
- apfs_boot_util 的最小需求：
  - 必须有 Preboot 和 xART，xART 所在容器的 IOMedia 要带 ISC Content Hint（NativeRamBlock 已经补上）；
  - VM 卷缺了会自动建，Update 卷由系统自建，Hardware 出错会被忽略。
- 加卷只涉及少量元数据：每个空卷约 5 个块（卷超级块、卷 omap 和它的根节点、fs 树根节点、extentref 树、snap meta 树），外加容器 omap 一条记录、`nx_fs_oid[]` 一个槽位。

## 方案

两条路：

- **甲（推荐）：Python 离线工具，扩展 grow-data-store.py 那套容器操作。**
  - 卷对象不手写：用 mkapfs 在临时小容器里建一个空卷，再把它的几个对象移植到目标容器的空闲块：
    - 改物理地址（卷 omap 映射、超级块里的物理 oid）和 xid；
    - 设角色、卷组 UUID、特性位、名字、UUID、大小写；
    - 重算校验和。
  - 空树都是单个根叶节点，没有子指针要改。
  - 理由：
    - 复用已验证的扩容和 spaceman 代码；
    - 空卷的结构用 mkapfs 现成的正确实现；
    - 在用户态跑，出错只坏输出文件；
    - 输出能直接用 apfsck 和 macOS 的 fsck_apfs 验证。
- **乙：给 linux-apfs-rw 加一个“建卷”ioctl，复用驱动里的事务、分配和 B 树插入。**
  - 代码可能更少，但是内核模块：出 bug 会影响宿主内核。
  - 卷组和角色这些容器级操作驱动本来也没有，还是要自己写。
  - 留作备选。

## 工具设计（scripts/apfs-add-volumes.py）

```
apfs-add-volumes.py CONTAINER [--grow-to SIZE] --group-with SYSTEM_VOLUME_INDEX \
    --add Data:D:insensitive --add Preboot:B --add xART:X [--add Hardware:H] [--add VM:V]
```

步骤：
1. 读最新 checkpoint：容器超级块、checkpoint map、ephemeral 的 spaceman 和 reaper、容器 omap。
2. 可选扩容：复用 grow_container 和 grow_internal_pool。
3. 分配块：在已有 chunk 的位图里找空闲位并置位，同步更新 chunk-info 的空闲计数、spaceman 设备空闲计数和 `sm_fs_reserve*`。新卷只占十几个块，放在原有区域。
4. 建卷：对每个要加的卷，先跑 `mkapfs -L NAME -u UUID [-s]` 生成临时容器，按上面的办法移植对象。
   - Data 设 `APFS_VOL_ROLE_DATA` 和 VOLGRP 特性，加入卷组；
   - Preboot、xART（角色 0x100）、Hardware（0x140）、VM 不在组里。
5. 改 System 卷：设 `apfs_volume_group_id`（取 Data 卷的 UUID，与现在真机布局一致）和 VOLGRP 特性位（若未设）。超级块是虚拟对象，写到新块并更新容器 omap，不原地改。密封的 hash 只覆盖 fs 树，不受影响。
6. 容器 omap：插入新卷超级块的 oid→物理地址映射。先假定容器 omap 是单个根叶节点（只有一个卷时），有空位就直接插入，没有就报错退出，不实现分裂。同时更新 `nx_fs_oid[]`、`nx_next_oid`、`nx_next_xid`。
7. 写 checkpoint：按 grow-data-store.py 的做法原地更新最新 checkpoint（超级块两份、map、spaceman），所有改动的对象 xid 用 `nx_next_xid`。

## 验证（逐级，前一级不过不进下一级）

1. 宿主：apfsck 检查整个容器；Linux apfs-rw 逐卷挂载（`vol=N`，Data 和 Preboot 读写），写入、卸载、再跑一遍 apfsck。
2. 参照真机：把 guest 里 disk1 各卷（diskutil 建的）的超级块用 dd 读出来，逐字段对比工具建出的卷（角色、特性位、incompat、组 UUID、`next_obj_id`、`fs_flags`），差异要么解释清楚，要么改掉。
3. macOS 自检：guest 里 hdiutil 挂上产物（镜像放在宿主共享上，或临时推一个小的），跑 `fsck_apfs -n` 和 `diskutil apfs list`，确认卷组、角色和 System+Data 卷组关系。
4. 上机：填好内容、打包后起一台新 VM（不碰现在这台）。确认 apfs_boot_util 两个阶段都过、firmlink 拼接正常、登录正常。

## 之后接 P6 其余步骤

- 填内容：Preboot 放 Cryptexes/OS（OS cryptex 内容）、Cryptexes/App 和 cryptexd 状态目录；Data 放 Templates/Data 加现有定制（make-macos-data-seed.sh、stage-gpu-plugin.py：用户、任务、GPU 插件）。都用 Linux apfs-rw 按卷号挂载来写。
- 打包：全零种子 + 一个含全部非零页的 store（data_store.py 增加一个从裸镜像生成的入口）。
- stage-gpu-plugin.py 改为按角色或卷号找 Data，不再默认第 0 个卷。
- 旧脚本：make-macos-systemos.sh、make-macos-data-seed.sh 的旧布局部分删除或标为旧内核专用。fsck shim 是否还要，在第 4 级验证里确认。

## 阶段和工作量

| 阶段 | 内容 | 估计 |
|---|---|---|
| A0 | 读 os.raw 和现有容器的结构：容器 omap 层数和空位、System 卷特性位、空闲位图；dump guest 里真机布局各卷超级块做对照 | 半天 |
| A1 | apfs-add-volumes.py：分配、移植、入组、omap、checkpoint，宿主验证（apfsck、Linux 挂载） | 1–2 天 |
| A2 | macOS fsck_apfs 验证并修差异 | 半天–1 天 |
| A3 | 填内容、打包、新 VM 上机 | 1 天 |
| A4 | 清理旧脚本、更新文档 | 半天 |

风险：
- 容器 omap 或 spaceman 有我们没覆盖的状态，比如 os.raw 的 omap 不是单节点、释放队列非空、有 reaper 任务。A0 先查清；不满足前提时工具直接报错，不硬写。
- 密封卷改超级块后，APFS 挂载会不会做额外校验，比如密封卷的组变更。A2 和 A4 会暴露出来。
- 工具建的卷有我们没设的字段（比如 `apfs_fs_flags` 里的 ONEKEY、`apfs_formatted_by`），能挂但行为有差别，靠 A0 的对照表消除。

## 进展（11-10）

A1 宿主部分完成：`scripts/apfs-add-volumes.py`（`info` / `add`）。
- 对 os.raw 做了 dm 快照：原卷只读，写入进 COW 文件，不拷 13.7 GB。在快照上扩到 48 GiB，加 Data（与 System 同组，UUID 8748FE31-…）、Preboot、xART、Hardware。
- apfsck 全容器通过；Linux apfs-rw 逐卷挂载、读写通过；Data 写入 2 GB 后 apfsck 仍通过。System 卷上 firmlink xattr 保留。
- 小容器测试：卷 0 改成 System 角色，`next_obj_id` 放进 System 段。扩到 3 倍后写满超过原容器大小，apfsck 通过；System 卷新文件的 inode 在 0x0FFFFFFF… 段，其余卷从 16 起。

A0 实测：
- os.raw 容器 xid 686，3350528 块（不是整数个 chunk，最后一个 chunk 只有 1/4）。
- 容器 omap 是单个根叶节点，1 条记录。reaper 空闲，主释放队列 15098 块（在位图里仍是已用，不影响分配）。
- System 卷：features 0x12（已有 VOLGRP 位），incompat 只有大小写不敏感（没有密封），没有快照，`next_obj_id` 0x0FFFFFFF000BD899。

过程中补的东西：
- grow-data-store.py：
  - `Checkpoint` 类抽出来，两个工具共用；
  - `Image` 支持块设备；
  - 容器最后一个 chunk 不满时，先把它补满再加新 chunk（先检查补出来的那段在位图里是空闲的）。
- apfsck 本地补丁（patches/apfsprogs/0001）：Apple 的系统卷里有 apfsck 认为“block metadata is too big”的压缩文件，原版 apfsck 在第一个上就退出，查不了整个容器。改成只算 weird，跳过这个文件压缩数据的检查。
- 坑：宿主 `/tmp` 是 1.7 GB 的 tmpfs，测试镜像要放 out/ 下，否则 Linux 驱动写入时报 I/O 错、转只读。

A0 真机对照（guest 里 dd /dev/rdisk0，按容器结构读出各卷超级块）：diskutil、storagekitd、mkxart 建的卷与本工具建的逐字段一致。
- 角色：Update 0xc0、xART 0x100、Hardware 0x140。
- features：组内 0x12、其余 0x2。incompat 0x1，fs_flags 0x1。
- 三棵树的类型相同；空卷 alloc 都是 5。
- 卷组 UUID 等于 Data 卷 UUID。
- 现在 Data 卷本来就是 mkapfs 做的（种子）。

A2 macOS 校验：工具产出的测试容器（3 GiB：扩容 + System 入组 + 4 个新卷 + Linux 写入）在 guest 里 hdiutil attach -nomount。
- diskutil 认出卷组（System+Data）和全部角色。
- `fsck_apfs -n` 每个卷和整个容器都 “appears to be OK”，没有警告。
- 注意：测试镜像的 Data 不能用活系统 Data 的 UUID，否则 guest 里会有两个同 UUID 的卷。

工具修正：容器卷槽位不够时，原来会写到一半才失败。现在先检查槽位（按扩容后的大小算）、卷组成员和空闲块，`allocate` 先找齐再置位，拒绝时一个字节都不写。已测：拒绝前后 sha1 相同。

已解决的 A3 前提：
  1. OS cryptex 的解密内容：~~27.2 的 SystemOS cryptex 是 AEA 加密的，宿主上只有 systemos.img~~ 已解决（11-10）：`configs/macos-27.2-26B8125.json` + `macos-fetch-member.py Cryptex1,SystemOS --identity k114sap` 取回，`ipsw fw aea --key` 取 key、`-b KEY -o` 解出 `artifacts/27.2/dec/141-64957-077.dmg`（2.8 GB，裸 APFS，只读挂载见 27.2/26B8125 与 dyld 共享缓存）。.aea 与旧 systemos.img 已删。
  2. 宿主空间：~~只剩约 12 GB~~ 清理后约 49 GB（多数是 /tmp 下旧只读挂载占着已删文件的 loop 设备，卸载后才释放）。

A3/A4 已完成（11-10）：`make-macos-disk.py` 生成 48 GiB 单容器新装盘，七卷经宿主 apfsck 检查，独立实例上机后可登录桌面并通过 SSH 检查卷组、挂载和 firmlink 读写。旧镜像生成脚本已标为旧布局专用；首次 clone 缺少 UEFI 固件的问题已补齐并定向验证。完整结果和原始记录见 [P6 上机验证](k27-real-disk-layout-plan.md#p6-上机验证11-10)。fsck shim 已去除，已验证测试盘重启、登录、firmlink 读写及七卷正常卸载；全新 Data 的首次启动也已由用户确认验证通过。fsck 任务逐阶段退出码尚未单独验证。
