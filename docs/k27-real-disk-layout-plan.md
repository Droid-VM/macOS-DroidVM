# k27 磁盘布局改成接近真机（计划，2026-11-09）

## 目标

`/` 是一个真正的 System 角色卷，和 Data 卷在同一个 APFS 容器、同一个卷组里，和真机一样；去掉为了把三块盘拼成一个系统而加的内核补丁。

现状（三块盘拼成的系统）：

| 盘 | 内容 | 怎么用 |
|---|---|---|
| os.img（disk3） | IPSW 的 Macintosh HD，System 角色 | 真正的根，只读，被 union 盖住 |
| systemos.img（disk2） | Cryptex1,SystemOS（dyld 缓存）+ 我们加的文件（make-macos-systemos.sh） | 内核 union 挂在 `/` 上（`native_owner_cache_prepare`） |
| Data 容器（disk5） | 种子（boot.img 里的 RAM 盘）+ 覆盖层（data-store.img，DroidVMDataStore） | 内核挂到 `/System/Volumes/Data` 并建 firmlink；11-09 起已有 Data(D) + 空的 DroidVMSystem(S) 卷组，24 GiB |

为此存在的内核改动：union 一串（0015、0023、0024，vfs_flags 隐藏 MNT_UNION），`native_owner_cache_prepare` 的 SystemOS union 挂载与校验，boot manifest 要求根和 SystemOS 在不同设备（IOKitBSDInit.cpp:594），11-09 的根设备名替换（`virt_union_mntfromname`、`native_volume_group_system_device`，未提交）。每碰到一处“系统以为 `/` 和 Data 是同一组卷”的地方就要再补一刀：softwareupdate 查 `/` 的空闲空间就是下一处。

## 选定的做法：系统内容放进 Data 容器里的 DroidVMSystem 卷

- 只能这样做：NativeVirtioBlock 驱动自报写保护、拒绝所有写（NativeVirtioBlock.cpp:139、534），可写的路径只有 NativeRamBlock + DroidVMDataStore。Data 容器正好就是可写的，而且已经有 System + Data 卷组。
- Data 卷原地不动，用户数据不用拷。
- 不用给 VM 多挂盘，不用改 crosvm / App 的磁盘列表。

目标布局（disk5，一个容器）：

| 卷 | 角色 | 挂载 | 内容 |
|---|---|---|---|
| DroidVMSystem（4646A7E0-…） | System | `/`，只读 | os.img 的系统 + systemos.img 的内容（现在 union 合出来的那棵树） |
| Data（8748FE31-…） | Data | `/System/Volumes/Data`，读写 | 不变 |

dyld 缓存放在根卷的 `/System/Library/dyld`：生效的是原版 CSR 路径（vm_unix.c 1737–1771，carrier 检查没编进来），要求缓存文件有 SF_RESTRICTED 或 SIP0 有 0x2（已设）、并在信任缓存里或属主为 root。现在系统就是从这个路径用的缓存。

## 步骤

### P0 扩容到 48 GiB（VM 停机，在手机上离线做）

1. 空间：系统约 21.8 GB + Data 10.6 GB = 32.4 GB，48 GiB 留约 15 GB。
2. grow-data-store.py：按 APFS `spaceman_sanity_check` 的期望值公式（apfs kext 0xfffffe0009bbe230，已用 IDA 反出）计算并写入全部字段：
   - 块数、chunk 数、chunk-info 块数（4 个）、内部池（3×(384+4)=1164 块）。
   - 两个 free queue 的节点上限：主队列 512；内部池队列在 48 GiB 时是 3（现在是 1，24 GiB 时不用改，48 GiB 必须改）。
   - tier2 地址数组偏移推到主数组之后（24 GiB 那次的教训）。
3. smcheck.py 增加：把上面每个期望值都和写入值对一遍，不符就不换文件。
4. 流程同 11-09：seed → fold → smcheck → store → 换文件 → 换种子 → 启动。保留 24 GiB 的 store 作回退。

### P1 填充 DroidVMSystem（旧布局下运行，在 guest 里）

1. 把 disk5s2 读写挂到 `/private/tmp/newsys`（nobrowse）。
2. 以 root 用 ditto 从 `/`（现在 union 合出来的视图）逐个拷顶层项，跳过：
   - `/dev`。
   - `/System/Volumes` 下的挂载点：只建空目录，Preboot 例外，它在根上是普通目录，含 cryptex 符号链接，要拷。
   - firmlink 源：`/private` `/Library` `/Users` `/Applications` `/Volumes` `/cores` `/opt` `/usr/local` `/System/Library/Caches` `/System/Volumes/Hardware`。只建空目录（root:wheel，权限照抄）；`/private` 下建空的 var、etc、tmp。
   - os.img 自己的这些目录本来就是空的（宿主核实过），union 下没有被遮住的内容。
3. 核对：
   - 每个顶层项比较文件数和总字节数。
   - dyld 缓存逐文件比 sha256。
   - 抽查 `codesign --verify` 系统二进制。
   - 检查 `/sbin/mount`（shim）、`/sbin/mount.real`，`/var` `/etc` `/tmp` 三个符号链接，`/System/Volumes/Preboot/Cryptexes/OS -> /`。
4. 可撤销：出问题直接删掉 disk5s2 里的内容，旧布局不受影响。

实际做法（11-09）：
- 不能用 ditto：它走 getattrlistbulk，不穿透 union，`/usr/lib` 48 项只拷到 26 项。bsdtar（`tar -cf - … | tar -xpf -`）走 readdir，路径清单与 union 视图逐项一致，保留压缩、xattr、硬链接；`restricted` 标志丢失（SIP 下设不了，靠 SIP0 0x2）。
- 根设备名替换开着时挂不上 DroidVMSystem：mount_apfs 认为它已挂在 `/`（报 Operation already in progress），mknod 别名设备被拒（Permission denied）。用 `k27-root-system-volume=0` 重启后挂上。
- 磁盘号每次开机会变（这次 Data 容器是 disk4），脚本用参数传设备名。
- bsdtar 也有盲区：union 目录里部分只在上层的项（`/System/Library/dyld`、DroidVMData、Safari/WebKit 一串、Preboot/Cryptexes、cups、snmp 等 210 项）fts 看不到；`find` 同样看不到，所以用 find 做的核对会漏。最后用 Python `os.listdir`（readdir）逐目录比对名字、类型、大小、链接目标，缺的和类型不符的（如一层是目录、另一层是符号链接）删掉后用 tar 按清单补拷，一轮收敛：194548 个目录、354389 个文件，缺 0、错 0、多 0；dyld 缓存逐文件 sha256 一致，抽 99 个二进制 hash 一致。卷占 20 GB。
- bsdtar `--exclude` 不锚定：`./System/Library/Caches` 也排除了 `System/Library/Templates/Data/System/Library/Caches`，靠上面的比对补回。
- 漏建 `/dev` 空目录 → `devfs_kernel_mount: kernel_mount failed: 2`，launchd 起不来。真机系统卷有空 `/dev`（root:wheel 555）。

### P2 进展（11-09）

- 内核：撤掉根设备名替换（存档 out/k27/root-rename-20261109.diff）；`native_owner_cache_prepare` 无 `/chosen/owner-systemos-uuid` 时进单卷模式；boot manifest 无缓存卷时只算根。同一个 KC 两种布局都能启动（有 systemos uuid 走 union）。旧 KC 留在 out/k27/kc-k27-union-rename.bin。
- 脚本：`MACOS_ROOT_UUID` → root-matching 改指 DroidVMSystem、不写 owner-systemos-uuid、不加 union-hide-lower。
- 上机：APFS 自己认出“卷组的 System 卷作根”并建 shadow fs_root；Data 挂载显示 `root data`；`df /` 是容器空间；10 个 firmlink 全成功；`mount -uw /` 可行（SIP0 0x2）。dyld 缓存首次映射 34–45 s，两种布局一样，不是新问题。
- 卡点：launchd 启动任务 `init_featureflags --boot` 在单卷布局下 abort（SIGABRT，不打印任何消息，说明在 FeatureFlagsSupport 的 `FFConfiguration initPrivateForBootTask` 内部，不是 init_featureflags 自己的检查），之后 launchd 停在这里。环境是 `XPC_NULL_BOOTSTRAP=1 XPC_SERVICES_UNAVAILABLE=1`；启动后手动不带这些变量跑成功。临时在 DroidVMSystem 上放了包装脚本（真二进制改名 init_featureflags.real），用于定位，不是修法。
- 根因：vfs_syscalls.c `virt_preboot_hidden` 让 statfs(`/System/Volumes/Preboot`) 报不存在，否则 CoreServices `FSNodeServer_PreWarmVolumeCache` 发现 Preboot 和根同设备号就 abort；这个开关挂在 `union-hide-lower=1` 上，单卷模式去掉该参数后 Preboot 暴露。保留 `union-hide-lower=1`（没有 union 挂载时它别的分支不生效）后 init_featureflags 返回 0，系统起到登录界面。包装脚本已撤掉、原二进制已还原。
  - 真机做法是 Preboot 单独成卷。以后（P5）可在 Data 容器加 Preboot 卷（role B）并挂到 /System/Volumes/Preboot，然后去掉 `virt_preboot_hidden`。
- 已验证：`/` = disk5s2（无 union），Data 带 `root data`，`/`、Data、firmlink 目录同一个 st_dev（APFS 卷组行为，与真机一致）；`diskutil apfs listVolumeGroups` 显示 Data+System 卷组；容器空闲 19.5 GB。
- 11-10 IPv4 恢复后：`softwareupdate --list`（带触发文件）列出 Command Line Tools for Xcode 27.2；容器空闲 17 GiB > 安装需要的 9.54 GB（CLT 已装，未再实际安装）。
- 当时未验证（网络）：softwareupdate 列 CLT 和空间检查（这次手机 Wi-Fi 桥的 IPv4 不通，DHCP 拿不到地址、静态地址也 ping 不通网关，union 布局同样，与布局无关；IPv6 正常，SSH 用 IPv6 地址）；登录、GPU、视频、音频、触屏。
- 启动方法：在原来的 boot 命令前加 `MACOS_ROOT_UUID=4646A7E0-5598-41A2-B158-E1AF6D3CF7FB`；不加即回到 union 布局（同一个 KC）。

### P2 内核与启动配置

内核（out/k27/xnu）：
- 新的单卷模式：`/chosen/owner-systemos-uuid` 不存在时进入，或用一个开关（暂定 `k27-single-volume=1`）。
  - `native_owner_cache_prepare` 不做 SystemOS union，只校验根是只读 apfs。
  - boot manifest 只用根卷 UUID 计算；27 的 Image4 要求 hash 非零，具体编码在实现时对照 0032。
- `native_owner_data_prepare` 不变：照旧按 UUID 找 Data 卷读写挂载、建 firmlink。firmlink 源现在是根卷上的空目录，目标在另一个挂载上，条件仍成立。
- 撤掉 11-09 的根设备名替换（`virt_union_mntfromname`、`native_owner_root_device_prepare`、`native_volume_group_system_device`）：根就是 System 卷，不再需要。

启动配置：
- `run-macos-vm.py`：`/chosen/root-matching` 的 UUID 改成 DroidVMSystem（新增 `MACOS_ROOT_UUID`），单卷模式下不写 `owner-systemos-uuid`。
- `droidvm-app.py`：REQUIRED_ARGS 去掉 `union-hide-lower=1`。
- os.img / systemos.img 先保持挂着（只读、无害），验证完再从 App 配置里去掉。

已确认没问题的前提：
- 根挂载在 11.9 s，Data 容器 9.1 s 已出现，所以根可以在 NativeRamBlock 盘上。
- `rootauth=0` 已在参数里。

### P3 上机验证（一次过）

- 启动、登录、桌面。
- `mount`：`/` 是 disk5s2、不带 union；`df /` 是容器空间。
- `dataVolumePathGivenSystemPath:@"/"` 返回 `/System/Volumes/Data`。
- `softwareupdate --list`（带触发文件）能列出 CLT。不实际安装，只看空间检查是否通过，日志里的 available 值。
- `installer` 能装 Apple 签名包。
- 以前和 union 相关的功能逐个看：fseventsd（MNT_ROOTFS）、mds/Spotlight（union 属性）、FileIDTree（设备号）、Safari（cryptex 相对链接）。
- GPU/Metal、视频解码、音频、网络、触屏。
- 新崩溃报告。

### P4 清理（P3 通过后）

- App 配置去掉 os.img、systemos.img 两块盘，手机删除这两个文件（约 25 GB）；宿主上的构建产物保留。
- 内核去掉单卷模式下用不到的代码：union-hide-lower 一串（0015/0023/0024 及 vfs_flags 部分）和 SystemOS union 挂载。先保留开关、确认没人再用后再删，补丁系列重新导出。
- 删除手机上的旧 store 备份。

### P5（11-10 已完成，见文末）

- 让 launchd 的 mount-phase / APFS 自己挂 Data、建 firmlink（去掉 `/sbin/mount` shim 和内核 0038/0039）。
  - 前提：`/usr/share/firmlinks` 里有 Assets、Speech、cups、snmp、CoreTypes 等模板目录，我们现在直接放在系统卷上。原生 firmlink 会把它们指向 Data，所以要先挪进 Data。
- 加 Update / VM / Preboot 卷。

## 手机空间

| 阶段 | 增量 | 说明 |
|---|---|---|
| 现在 | 剩约 20 GB | 另有两份旧 store 备份各 16 GB（before-volgroup、before-grow） |
| P0 | 中间 raw 约 12.5 GB + 新 store 约 12.5 GB，旧 24 GiB store 留作回退 | 需先删 before-volgroup 和 before-grow 两份（+32 GB） |
| P1 | 覆盖层增加约 22 GB | 删掉 P0 的中间 raw 后够用 |
| P4 | 删除 os.img、systemos.img（+25 GB）和 24 GiB 回退 store | |

## 回退

- P0：换回 24 GiB 的 store 和对应种子（`scratch-data.img` 与 `seed.sha` 照 11-09 的做法切换）。
- P1：只写 DroidVMSystem 卷。
- P2/P3：旧 kc 和启动参数留着，`droidvm-app.py boot` 用旧参数重建 boot.img 即可回到 union 布局。

## 风险

- ditto 的保真度：
  - SIP 下不能设 SF_RESTRICTED，靠 SIP0 0x2。
  - 压缩文件、硬链接、xattr 由 ditto 保留。
  - 信任缓存按内容 hash，内容不变就有效。
- APFS 能否从“只读 System + 读写 Data 同容器、底层是 RAM 盘 + 覆盖层”的设备挂根：真机就是同容器混挂，问题不大，要上机确认。
- boot manifest 单卷时 Image4 是否接受：实现时对照 0032 的用法。
- 覆盖层变大：P1 写入约 22 GB 都进 data-store.img；stage-gpu-plugin `--store` 和 fold 的中间 raw 会跟着变大（48 GiB 稀疏文件）。

### P4 进展（11-10）

- 用户确认登录、GPU、视频、音频、触屏正常。
- `droidvm-app.py disks`（新）：按 `MACOS_ROOT_UUID` 只替换 App 配置里的 `--virtio-mmio-block`，其余设置不动，再 dump FDT。单卷布局下只剩 data-store.img，它的窗口变成 0x0a000000（run-macos-vm.py `DATA_STORE_MMIO`），其后的 net/gpu/snd/media 窗口整体前移，均已上机确认挂上。`push` 在单卷布局下不再推 os/systemos。
- 已删手机上的 os.img、systemos.img（及 .sha）和 data-store.img.24g，手机剩余 16 → 49 GB。宿主 artifacts/27.2/os.raw、systemos.img 保留。
- 回退到 union 布局：不设 `MACOS_ROOT_UUID` 跑 `push`（重新推约 25 GB）、`disks`、`boot`。
- 内核里 union 那串代码暂不删（同一个 KC 仍支持两种布局）；当时 `union-hide-lower=1` 必须保留（隐藏 Preboot，见 P2），P5 之后单卷布局已不再需要。

### P5 完成（11-10）：launchd/APFS 原生挂载

现状与真机相同：根 = DroidVMSystem 只读，launchd 的 mount-phase-1/2（apfs_boot_util）挂上 VM、Preboot、Update、xART（/System/Volumes/xarts）、Hardware 和 Data（`root data`），APFS 按系统卷上的 firmlink 自己拼接（`/Applications`、`/Users` 等与 Data 同 st_dev）。`/sbin/mount` 已换回原版，单卷布局下不再传 `union-hide-lower=1`，内核也不挂 Data。union 布局不受影响：内核看 FDT 有没有 `/chosen/owner-systemos-uuid` 决定走哪条路。

Data 容器 disk1 的卷：s1 Data、s2 DroidVMSystem（System）、s3 Update（系统自建）、s4 Preboot、s5 VM、s6 Hardware、s7 xART。

做法与坑：
- firmlink 存为系统卷目录上的 FS 专用 xattr `com.apple.fs.firmlink`（值是相对 Data 根的路径）加 BSD 标志 SF_FIRMLINK 0x00800000。用户态 setxattr/chflags 都返回 EPERM。
  - 唯一入口是 `fsctl(dir, 0xC4084A3C, {char path[1024]; u32 get; u32 value}, 0)`（apfs `handle_firmlink_ctl`）。
  - 要求：root、entitlement `com.apple.private.apfs.set-firmlink`、卷可写、System 角色、在卷组里、目标目录在 Data 里已存在。
  - 工具 `k27/disk-tools/setfirmlink.c`（`-f` 按 /usr/share/firmlinks 全设）。
- `/usr/share/firmlinks` 里的模板目录（Assets*、AssetsV2、Speech、CoreTypes Contents/Library、cups、snmp、pkg 等）先挪进 Data，系统卷上的同名目录清空，然后设 firmlink。AppleInternal 跳过。
- 带私有 entitlement 的 ad-hoc 二进制会被 AMFI 杀掉（137）。办法是把它的 CDHash 加进启动信任缓存：stage-gpu-plugin 的 `cdhash`/`trust_bundle` 多加一个模块，产物在 `out/k27/firmlink/kernel.macho.trustcache`，用 `MACOS_TRUSTCACHE` 指过去启动一次。只有设置时需要，平时用标准信任缓存。
- apfs_boot_util phase 1 依次做下面几步：
  - 按角色挂 VM（没有就自动建）、Preboot、Update。
  - 必须挂 xART，失败就 abort，launchd 随即重启。
    - 它找 xART 的方法：AppleAPFSVolume 角色为 xART，且向上最近一个非 AppleAPFSMedia 的 IOMedia 带 `Content Hint` = `69646961-6700-11AA-AA11-00306543ECAC`（iBoot System Container）。
    - 我们的 store 是整盘容器，IOBlockStorageDriver 给它的 IOMedia 一个空 hint，所以 NativeRamBlock 在盘发布后补上这个 hint（`scripts/build-native-ram-block.py` 的 `markSystemContainer`）。
  - iSCPreboot、Hardware（角色 320）出错会被忽略。
  - `kern.exclaves_status`=255 时跳过 ExclaveOS 部分。
- 建 xART 卷要 entitlement `com.apple.private.apfs.xart`，diskutil 没有，会报 -69624。改用 `k27/disk-tools/mkxart.c`：dlsym APFS.framework 的 `APFSVolumeCreate`，角色 0x100，同样要进信任缓存。
- 写系统卷：在 SIP0 0x2 下用 `mount -uw /`，改完重启。
- 根卷上 /System/Volumes/Preboot 挂载点下面还留着 P1 拷的约 50 MB 旧内容，被挂载遮住、无害，暂不清。
- 旧 union 布局时的 “nx_volume_group_update: … already in stitched list” 日志刷屏，在原生挂载下没有再出现。

### 删除内核里的 union 布局代码（11-10）

单卷 + 原生挂载跑通后，k27 内核删掉了只给 union 布局用的代码。删除不是另加一个回退补丁，而是重建了 k27 分支历史，再整体重新导出补丁系列（共 49 个）：
- 旧 0023（union-hide-lower 的 MNT_ROOTFS）、0024（union create 查找）整个去掉。
- 0015 只剩 IOWorkLoop，0038 只剩 CONFIG_FIRMLINKS，0039 只剩 k27-mkdir-log；0002、0008、0025、0044 里的 union/Data 挂载部分也去掉了。
- 最后一个补丁 0049 只做根卷校验和 boot manifest 的单卷化，并删掉 SystemOS 挂载。
- 旧历史留在分支 `k27-before-reexport-20261110`。

最终源码删掉的内容：
- `union-hide-lower` 全套：`virt_union_top`/`virt_union_visflags`（stat、statfs、getattrlist 报上层设备号和 MNT_ROOTFS）、getfsstat 隐藏下层、`virt_preboot_hidden`。vfs_attrlist.c、vfs_vnops.c 回到原版。
- union 查找/读目录的修补（0015 里 vfs_lookup 那部分、0024，以及 getattrlistbulk 的 union 读）。vfs_lookup.c 回到原版。0015 里 IOWorkLoop 的修复保留。
- 内核自建 firmlink（0038：`native_owner_firmlinks_prepare`、lookup 跟随 firmlink、`vfs_flags` 隐藏 MNT_UNION）。kpi_vfs.c 回到原版。`config_firmlinks` 保留，APFS 原生 firmlink 要用它。
- 内核挂 Data（0039 的 `native_owner_data_prepare`），连同挂在它后面的 gpu-addon、staged-apps 两个 bindfs union，以及 bindfs 的 boot-mount 例外（bindfs 回到原版）。
- SystemOS union 挂载：`native_owner_cache_prepare` 只剩根卷校验、发布 boot manifest（集合只含根卷）和 dyld 标志。`native_owner_systemos_volume_uuid`、`native_verified_block_volume_device`、`native_ram_block_volume_seed`、vm_unix.c 里早已不用的 CARRIER 代码一并删除。
- build-kernel27.sh 去掉 `XNU_OWNER_DATA_MOUNT`、`XNU_OWNER_UNION_SYSTEMOS`。

保留的诊断开关：mount-log、symlink-log、k27-mkdir-log。27.2 的 rename-swap 通知也保留。

从此 k27 内核只能起单卷布局。`droidvm-app.py` 的 `MACOS_ROOT_UUID` 默认是 DroidVMSystem，设成空串才是旧 union 布局（只给旧内核用）。上机验证：挂载与真机一致，firmlink 和 `..` 正常，fseventsd、mds、kernelmanagerd、WindowServer、loginwindow 都在跑。

## P6 生成脚本适配（新装启动已验证，11-10）

现状：生成脚本还在做 union 布局（make-macos-systemos.sh、make-macos-data-seed.sh、run-macos-vm.py 的 os/systemos），新内核已经起不来它们做出的镜像。手机上现在的盘是旧种子 + 覆盖层再在 guest 里手工迁移来的，从 IPSW 重做不出来。

已核实（os.raw 只读挂载）：
- os.raw 容器里只有一个卷：原版密封 System 卷 “Macintosh HD”。
- 它自带全部 firmlink：源目录为空，带 `com.apple.fs.firmlink` xattr，值是相对 Data 根的路径，与 /usr/share/firmlinks 一致。根目录的 var/etc/tmp 链接齐全，System/Volumes 下的挂载点也齐全。
- `/System/Cryptexes/{OS,App,…}` 都是指向 `../../System/Volumes/Preboot/Cryptexes/…` 的链接。真机在 Preboot 里挂 cryptex，这里在 Preboot 卷里放普通目录即可。

所以 System 卷直接用原卷，一个字节都不改。systemos.img 以前加的东西都搬到别处：
- OS/App cryptex 和 cryptexd 状态目录 → Preboot 卷；
- Data 模板内容 → Data 卷（`/System/Library/Templates/Data`，真机安装器也是这么做的）；
- mount shim 已不需要；fsck shim 也已去除，验证范围见下文。

流程：
1. 从 os.raw 的 GPT 分区取出 APFS 容器。
2. 结构步骤（要 macOS 的 diskutil）：在原容器里加 Data（role D，与 System 同组）、Preboot、VM、Hardware 和 xART（mkxart）。
   - 在 guest 里对挂进来的镜像做，镜像放在宿主网络共享上，guest 用 hdiutil attach，不占 guest 和 Data store 的空间。
   - 只依赖 os.raw，每个系统版本做一次，结果缓存在 artifacts/TAG/ 下。
3. 宿主扩容：复用 grow-data-store.py 的扩容逻辑，加一个裸容器模式。
4. 宿主用 Linux apfs-rw 按卷号挂载填内容：
   - Preboot：cryptex；
   - Data：模板，加上 make-macos-data-seed.sh、stage-gpu-plugin.py 的定制（用户、任务、GPU 插件）。
5. 打包：全零种子 + 一个含全部非零页的 store。种子打包后极小，逻辑上限 1 TiB；store 格式本来就是页覆盖。
6. 清理旧脚本：make-macos-systemos.sh 等标为仅旧内核使用，或删除。stage-gpu-plugin.py 挂 Data 时要显式按卷号或角色挂，现在默认挂第 0 个卷。

不动用户现有的种子和 store：新流程只用于新装。

### P6 进展（11-10）

新装镜像由 `scripts/make-macos-disk.py OUTPUT_DIR` 一步生成（宿主，需要 sudo）：
- 输入：artifacts/27.2 下的 os.raw、`dec/*.dmg`（SystemOS cryptex，macos-fetch-member.py 下载后用 ipsw fw aea 解密）、`app-cryptex/*.dmg`。
- 容器直接建在 Data store 的页窗口里：os.raw 用 dd 写到窗口偏移处，apfs-add-volumes 扩到 48 GiB，加 Data（与 System 同组）、Preboot、VM、Update、Hardware、xART。种子是同样大小的空盘（32 字节的 DBRDISK1），整盘都在 store 的覆盖层里，所有有数据的页都标为存在。不需要再拷一份 20 GB。
- 计划里原想 System 卷一字节不改，这条做不到：内核让 dyld 走 no-ignition（kern_exec.c `native_owner_cache_prepare`），没有东西把 Preboot 里的 cryptex graft 上来，而 launchd 和挂载阶段在 Preboot 挂上之前就要用共享缓存。所以 OS cryptex 合并进 System 卷，Preboot 里放 `Cryptexes/OS -> /`，与现在机器上的布局一致。`/sbin/fsck` 保留 Apple 原版，不再安装 bring-up shim。
- Data：整份 /System/Library/Templates/Data（不再受 256 MiB 种子限制，旧脚本的 DroidVMData 链接不再需要）。
- 用户、GPU 插件等由 `stage-gpu-plugin.py --base DIR/scratch-data.img --disk DIR/data-store.img` 原地写入；stage-gpu-plugin 现在在所有模式下都按角色找 Data 卷。
- 手机侧：`droidvm-app.py install DIR` 只传有数据的段，不会覆盖已有 store；`MACOS_INSTANCE=NAME` 在 MacOS-NAME 目录里放第二台 VM，`clone BOOT_IMG` 复制主 VM 的 App 配置。

坑：
- Linux apfs-rw 同时以读写方式挂同一容器的多个卷时，开发机两次内核 panic（apfs_node_query UAF）。现在每次只读写挂一个卷，源从别的镜像只读挂（Data 模板读 os.raw）。
- mkapfs 用自己的 euid 作新卷根目录属主：apfs-add-volumes 改用 `unshare -r` 跑 mkapfs，卷根为 root:wheel。
- apfsck 检查 Apple 原版 System 卷不要加 `-u`（cloneinfo epoch 报 not supported 后直接退出）；`-cw` 的退出码 1 只是因为有 weird 提示（压缩元数据），不算错误。

结果：apfsck 全容器通过；7 个卷，System UUID 354D4F10-…，store 约 20 GB 数据。

### P6 上机验证（11-10）

新实例 `macOS 27 (DroidVM) new`（`MacOS-new/`，VM ID `e38b5f50-8527-5d1f-b687-1b42f8d260f0`）已启动，droid/droid 登录桌面成功，用户开启远程登录后 SSH `droid@192.168.1.196` 可用。
- 系统为 macOS 27.2 / 26B8125，内核 Darwin 25.5.0。System UUID `354D4F10-9A79-4243-BA00-60FAB89D7561`；System/Data 同组，组 UUID 等于 Data UUID `3E85A466-1B38-4F91-A4F1-696737AFE9AF`。
- 七卷均已挂载：System 只读根，Data 为 root data，Preboot、VM、Update、Hardware、xART 各在标准挂载点。未取到 apfs_boot_util 的阶段日志，不把挂载结果记成逐阶段退出码验证。
- `/Users`、`/Library`、`/Applications`、`/private` 与 Data 下对应目录的设备号和 inode 相同；`/Users/droid/../..` 回到 `/`；经 `/Users` 写入后从 Data 路径读回一致，临时文件已删除。
- WindowServer、loginwindow、Dock、Finder、SystemUIServer、fseventsd、mds、kernelmanagerd 均在运行。Data 已用约 3.3 GiB，容器剩余约 25 GiB。
- 首次 clone 漏了 UEFI 固件，报 `failed to open kernel image .../edk2-macos.fd`；clone 现同步复制实例目录内的固件。临时实例注册和固件 SHA-256 对比通过，临时实例已删除。
- 旧 SystemOS/Data 种子生成脚本已标为旧布局专用。本次初验仍使用 `/sbin/fsck` shim；后续去除验证见下文。

本轮原始记录：[SSH 系统和挂载](../out/p6-validation-2026-11-10/guest.txt)、[firmlink](../out/p6-validation-2026-11-10/firmlinks.txt)、[root 检查](../out/p6-validation-2026-11-10/root.txt)、[桌面截图](../out/p6-validation-2026-11-10/desktop.png)。生成和宿主校验记录仍在 `out/a0test/`。

收尾：工具仓库 `python3 -m unittest discover -s tests -v` 的 13 项测试通过（[输出](../out/p6-validation-2026-11-10/tests.txt)）。测试 guest 执行 shutdown，日志确认七卷均卸载、`CPU halted`；crosvm 仍驻留，由 daemon stop 后退出码 0。主 VM 首次启动遇到大页控制忙，重试后已恢复 RUNNING。

### 关机块计数提示（11-10，已定位并修复生成端）

[关机日志](../out/p6-validation-2026-11-10/shutdown.txt) 的 System/Preboot 都有 `fs_alloc_count mismatch`。停机测试盘经主 VM 的原版 `fsck_apfs -n` 只读检查，七卷和容器均通过，退出码 0（[完整输出](../out/p6-fsck-2026-11-10/fsck-phone.txt)）。不是只读 shadow 导致，也未发现文件系统结构损坏。

根因：APFS kext 的 `sanity_check_alloced_blocks` 把 `apfs_total_blocks_alloced - apfs_total_blocks_freed` 当作用户数据块数，再加各元数据树及 omap 对象。Linux APFS 驱动却在创建、删除或保留元数据节点时也增减这两个累计字段，导致卸载重复计数。`fs_alloc_count` 本身仍要计入元数据，不应修改它或屏蔽日志。[反编译记录](../out/p6-fsck-2026-11-10/sanity-pseudocode.txt)。

修复：`patches/linux-apfs-rw/0001-user-data-block-counters.patch`，元数据路径只更新 `fs_alloc_count`，累计计数留给数据 extent 路径。宿主模块已用 `make LLVM=-21` 重编并加载。
- 同一 1 GiB 空卷上创建 1400 文件、删半数、再写 700 文件：旧驱动累计净分配 3719，实际用户数据 3500，差 219；新驱动净分配 3500，差 0，元数据均为 224 块，总分配均为 3724 块。
- 新镜像通过 Linux apfsck 和 Apple fsck_apfs；Apple 只读挂载、读取 1400 文件、卸载后不再报 mismatch；旧镜像同样操作复现 `3724 != 3943`。
- [旧计数](../out/p6-fsck-2026-11-10/counts-before.json)、[新计数](../out/p6-fsck-2026-11-10/counts-after.json)、[Apple 旧镜像日志](../out/p6-fsck-2026-11-10/apple-fixtures.txt)、[Apple 新镜像日志](../out/p6-fsck-2026-11-10/apple-after.txt)、[复现脚本](../out/p6-fsck-2026-11-10/write-fixture.py)。旧产物的累计字段不会因重编模块自动恢复，应重新生成或单独校正。fsck shim 去除测试已完成，见下文。


### 原版 fsck 启动及关机验证（11-10）

测试实例停机后，在 COW 副本内恢复原版 `/sbin/fsck`，并校正旧 Linux APFS 驱动留下的累计分配字段（System、Preboot、Data）；未改 `fs_alloc_count`。只将差异块写回已停止的测试盘，保留原字节备份和写后比对。主 VM 及宿主原始产物未校正。

- 原版 fsck 为 135152 字节，SHA-256 `9fe1cc4e195431152025f619981294386803f99fc21a04a937e2ea4b7938bcbf`，没有 fsck.real；重启可达登录窗口和 SSH。
- 用户登录 droid 后，SSH 确认 console 属主 droid，WindowServer、Dock、Finder、SystemUIServer 运行；七卷挂载正确，四组 firmlink 的设备号/inode 相同，写入读回和 `..` 跳转通过。[桌面进程与读写记录](../out/p6-fsck-2026-11-10/no-shim-desktop.txt)。
- 正常 shutdown 后七卷全部卸载，`numMountedAPFSVolumes 0`、`CPU halted`，日志没有 `fs_alloc_count mismatch`。[关机日志](../out/p6-fsck-2026-11-10/no-shim-shutdown.txt)。随后 daemon stop。
- `make-macos-disk.py` 已去掉 fsck shim 的安装逻辑和命令行开关，新生成盘保留 Apple 原版 fsck；旧布局脚本的 shim 暂留。
- 收尾 13 项 unittest 全部通过；测试实例 STOPPED，主实例恢复 RUNNING，SSH 确认根为 `/dev/disk1s2`。[恢复记录](../out/p6-fsck-2026-11-10/main-restored.txt)。

范围：本轮采集覆盖已完成首次登录的测试盘恢复原版 fsck 后的重启；全新 Data 的首次启动也已由用户确认验证通过。未捕获 launchd fsck 任务的逐阶段退出码，不能把正常启动等同于该任务退出码已确认。旧产物应重做或单独校正累计字段，加载新模块本身不会修复旧字段。测试记录见 `out/p6-fsck-2026-11-10/`。


### 补丁历史清理（11-11）

此前 49 个补丁的最终源码虽已无旧布局，0002 仍加入 SystemOS 挂载及双卷 manifest，再由 0049 删除；0042 也只服务这条过渡路径。本次重建每个提交的源码树：0002 直接引入当前根卷校验、从根读取 UUID 及仅含根卷的 manifest；后续提交不再出现旧 SystemOS 挂载。0042、0049 变为空提交并删除，补丁重新编号为 47 个。上文 11-10 的编号和数量是当时记录。

47 个补丁从 `ac9718f` 全部 `git am` 重放通过，最终 tree 为 `c97cc109b2b49890091f3fb035777204c2fd1e4b`，与清理前已验证内核完全相同，不需要重新部署内核。记录见 `out/layout-cleanup-2026-11-11/{history.json,replay.txt}`。旧实验分支属于归档，不在当前 k27 补丁序列中。


### 旧制盘和启动路径清理（11-11）

已删除 `make-macos-systemos.sh`、`make-macos-data-seed.sh`、`rebuild-root.sh` 和 `overlay/systemos-shims/sbin/{mount,fsck}`。`run-macos-vm.py`、`droidvm-app.py` 不再配置或推送 os.img/systemos.img、不再写 owner-systemos-uuid 或传 union-hide-lower；唯一 mmio 块设备是完整新装盘 store，根 UUID 指向其中 System 卷。空 MACOS_ROOT_UUID 直接报错，不再选择旧布局。默认版本为 27.2，默认种子为 `artifacts/TAG/disk/scratch-data.img`，仍可用 MACOS_DATA_SEED 指定已部署盘的种子。

缺少 store 时启动工具直接提示先制盘并 install，不再创建只有旧布局才能使用的空 Data store。插件部署工具删除旧的单 Data 卷重建扩容选项 `--data-size-mib`，保留按角色挂载 Data 及 `--base/--store/--disk`；容量在制盘时用 `make-macos-disk.py --size-gib` 设置。参考内核构建工具也不再从已删除的 Data 制盘脚本读取 UUID。归档文档保留当时的命令作为历史记录；参考内核镜像认证工具仍用于复现归档参考构建，不作为当前 k27 制盘入口。

验证：4 项启动配置定向测试及全量 17 项 unittest 通过；用现有 FDT、相同根 UUID 和固定随机输入生成的 ADT 在清理前后逐字节相同（SHA-256 `86cb056b509376e983d12ae05f1dc3ecd9b8abcf7a36bff372bad3d772aac29d`）。App 的磁盘参数、必需启动参数及内核命令行与清理前一致；三处脚本 CLI 帮助和 Python 编译检查通过。主实例仍为 RUNNING，本次未重新部署镜像或重启 guest。记录见 `out/layout-cleanup-2026-11-11/`。
