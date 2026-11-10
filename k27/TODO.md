# k27：xnu-12377 内核 + macOS 27.0.1 内核缓存 kext — TODO

独立于 26.5 kext 主线（`scripts/kc-build.py` + `out/kc/kc265.bin` + `out/x12377/xnu-m`），不改主线产物、不动主线内核树。
本目录放脚本和本文件；大文件（内核源码 worktree、构建目录、KC）在 `out/k27/`。文档不提交。
上机测试可自动进行，超时自定：先短（launchd 前 60–90 s）后长（到登录界面 240–400 s）。

评估数据见记忆 `macos-27-kext-on-12377-eval`（2026-10-30）：kc-keep 闭包 37 个 kext，缺内核符号 16 个，内核虚表 212 个只差
IOPerfControlClient 1 槽，27 kext 无 adrp 进内核；只能整体换 KC，不能和 26.5 混搭。

## 目录
- `k27/kc27-layout.py`：检查 kc27 里保留 kext 占用与我们内核段的冲突，生成 `k27/segaddrs.sh`。
- `k27/kc-build27.py`：复用 `scripts/kc-build.py`，换成 kc27 的常量；KEPT_CODE_PATCHES 为空（Sandbox 字符串补丁 try62 起已删），KEPT_POINTER_REBINDS 把 AMFI 的 PAGE_SHIFT_CONST GOT 槽绑到内核 `k27_amfi_page_shift`。
- `k27/build-kernel27.sh`：用 `out/k27/xnu`（xnu-m 的 git worktree，分支 k27）+ 独立对象目录编内核。
- `k27/try.sh`：重做 KC27 并上机一次（同 kc-try.sh）；默认带 `MACOS_BOOT_MANIFEST_HASH=1`；默认保留旧 DiskImages kext（hdiutil 要），`K27_DI=0` 去掉。
- `k27/build-native-display.sh`：k27 版 DroidVMDisplay（重生 IOMFB ABI、偏移表 26.5→27、去掉 convertSwapRecord 钩子）。
- `k27/cpu-stacks.py`：冻结/死锁时各 CPU 当前线程栈与中断栈（慢，几分钟）；`k27/dbg-state.sh`：debugger_* 状态（current_op=3 即 panic 中）。
- `k27/build-native-aes.sh` + `k27/kext/NativeAES.json`：k27 版 NativeAES（源码拷到 out/k27/src 再改，加设备密钥 selector 2212）。
- `k27/sym.py`：符号化 k27 地址（内核 nm 的 s/S 段符号 + kc27 kext 符号，平移 0x1f000000000）；`k27/sym.py < dmesg` 展开 k27-stall 行。
- 诊断开关（k27 内核）：`panic-spin=1`；`stall-dump=秒`（launchd 没起来就打印阻塞线程栈）；`stall-panic=秒`（在时钟中断里 panic，留下所有核 PC）；`crash-log=1`；`iokit-log=类名[,…]`（打开/匹配/new/每个 (类,selector,返回值) 首次调用）；`stderr-log=1`；`sample-name=进程[,进程…]` / `sample-pid=PID`（-1 = kernel_task）+ `sample-period=秒`（线程状态+内核栈+用户栈，`/tmp/k27-symsample.py` 符号化）；资源等待自动打印 `iokit: wait resource KEY state A/B published N`（state 无 0x4 = IOResources 未 matched）；`k27-deny-exec=路径[,…]`（默认 mobileactivationd，exec 返回 EPERM）；（`k27-sandbox-native`、`k27-firmlink-paths` 已分别在 23a75df、de67fea 删除）。
- 看日志：`/tmp/k27-poll.sh` 只抓环形缓冲最近一段，早期行会滚掉；要累计就每次追加到一个文件，判断“没起来”前先看最新时间戳。
- `k27/panic.sh`：读运行中 VM 的 panic 文本（xnu debug_buf_base..debug_buf_ptr；kc-panic.sh 的固定 PA 在 k27 不对）。上机加 `panic-spin=1`（k27 内核诊断开关），否则 panic 后 VM 直接复位，读不到。

## 阶段
- [x] 0 准备：worktree `out/k27/xnu`（分支 k27：xnu-m a360f13 + 主线未提交改动快照 e0ce7cc），对象目录 `out/k27/{obj,sym,dst}`（经 `out/x12377/build/xnu/k27-*` 链接）。iig 依赖的 Darling 容器没起，`build-kernel27.sh` 先拷主线 e-obj 生成好的 DriverKit 头（.iig 未改）。
- [x] 1 布局：`k27/segaddrs.sh`/`segaddrs.json`。kc27 把 Libm、pthread（都要保留）紧贴在 Apple 内核 __TEXT（0x11c000）之后，我们的
  DEVELOPMENT 内核 __TEXT 0x188000（__cstring 多 0x64000）放不下 → 链接时 `-rename_section __TEXT,__cstring,__TEXT_EXEC,__cstring`
  （__os_log 留在 __TEXT，resolve_dso 只查它），__TEXT_EXEC 放在 0x2dcc000 结束于 Apple __KLD；__KLDDATA/__DATA/__BOOTDATA 结束于 Apple
  __BOOTDATA 末尾 0x3ca4000，起点 0x3a54000 吃进 __PRELINK_INFO 尾部（剩 2 MiB 给裁剪后的 plist）。
- [x] 2 内核垫片（16 个符号，`bsd/kern/k27_compat.c`，692af4a，按 27 内核反汇编实现）：
  - AMFI：`csblob_get_cdhash_with_length`、`query_trust_cache_with_length`、`match/set_compilation_service_cdhash_with_length`、`unrestrict_local_signing_cdhash_with_length`（cdhash 长度 20 的包装）
  - Image4：`image4_v2_interface_register`（存指针）、`image4_v2_load_diavlo_root_ca`/`load_local_policy`/`roll_nonce`/`set_nonce_digest`
  - Sandbox：`task_get_sanitizer_config`、`vnodeop_desc_name`
  - APFS：`vfs_context_ignores_content_protection`、`vfs_context_is_strict_content_protection`、`cluster_update_range_with_callback`（要对照 27 内核逆向语义）
  - Skywalk：`ifnet_enable_synchronous_input`
- [x] 3 只含内核+安全 kext 的 KC27 启动到 launchd（短超时）。
- [x] 4 关掉 26.5 专用的 bring-up 绕法：23a75df 删除 mac-sandbox-permissive / mac-sandbox-skip-exec / sandbox-call-shift / sandbox-translate（allow-all 配置、call 68 跳过）与 k27-sandbox-native；27 Sandbox 直接吃 27 配置，try66 不带任何开关：桌面、零崩溃、拒绝同前。这些启动参数（droidvm-app.py 仍会传）现在被忽略。仍保留 mac-amfi-launch-permissive（待验证是否还需要）。
- [x] 5 接口结构体核对（IDA）：`amfi_t`（TrustCache v5 多一项，已补）、OSEntitlements 槽序同 26.5、mac_policy_ops 同 26.5（lookup_preflight 多 flags 参数，已补）。
- [~] 6 原生 kext：DroidVMDisplay 已按 27 重生 ABI、能出帧；部分偏移待核实（见优先级 3）；DroidVMEthernet 加 NoBSDWait（IOResources 自锁）。
- [~] 7 已到桌面（自动登录、Dock、home 正常）；待对比主线功能（Safari、第三方 App/AMFI）。

## 当前优先级（用户定 3 5 4 1 2 → 按序：磁盘映像、AMFI、显示偏移、mds、沙盒拒绝）
- [x] 磁盘映像：保留旧 DiskImages kext；随机卡死=DroidVMEthernet 自锁，已修，DI 默认保留。
- [x] AMFI copyDictionary panic：CEElementIterate 栈页偏移检查，GOT 改绑修复（不改 AMFI 字节），40d4c05 绕法已撤。
- [x] 显示偏移核实：全部与 27 一致，代码不用改（见“显示偏移核实”一节）。
- [x] mds 崩溃循环（exc 10）：mds.sb 末行 `(deny file-read* (file-attribute union-mounted-filesystem))`，Sandbox 用 vfs_flags 判 MNT_UNION，而我们的根是 SystemOS 的 union 挂载 → mds 读不到根上任何东西（SystemVersion.plist）就 abort。内核 vfs_flags 对“盖在根卷根目录上的挂载”隐藏 MNT_UNION（k27-root-union-visible=1 恢复），kern_exec.c 自己的检查改读 mnt_flag。try62：零崩溃。
- [x] 沙盒拒绝 A（根条目）：内核真 firmlink（b84cfb2，见 try61–62）。Sandbox 字符串补丁已删除。
- [x] 沙盒拒绝 C：.TemporaryItems 已修（方案 B：Data 挂 /System/Volumes/Data + 真机布局 + /private firmlink，内核 de67fea，见 try63–65）；mach-lookup 与 /var/empty/Library、kernelmanagerd TMPDIR 为设计内/Apple profile 自身问题，不修。
- [ ] iconservicesagent 写 m2v 缓存（/private/var/folders/zz/.../C/com.apple.iconservicesagent/m2v）与 /private/var/root/Library/Caches/native-metal-shaders 被拒：我们 Metal 翻译层的缓存位置问题。
- 旁支：cryptexd 已禁用（真因 hdi_copy_grafted Preboot）；mobileactivationd 内核拒绝 exec（真因无 OIC/UCRT）。

## 记录

- 2026-10-30 `cluster_update_range_with_callback`：27 先校验（off+len ≤ round_page(filesize)），再按 64 MiB 块调回调（PAC 类型判别值 35639 =
  `int(*)(ptr, 5×int64, ptr)`，已用 clang 核对），然后做的正是 12377 `cluster_update_state(vp, s, e, FALSE)` 的内部调用。
- `*_with_length`：match/set_compilation_service 的参数是 {64 字节 hash, size_t 长度} 结构指针；query_trust_cache_with_length(type, hash, len, token)；
  csblob_get_cdhash_with_length(blob, uint8_t *len)。image4_v2_* 在 macOS 27 就是桩（8，空参数 3）。
- 2026-10-30 首次上机（try1–3）：KC27 能启动，安全 kext、APFS 都起来了，约 5 s 时 panic：`"Image4: unable to initialize magazine: 7" @IOKit.cpp:45`
  （27 新拆出的 Image4 kext，Image4::start → magazineInit → image4DeviceGetBootManifestHash 读 /chosen/boot-manifest-hash，缺失返回 7；
  26.5 AppleImage4 同样读不到但不 panic）。修：`scripts/run-macos-vm.py` 在 `MACOS_BOOT_MANIFEST_HASH=1` 时给 /chosen 加 48 字节全零
  boot-manifest-hash（主线不设此变量，不受影响）。panic 后 xnu 直接 PEHaltRestart 复位 VM，所以前几次只看到 “MACH Reboot”/卡住。
- img4 v1 接口表（AppleImage4 注册）27 与 26.5 完全一致：版本 20，槽位形状相同。
- try4（加 boot-manifest-hash 后）：magazine 初始化通过、12 个 nonce 槽全部 reset，接着 panic `encryption failed: 0xe00002c7`：AppleImage4 27
  `_darwin_el2_entangle_nonce` 用 IOAESAccelerator::performAES、硬件密钥 selector 2212（keyData {bits 128, selector 2212}）做 nonce
  entangle，NativeAES 只认软件密钥 → Unsupported → panic。修：k27 版 NativeAES 对 2212 用固定软件密钥（`k27/build-native-aes.sh`）。
- 坑：panic 停住的 VM 之后 smoke 的 start 可能连续 3 次 "failed to start VM"；`droidvm-app.py status` 看到 STOPPED 后手动 `start` 即可（启动盘已推好）。
- try5（k27 NativeAES）：Image4/AppleImage4 全过，26 s 挂上根卷（disk3s1 Macintosh HD），停在 `is_root_hash_authentication_required: Root Volume,
  root hash authentication is required`（无 panic）。27 APFS 的判定：Root Volume 类只看 csr_check(CSR_ALLOW_APPLE_INTERNAL 0x10)，不再看
  CSR_ALLOW_UNAUTHENTICATED_ROOT（日志 "ARV disabled: 1" 也没用）。先试 MACOS_LP_SIP0=0x12；不行就在 kc-build27 里给 APFS 打补丁
  （0xfffffe0009bafbb4 `cmp w20,#0` → 看 w21，即回到 26.5 的 ARV 语义）。
- try5/try6：根卷挂上后停在 `is_root_hash_authentication_required ... is required`；但 26.5 APFS 的判定逻辑完全相同（主线也走 "required"），
  所以这不是差异点。MACOS_LP_SIP0=0x12 不改变 internal build=0（没用）。rootvnode 已设、initproc 为 0、owner 链状态全是 -1（没开始），
  sched_tick 停在 ~22 s 不再走、stall-dump 的 thread_call 也没执行 → 整机级停顿（不是单线程阻塞）。
  APFS 不读 boot-manifest-hash（排除了 ADT 改动的嫌疑）。下一步：stall-panic 拿所有核 PC。
- try10（stall-dump=12）：12 s/24 s 两次栈：IOFindBSDRoot 等根盘；两个 NativeVirtioBlock::start 卡在 delay 循环（根盘 26 s 才出现，主线同一份对象）；
  AMFI 的 AKS/ACM 线程在等服务（主线也这样）。之后 36 s 的 dump 没出现，8 个核的 cpu_stat.timer_cnt（cpu_data+0x230）全部不动 → 整机冻结。
- try11（wfi=0）：不冻结，改为 panic `rootvp not authenticated after mounting @bsd_init.c:1114`：27 APFS 的 FSIOC_KERNEL_ROOTAUTH
  （handle_kernel_rootauth → is_root_hash_authentication_required → handle_eval_rootauth）真的去校验密封根卷；26.5 遇到
  CSR_ALLOW_UNAUTHENTICATED_ROOT 就放行。修：try.sh 默认带 `rootauth=0`（port 已有开关）。冻结是否就在这条校验路径上，看 try12。
- try12（rootauth=0，默认 wfi）：越过 rootauth，挂根、"userspace boot"、exec launchd 之后整机冻结（timer_cnt 不动）。WFI 冻结与 rootauth 无关，
  像是 Gunyah 对 WFI 核的唤醒问题；诊断时先固定 wfi=0。
- try13（wfi=0 panic-spin=1）：panic `PAC failure ... DA key while authing x16` 于 safeMetaCast+0x24 ← OSEntitlementsBridge_matchBool+0x28 ←
  IOCurrentTaskHasEntitlement ← set_exception_ports_validation ← host_set_exception_ports ← ux_handler_setup ← bsdinit_task。
  x0 是 proc（第二个字 = &allproc）。根因：27 AMFI 的 `TrustCacheInterface_t` 版本 5，在 getUUID 后多一个 `trustCacheQueryWithLength`，
  amfi_t 中 TrustCache 之后的 OSEntitlements/MTE 全部后移 8 字节；内核 `amfi->OSEntitlements.queryEntitlementBooleanWithProc`（+448）
  于是落到 matchBool，把 proc 当对象。27 注册的表基址 0xfffffe0007b3d4d8（_initializeCoreEntitlementsSupport），第 0 项仍是 invalidate；
  CoreEntitlements 段、OSEntitlements 段、MTE 段的槽位顺序与 26.5 相同。修：k27 树 libkern/libkern/amfi/amfi.h 给 TrustCacheInterface_t
  末尾补 queryWithLength。顺带核对：AMFI/Sandbox/Quarantine 的 mac_policy_ops 槽位 27 与 26.5 一致，27 新增 hook 都在 12377 的 reserved 槽。
- try14/15（amfi.h 修复后，wfi=0）：PAC panic 消失，launchd（initproc）起来，挂完 SystemOS（native_owner_cache_stage=6、status=0）。
  try14 根盘 100 s 才出现（偶发，try15 是 27 s）；try15 在 ~28 s 整机冻结（8 核 timer_cnt 不动、sched_tick=196），停在 Data 挂载前
  （native_owner_data_stage=0，但 NativeRamBlock persist_state=2、attachStore 已完成）。冻结点每次不同（try10 36 s、try12 launchd 后）。
  `k27/cpu-stacks.py`（cpu_data/线程栈/中断现场，偏移见脚本头）：CPU0–6 都在 idle 里被中断、仍在中断处理中（int_state 非 0），
  中断栈残留 cpu_signal_internal / thread_timer_expire / os_log→putchar；CPU7 不在中断，栈上 NativeVirtioBlock::doAsyncReadWrite →
  biodone → thread_wakeup。像是 CPU7 持锁/卡在宿主，其余核关中断自旋。宿主侧 8 个 vCPU 线程全 R（Gunyah 下无区分度）。
  下一步：确认 CPU0–6 在中断里自旋的锁（读 IRQ 栈当前帧之外的手段：panic-on-spin 超时 / lck_spin 超时缩短 ml-timeout-lock-panic-scale）、
  CPU7 当前 PC；对照主线同一 NativeVirtioBlock 为何不冻结。
- 更正 try15：不是整机冻结，是 panic 死锁。try16 读 debugger_* 才看清：`offline owner SystemOS mount failed: 80`（EAUTH），
  native_owner_boot_manifest_status=3——为 27 Image4 预放的全零 boot-manifest-hash 挡住了 owner 清单发布。修 7b0eea5：全零且无 owner
  域标签时视为占位、允许覆盖。看“冻结”先跑 `k27/dbg-state.sh`（debugger_current_op=3 即 panic 中）+ `k27/panic.sh`。
- try17：Data 挂上、/sbin/launchd 起跑，随后“冻结”：CPU6 在 launchd open()→namei→mac_vnode_check_lookup_preflight PAC 失败 panic，
  panic 打控制台时等 vc 的 ticket 锁，而持锁的 CPU3（vc_paint_char 滚屏）被 DebuggerXCall 停住 → 死锁、无 panic 文本。
  根因：27 的 mpo_vnode_check_lookup_preflight 末尾多一个整型 flags（Sandbox 27 读 w5 的 bit0–4），PAC 类型判别 0x421a→0x3ad2
  （clang __builtin_ptrauth_type_discriminator 核对：任意整型第 6 参都是 0x3ad2）。修 03f4434：typedef 加 int flags、调用传 0（语义待对齐）。
  全部 7 个策略 kext 的 DATA 里函数指针判别值 26.5 vs 27 只有这一处变化（/tmp/opsdiv2.py 思路，AMFI ops 运行时填写未覆盖）。
- try18（03f4434 后）：launchd 正常跑起 sh/bash，接着 panic `AMFI: failed to create OSDictionary copy: 14 @OSEntitlements.cpp:863`：
  launchd posix_spawn → load_machfile/process_is_plugin_host → IOVnodeHasEntitlement → copyClientEntitlementVnode →
  cs_entitlements_dictionary_copy_vnode → 27 AMFI OSEntitlements::copyDictionary → CEContextCreateAsOSDictionary → CEElementDeserialize
  某个分配/追加回调返回 NULL（14）。这些回调与 26.5 逐条相同（OSString::withCString(p,len)/OSSymbol/OSData/OSNumber、setObject 槽 62/61），
  根因未定（数据侧？）。绕法 40d4c05：copyClientEntitlementVnode 改走 amfi->OSEntitlements.copyEntitlementAsOSObject（单项查询）。
  （已过时：根因是 CEElementIterate 栈页检查，GOT 改绑已修，40d4c05 已撤。）
- try19（40d4c05）：无 panic，2 分钟内 pid 到 300+：xpcproxy、xprotectd、fskitd、apsd、powerd、bluetoothd、mobileactivationd、
  cfprefsd、containermanagerd、lsd、WindowServer(118)、loginwindow 都起来了；有个别 Corpse（apsd 等崩溃，ReportCrash 处理）。
  sandbox-call 日志里大量 call 4 error 45 / call 1 error 22 (ignored)：是 mac-sandbox-permissive 的放行，下一步关掉它（阶段 4）看 27 Sandbox 原生是否成立。
  KC 里还没有 DroidVMDisplay/Input/Gpu（阶段 6），所以无画面是预期。注意：手机前台可能是用户在用，不要用 screencap 看 VM。
- 阶段 4（1f8206f）：`k27-sandbox-native=1` 关掉 mac-sandbox-permissive（droidvm-app.py 把 =1 放在命令行最前，首个匹配生效，所以只能在内核里关）。
  try20：27 Sandbox 原生生效（"Sandbox apply" 各进程自带 profile、正常 deny 报告），不需要 26.5 时代的 allow-all 替换。
  try21：kernelmanagerd 被拒 renamex_np → brk 崩溃 → 关键进程退出 panic（exit reason ns 2 subcode 5）；deny 集中在 /private/var/.data/...
  （系统卷用符号链接 /Library→/private/var/.data/Library 冒充 firmlink，profile 按 /Library 写），另有 "syscall_check_sandbox: canonical check failed"。
  修 275ea46+a273781：build_path_with_parent 外包一层，`/private/var/.data/X` 读回为 `/X`（k27-firmlink-paths，默认开；BUILDPATH_NO_FIRMLINK
  不改；带 mntpt_outlen 的调用置 0，同 xnu firmlink 路径）。Sandbox 27 用 vn_getpath_ext_with_mntlen。
  try22：无 panic；.data deny 与 canonical 失败归零，kernelmanagerd 不再崩。剩：apsd、mobileactivationd 循环崩溃（主线是否同样待对照），
  /private/var/.TemporaryItems 下 file-write-create 被拒（真机该在 /System/Volumes/Data/.TemporaryItems），tccd/timed/windowserver mach-lookup deny。
- 阶段 6 DroidVMDisplay（k27/build-native-display.sh → out/x12377/native-kexts/k27-DroidVMDisplay，k27/kext/DroidVMDisplay.json，
  try.sh 的 MACOS_DISPLAY=1 已改用它）：gen-iomfb-abi.py 对 kc27 重生头文件（Legacy 实例 0x1af8→0x1dd8；27 删 get/set_programfifo_blocked_state、
  get_diags_handler，加 task/genlock/LPR 方法）。硬编码偏移用 `k27/offset-map.py 函数 偏移...`（两版同名函数指令对齐）迁移：
  Legacy：6032→6720 6040→6728 6048→6736（clear_up_swap_queue_gated、dropSwap_gated）；6400/6404→7152/7156（display_width/height）；
  6412→7164 6436→7188（swap_wait_gated）；6428/6432→7180/7184（do_power_state_change_action_gated）；6902→7634（推定：6900→7632 于
  systemWillShutdown、6901→7633，未直接验证）；264、140 不变。IOMFBSwapIORequest：752→912 816→976 820→980 824→984 844→1004（+160，
  update/record_swap_info_state、swap_queue、dropDummySwaps）；2752→2944 3192→3384 3200→3392（+192，queue_move_entry_gated）。
  未验证：IOMFBNotifyRequest 24/120/128、IOAVElement 16/24、timingData 各字段（IOAVFamily）。KC 链接：4 个原生 kext 虚表 0 问题槽。
  注意：符号表里不少 Legacy 方法是 ICF 合并的空桩（如 swap_begin_gated），对齐要挑有实体的函数。
- try23/24（MACOS_DISPLAY=1 [+MACOS_GPU=1]）：DroidVMDisplay 起来（1920x1080@120，display on）、DroidVMInput 四个服务起来、无 panic；
  WindowServer 每 ~30 s 崩溃重启（无 Metal 设备，同主线旧坑）→ 无登录界面。try24 带 GPU kext 但 "droidvm-gpu: no droidvm-gpu device"：
  app 里注册的 VM 模板没有 --droidvm-gpu（要 MACOS_GPU=1 [MACOS_NET=1] droidvm-app.py register + prepare，改的是用户 app 的 VM 配置，先问）。
  用户反馈 CPU 特别高：wfi=0 让空闲核空转（冻结已查明是 panic 死锁，不再需要 wfi=0），加 apsd/mobileactivationd 崩溃循环。以后默认不带 wfi=0。
- try25–27：VM 注册模板本就有 --droidvm-gpu/--virtio-mmio-net/--virtio-mmio-gpu；ADT 要与之一致，启动要 MACOS_GPU=1 MACOS_VIRTIO_GPU=1
  MACOS_NET=1（只设 GPU 时 droidvm-gpu 报 no device）。WindowServer 只开 type 5（原 IOGPU）→ 30 s abort（crash-log：exc 10 于 SkyLight），
  根因是默认 Data 种子里没有 Metal 插件：主线用 MACOS_DATA_SEED=out/metal/stage/scratch-data.img MACOS_TRUSTCACHE=out/metal/stage/
  kernel.macho.trustcache（stage-gpu-plugin.py 产物；换种子 data-store 从空白开始，用户已同意）。try27 带上后：WindowServer 不再崩，
  1400+ GPU 对象，loginwindow 以 0x4147 打开加速器。剩 cryptexd（exc 10）、mobileactivationd、apsd 崩溃循环。不再带 wfi=0（CPU 高）。
  标准启动：MACOS_DATA_SEED=… MACOS_TRUSTCACHE=… MACOS_DISPLAY=1 MACOS_GPU=1 MACOS_VIRTIO_GPU=1 MACOS_NET=1 k27/try.sh SECS panic-spin=1 k27-sandbox-native=1

## try29–31（2026-10-30）无登录界面定位
- WindowServer 主线程在 IOMFBDisplay::finish_update→swap_set_layer（set_icc_matrix_and_trc 报 os_log error），说明在出帧。
- 新内核诊断（IOUserClient.cpp，iokit-log=NAME）：每个 (类, selector, 返回值) 首次打印。IOMobileFramebufferUserClient 5（swap submit，1760 字节）→ 0xe00002c2。
- 27 IOMobileFramebufferLegacy::swap_submit：每层 surface ID（rec+156）用 IOSurfaceRoot::lookupSurface([this+6976], id, current_task) 查，非零 ID 查成 NULL → 静默返回 706（0x94c0de4 cbz → 0x94c1170），走不到 swap_queue/verify_swap，所以 "first swap submitted" 从不出现。
- vtable 已核对：DroidVMDisplay 的 swap_submit=284、verify_swap=417、do_power_state_change_gated=419，与 27 一致。
- try31：out/k27/src 的 DroidVMDisplay 副本（未改 overlay）在 swap_submit 失败时打印 ids/root/lookup 结果，已编进 k27-DroidVMDisplay，未拿到输出（用户因 CPU/GPU 占用过高停机）。
- 下一步：取这条日志，看是 root 指针错、ID 错位（rec 布局）还是 lookupSurface 本身（userClientForTask/find_surface）失败。

## try32–34：无画面根因已修
- 真正原因：主线 DroidVMDisplay 在 start 里注册 virt_set_external_method_hook(convertSwapRecord)，把 27 的 1760 字节 swap 记录裁成 26.5 的 1416 字节；k27 的 IOMFB 是 27 自己的，派发表 selector 5 要 1760（0x6e0）→ IOUserClient2022::dispatchExternalMethod 尺寸检查 0xe00002c2，帧全丢，WindowServer 不停重交（CPU/GPU 高）。
- 之前的 lookupSurface 推断是错的（静态读代码推测，实际根本没进 swap_submit）。
- 修复：k27/build-native-display.sh 的替换表把注册换成 (void)convertSwapRecord。try34：selector 5 → 0x0，first swap submitted，172 提交 164 显示，最高 37 帧/秒，零拷贝 scanout 格式 RGhA。
- 内核：97f9ce0 iokit-log 打印每个 (类, selector, 返回值) 首次调用。
- 剩：cfprefsd 读 /Users/droid/Library/Preferences 被拒（firmlink 路径），cryptexd/mobileactivationd 崩溃循环。

## try35–36：home 无法访问（登录后弹窗）
- try34 已到桌面（droid 自动登录、Dock），但弹 "home folder isn't located in the usual place"：cfprefsd/contactsd/calaccessd 读写 /Users/droid/Library 全被拒，另有 syscall_check_sandbox "canonical check failed for /private/var/.data/Users/..."。
- Sandbox verify_path_is_canonical：用户路径≠内核推导路径时，只把 "/System/Volumes/Data/X" 当作 /X。k27/kc-build27.py 在 KEPT_CODE_PATCHES 里把 Sandbox 的该字符串（0xfffffe00077243dd）改成 "/private/var/.data"（三处使用都先 strlen）。try35：canonical 失败消失，home 拒绝仍在。
- home 规则来自 realpath 过的 HOME_DIR（realpath 跟随 /Users 链接 → /private/var/.data/Users/droid），而内核把它改写成 /Users/...。内核 fde0a17（vfs_cache.c k27_firmlink_keeps）对 /Users 不改写。try36：home 拒绝全部消失。
- 剩：mds 读 /Users 元数据被拒（少量）、.TemporaryItems 创建被拒、tccd mach-lookup。

## try37–39：cryptexd / mobileactivationd 崩溃循环
- 根因同类：都要在只读 union 根上建状态目录。cryptexd daemon_init → mkdirat(/System/Volumes/Preboot, "com.apple.security.cryptexd") 失败 → os_crash（还要 /var/db、/var/run 同名目录）；mobileactivationd main → create_required_directories(/System/Volumes/Hardware/MobileActivation/{internal,logs}) 失败 → os_crash（Failed to create required directories）。真 macOS 上 Preboot/Hardware 是同容器的独立可写卷。
- 试过：① tmpfs union 挂载（mount_tmpfs 支持 -o union）：kc27 有 tmpfs kext，但 k27 内核 __TEXT_EXEC 长进了未保留 kext 的空间，tmpfs 正在其中（内核代码覆盖它）→ kernelmanagerd 加载 tmpfs 时 _start 数据异常 panic。保留 tmpfs 需要重新布局，不可行。② hdiutil ram:// + newfs_hfs + mount -o union：attach 失败 "Device not configured"（k27 上磁盘映像不可用）。③ xnu firmlink 只管路径拼接，查找重定向由 APFS 做，union 根上没用。
- 种子已恢复（scratch-data.img.before-tmpfs.bak）；/tmp/k27-seed-job.py 是往种子加 LaunchDaemon 的脚本。
- 剩下的路：在 systemos.img 里建目录（主线共用 11G 产物、要重新推手机，cryptexd 后续还可能失败）；或用 launchd disabled.plist 禁用这两个守护进程（目前它们本来就不可用）。
- try40（用户选“改 systemos.img 补目录”）：systemos.img 原地加 `System/Volumes/Preboot/com.apple.security.cryptexd`（真目录，cryptexd 用 O_NOFOLLOW 打开）和 `System/Volumes/Hardware -> /private/var/.data/System/Volumes/Hardware`（内核 firmlink 改写回 /System/Volumes/Hardware，符合 mobileactivationd 的沙盒规则）；Data 种子加 `.data/System/Volumes/Hardware`（/tmp/k27-seed-hardware.py）。只改了 7 个 1 MiB 块，按块 dd 推到手机，整文件 sha256 两边一致，.sha 更新为 5b3accedf8aec469。结果：运行 20 分钟，990–1220 s 窗口内两个守护进程零崩溃（之前约 10 s 一次）。

## try41–43：磁盘映像（优先级 1）
- hdiutil attach "Device not configured" 的根因：hdiutil/DiskImages.framework 走旧驱动 IOHDIXController（"DI_kextExists: cannot find IOHDIXController object"，kIOReturnNoDevice），kc27 里有 com.apple.driver.DiskImages 及 5 个后端，但不在 keep 列表。它们的地址和 k27 内核段、native kext 都不重叠（不像 tmpfs）。k27/try.sh 加 DI_KEXTS 保留它们。try43：`hdiutil attach -nomount ram://2048` → /dev/disk6，内核识别为 disk image。
- 顺带：cryptexd 现在会走到 codex_init，它要在 Preboot 状态目录下建 Cryptexes（_states 表 flags 7）→ systemos.img 已补 Preboot/com.apple.security.cryptexd/Cryptexes（推送 5 块，sha ee8e625b4997f7b8）。之后 cryptexd 卡在 hdi_copy_grafted("/System/Volumes/Preboot") → "Failed to copy grafted system cryptexes"：这里的 cryptex 是系统镜像里的普通目录，不是 APFS graft。
- 更正 try40 的结论：mobileactivationd 只是按需启动，990–1220 s 没崩不代表修好。try43 里它过了建目录这一步，又在 dealwith_activation 的 "Failed to validate OIC" / "Invalid UIK/UCRT"（设备身份证书/密钥，VM 没有）处 os_crash。两者都还在崩溃循环（约 15 s 一次）。

## try44–50：禁用 cryptexd / mobileactivationd + 随机开机卡死
- 禁用：cryptexd 用种子的 launchd disabled.plist（try44 起它不再启动，/tmp/k27-seed-disable.py）；mobileactivationd 本来就在 disabled.plist 里却照样被拉起（UniXNU-droidvm 的 DroidVMLaunchPolicy.c 也记了：launchd 不认种子里写的 disabled.plist），改用内核 `k27-deny-exec=PATH[,PATH]`（默认 /usr/libexec/mobileactivationd，exec 返回 EPERM，提交 kern_exec.c）。try50：0–180 s 两者零崩溃，桌面正常。
- 随机卡死：保留旧 DiskImages kext 后 8 次启动有 5 次（try42/44/45/47/49）WindowServer 不起来。链条：loginwindow 等 WindowServer + RunningBoard 握手；runningboardd 主线程卡在 contentsOfDirectory → FSMountPrepare → FileIDTreeGetCachedPort → scCreateSystemServiceVersion("FileIDTreeStorage") → scsclient_FindService；coreservicesd 本身空闲（主线程 runloop、一个线程在 fseventsf_read）。加 DI kext 之前十几次启动都正常。
- 暂时撤掉 DI kext：k27/try.sh 里改成 K27_DI=1 才保留（hdiutil 回到 Device not configured）。待查：FileIDTreeStorage 服务由谁注册、为什么有 DI kext 时有时注册不上。

## try51–54：DI 随机卡死根因 = DroidVMEthernet 在 IOResources 匹配里自锁
- 链条往下追：WindowServer 主线程 confstr → mbr_uid_to_uuid → od_rpc_call 等 opendirectoryd；opendirectoryd 31 个线程都在 dispatch_sync 等同一个队列，持队列的线程卡在内核 gethostuuid → IOBSDGetPlatformUUID → waitForService(resourceMatching("IOPlatformUUID"))。
- kernel_task 采样（sample-pid=-1）：唯一卡在 startCandidate 的是 IOResources 配置线程里的 DroidVMEthernet::start → IONetworkController::start → waitForService(resourceMatching("IOBSD"))。资源等待要求 IOResources 有 kIOServiceMatchedState，而它要等自己这一轮 doServiceMatch 结束才置位 → 自锁。诊断日志（IOService.cpp waitForMatchingServiceWithToken，BCM2837）：98 s 时 IOResources state 0xa/0x84020002（未 matched、ConfigRunning），所有资源等待（IOPlatformUUID、IONVRAM…）全卡。
- 随机：DroidVMEthernet 的 IOResourceMatch 是 IOBSD；IOBSD 若在 IOResources 首轮匹配结束后才发布，DroidVMEthernet 在后续轮次启动（matched 已置位）就没事；DI kext 让首轮变长，IOBSD 落进首轮就死锁。
- 修复：DroidVMEthernet 覆盖 getFeatures() 返回 kIONetworkFeatureNoBSDWait（IONetworkController.cpp:289 跳过等 IOBSD；IOBSD 已由 IOResourceMatch 保证）。重编：`python3 scripts/build-native-kext.py DroidVMEthernet overlay/kext/DroidVMEthernet.cpp overlay/kext/NativeKextGlue.cpp -I $PWD/out/x12377/inc-net -I $PWD/overlay/droidvm/drivers/NativeVirtioBlock`（失败时会删掉旧 .o）。主线 26.5 共用同一源码，同样受益。
- 验证（try51–54，K27_DI=1）：4/4 正常到 WindowServer（修前 8 次卡 5 次，修前最后 3 次卡 2 次）；7.6 s 时 IOResources 已 0x1e（matched），不再有 IOBSD 等待；en0 照常 attached、MAC 02:44:56:4d:00:01。DI kext 改回默认保留（k27/try.sh，K27_DI=0 才不留）。

## try55–60：AMFI copyDictionary panic 根因（优先级 2）
- 27 AMFI 与 26.5 AMFI 的 CEContextCreateAsOSDictionary/CEElementDeserialize/回调逐条相同；KC 里 GOT 指向的 OSString/OSDictionary 等也正确。
- 诊断（已删，思路记下）：copyClientEntitlementVnode 里 ① 用内核 OS 对象按同样规则重建 DER 权限——全部成功；② 从 OSEntitlements 只读数据 +0xd0 取 AMFI 自己的 CEContext，直接调 AMFI 的 create → 绝大多数进程 14；③ 同一上下文用 AMFI 的 CEDictionaryIterate + dictionaryIterate 逐项 → 全成功。坑：内核开了函数指针类型判别，整数强转函数指针会先 autiza（PAC panic）；要在 uintptr_t 上 sign 再 memcpy；AMFI 回调判别值 0xe4fe。
- 根因：CEElementIterate 开头 `if ((sp & ~(-1 << PAGE_SHIFT_CONST)) < 0x80) return 2`。内核栈按页对齐，固定调用链上 sp 页内偏移固定；k27 内核的栈帧让每次 spawn 的 exec→IOVnodeHasEntitlement→copyDictionary 恰好落在 <0x80 → 2 → 14 → panic。launchd（load_init_program 链）和诊断调用（多几层帧）偏移不同，所以成功。只此一处用 PAGE_SHIFT_CONST。
- 修复：k27/kc-build27.py KEPT_CODE_PATCHES 把 0xfffffe0008625308 的 b.lo 改 nop。验证：带诊断 0 次失败（修前 577 行）；撤掉 40d4c05 绕法（c34cad6）后原版整字典路径无 panic、WindowServer 出帧。
- 改为不动 kext 字节（用户要求）：撤掉 b.lo→nop，改成链接期改绑——AMFI 唯一引用 PAGE_SHIFT_CONST 的 GOT 槽 0xfffffe0007b439c8 绑到内核新变量 k27_amfi_page_shift=31（掩码 0x7fffffff，sp 低 31 位 <0x80 实际不会发生）。kc-build.py 加通用 KEPT_POINTER_REBINDS（站点, 内核符号），kc-build27.py 用它；内核提交在 arm_vm_init.c。上机：无 panic、WindowServer 出帧。

## Apple kext 改动清单（2026-10-30，决定：不追求零改动；替身/IOTimeSync 闸门/AMFI 改绑保留，Sandbox 字符串随 firmlink 一起去掉）
- 改字节：无（Sandbox 字符串补丁 2026-10-30 try62 起已删，KEPT_CODE_PATCHES 为空）。
- 改链接：AMFI 的 PAGE_SHIFT_CONST GOT 槽改绑；ARMPlatformStandIn 顶替 AppleARMPlatform/AppleIISController/AppleAudioClockLibs（14 个指针改绑，0 跳转）。
- 改 personality：IOTimeSyncRootService 加 IOResourceMatch=DroidVMEthernet。
- 重链接本身：k27 上所有保留 kext 都是 0 branches retargeted、无 stack checks。
- （已过时，firmlink 后不再需要）Sandbox 补丁曾必要：K27_SB_PATCH=0 试跑，backgroundtaskmanagementd 对 /private/var/.data/Library/LaunchDaemons/*.plist 报 canonical check failed（用户态 realpath 跟着 /Library 符号链接走到 .data）。不动 kext 的出路是内核真正实现根上的 firmlink（查找重定向 + 路径报告为 /Library），见下方待定。

## 显示偏移核实（优先级 3，静态，未上机）
- 依据：kc27 里也有 AppleParavirtDisplay（com.apple.driver.AppleParavirtGPUIOGPUFamily），DroidVMDisplay 照它写；两版 119 个函数逐个反编译比对数值。
- 27 的 AppleParavirtDisplay 直接用到、与 build-native-display.sh 的表一致：notify_swap_done_gated 6720/1004/264/912/976、kSwapInfoHeld **7634**（之前是推定，现已证实）；start_hardware block 7180、kHardwareStarted 140 不变；set_digital_out_mode block 7152/7156；program_hardware_gated 984/2944(+8·i)；swap_begin/clean_queue 6720/6728/6736、3384/3392。
- IOMFBNotifyRequest：set_notify_tag_mask_gated / do_swap_info_notify_gated 两版相同（+24 异步引用、+120 掩码、+128 上次时间）。
- IOAVElement：createTimingElementWithDimensionsAndRate / createColorElementWithDepthAndEDR 两版相同（ID +16、score +24）。
- IOAVVideoTimingData（IOAVFamily）：元素数据仍在 +32；27 的 getter 只多了边界检查，偏移同 26.5（每轴 32 字节：total +4、active +8、sync width +12、back porch +16、front porch +20、sync rate +24、polarity +28）；IOAVVideoTimingGetPixelClock 逐字相同（+68 像素时钟，+56 垂直刷新率 16.16 定点 → rate<<16 正确）。
- 未在 APD 中出现、沿用 offset-map 结果：kAPIPowerState 7184、kHardwarePowered 7188、swap_wait 的 7164、IOMFBSwapIORequest 980（+160 区段）。

## try61–62：根上真 firmlink + mds（2026-10-30）
- 内核 b84cfb2：MASTER.arm64.bcm2837 开 config_firmlinks；kern_exec.c 在 Data 挂载后（stage 4）native_owner_firmlinks_prepare（k27-firmlinks，默认开）把 /Applications /Library /Users /Volumes /cores /opt /usr/local /System/Library/Caches /System/Volumes/Hardware /private/etc /private/tmp 设为指向 Data（.data/... 与 /private/var/tmp）的 firmlink，日志 `k27: firmlink X -> Y: 0`；vfs_lookup.c 慢路径对文件系统返回的 firmlink 源切到目标（删/改名的末分量除外），目标的 ".." 回源的父目录。源不是目录（旧 systemos.img 的符号链接）就跳过。
- systemos.img 原地把上述 11 个符号链接换成空目录（root 755），改了 9 个 1 MiB 块，按块推手机，sha d6fe86b76ae0a48d。**注意：主线（12377 内核，无 firmlink 设置）用同一个 systemos.img 时这些目录是空的**；要回退就在这几个路径重建符号链接（目标见 scripts/make-macos-systemos.sh），make-macos-systemos.sh 尚未改。
- 结果（K27_SB_PATCH=0，无 Sandbox 字符串补丁）：/Library /Users /Volumes /Applications 等元数据拒绝、canonical 失败、home 拒绝全部消失；桌面正常。vfs_cache.c 的 k27-firmlink-paths 改写和 /Users 例外已在 de67fea（Data 挂 /System/Volumes/Data + 真 firmlink）中删除。
- try62（加 vfs_flags 隐藏根 MNT_UNION）：mds 不再崩溃也无读拒绝；整次启动无崩溃。剩余拒绝见 C 项。

## C 项分析（2026-10-30，静态）
- .TemporaryItems 根因：libsystem_coreservices `_dirhelper_relative_internal`（NSItemReplacementDirectory 用它）对目标路径 statfs：f_mntonname 为 "/"（根上 firmlink 路径会改用 statfs("/System/Volumes/Data")）或 "/System/Volumes/Data" → `$TMPDIR/TemporaryItems/`（profile 允许）；否则 → `<挂载点>/.TemporaryItems/folders.UID/TemporaryItems/`。我们的 Data 挂在 /private/var，所以全落到 /private/var/.TemporaryItems，被 trustd/locationd/dasd 等的 profile 拒绝（它们的 profile 本来就不写 TemporaryItems）。不改 Apple 代码的修法 = 方案 B：Data 挂到 /System/Volumes/Data，/private/var 作为指向 Data 根的 firmlink。
- mach-lookup（tccd/tccd.system/timed/findmy 等）：searchpartyd、coreduetd、systemstats、contextstored 的 27 profile 本身就不允许这些服务（162 个 profile 里只有少数写了 tccd），真机上同样被拒，属于设计内的良性拒绝，不修。

## try63–65：方案 B（Data 挂 /System/Volumes/Data）（2026-10-30）
- try63（Data 挂 /System/Volumes/Data，/private/var 作为指向 Data 卷根的 firmlink）：opendirectoryd 崩溃循环、无桌面。根因：27 的 realpath(3) 发现某路径分量是卷根时（lstat 与 statfs 的 f_mntonname 同 dev/ino）把路径换成挂载点 → /var/db/dslocal 变成 /System/Volumes/Data/db/...；PlistFile odm_create_connection_with_options 对不以 "/private/" 开头的路径 strstr("/private/var") 后直接 strlcpy（NULL）。定位法：崩溃 lr 在模块里，按 4K 页对齐反推加载基址（我们的内核是 4K 页，不是 16K），x1 指向的字符串核对基址。
- 结论：firmlink 不能指向卷根。Data 种子改成真机布局（private/{var,etc,tmp}、Library、Users、Applications... 在卷根；/tmp/k27-seed-layout.py，备份 scratch-data.img.before-layout.bak），firmlink 改为 /private、/Applications、/Library、/Users、/Volumes、/cores、/opt、/usr/local、/System/Library/Caches、/System/Volumes/Hardware。systemos.img 的只读大件从 /System/Volumes/Data/Library 挪到 /System/Library/DroidVMData/Library（sha 7471c9fec6f3a383），种子 4 个链接改指过去。staged apps union 改挂到 Data 的 Applications（firmlink 目标；挂在源上会被跟随绕过，try61/62 时内置 App 应该看不到）。删除 k27-firmlink-paths 改写与 /Users 例外。
- try64/65：桌面正常、无崩溃；.TemporaryItems 拒绝全部消失（dirhelper 对 f_mntonname 为 /System/Volumes/Data 的路径用 $TMPDIR）。首启（种子变化后的第一次）contextstored/secd/trustd 有一批 mkdir -p 逐级上溯的 create 拒绝，第二次启动不再出现。
- 诊断：k27-mkdir-log=NAME[,NAME] 打印这些进程失败的 mkdir（路径、错误码）。
- scripts/make-macos-data-seed.sh、make-macos-systemos.sh 已按新布局改（未重新生成、未提交）。
- 拖影排查（10-30）：Data 种子按新布局重建（artifacts/27.0.1/data-seed，旧的在 data-seed.23g93-layout；stage 种子旧的在 scratch-data.img.before-rebuild.bak；stage-gpu-plugin.py 路径改为新布局，未提交）。新 Data 仍有拖影 → 与 Data 状态无关。
  DroidVMDisplay 探针（droidvm-display-probe=1，复制线程里对左半 3 行算哈希）：只有 2 个缓冲轮换；拖动时同一次 swap 的同一缓冲在之后 1/2/4 tick 的刷新里内容还在变（40 帧 ≥3 个不同快照）→ swap 到达时 GPU 还没写完。
  下一步：swap 是否该等 GPU 完成（IOMFB 的 fence）；以及 CA 的 partial update / 前缓冲保留拷贝是否在读未完成的缓冲。
- [x] 拖影根因（10-31）：WindowServer 的壁纸是 4096x2160 双平面 YCbCr surface（登录 '444f' = 格式 503；桌面 'x420' = 505 + 543），
  build-metal-plugin.sh 10-26 为防 jetsam 拒绝 >1 Mpx 的 YCbCr 纹理 → 壁纸层永远不画，窗口移开处不重绘（不是 IOMFB partial update：
  swap 的 active regions 恒 0、src/dst 全屏；不是 GPU 池：WindowServer 自己从未分配失败；不是 Data 满）。
  修复 NativeMetal a9531ab（UniXNU 8d2f0e3）：前端 convertedYCbCrTexture 在 CPU 上把平面转成 RGBA8/RGB10A2（4K 约 35 MB、44 ms），
  按 surface ID+seed 缓存 4 项。用户确认正常。诊断补丁存于 research/debug-2026-10-30/（DroidVMDisplay 探针+swap 区域、GPU 分配日志）。
  定位手段：stage-gpu-plugin --log-stream '(process == "WindowServer" ...) AND messageType >= 16' + stderr-log=1，看
  "Failed to allocate MTLTexture from IOSurface"；refuseSurface 日志给出 surface 格式/尺寸。
- Data 卷 1 GiB 首登约 200 s 写满（ENOSPC 96 次）→ 种子改 --data-size-mib 8192（data store 窗口 2097217 块，16G 文件够）。
- [~] 启动慢、CPU 高、卡（10-31）：根子是 guest 内存/GPU 显存不够。5 GiB 里 wired 2.1–2.4 GiB（GPU 池固定 1 GiB）、空闲 <100 MB、
  开机 2 分钟磁盘读 12 GB（换页）。池满后 iconservicesagent、com.apple.dock.extra 的分配失败→立刻重试（"texture refused:
  OutOfMemory(Device)" 两万多次）把 CPU 吃满；每次失败内核还 vm_page_find_contiguous 扫完 120 万页 + zone_gc（num=16384 = 64 MiB）。
  已做（未提交，build-droidvm-gpu.py + NativeMetal bridge 补丁）：
  - GPU kext 池外回退：不要求连续的 BO 用 inTaskWithOptions（无物理掩码 → 不走连续搜索；逐页仍查 GPU 可达）；连续申请失败后 2 s 退避
    （只拦连续的；第一版连分散页也拦了，icon 永远拿不到内存）；大 BO 的"先试连续"（UserClient prefer_contiguous）只从池里拿
    （native_adreno_pool_only），池外不再扫描。实测扫描 26→0。
  - 运行时块 64→16 MiB（NativeMetal bridge/patches/0021-sixteen-mib-memory-blocks.patch）：WS 运行时显存约 620→310 MiB，
    分配失败 873→1、纹理 OOM 14→0（首登对首登）。>8 MiB 资源改专用块（ded 130–180 MiB）。
  - 诊断：NMB_FRAME_ROWS=1 编插件 + stderr-log=1，WS 每 20 s 打 MEM 行（pool 块(已放置) empty ded imp alloc）；VM 里 --top 30 也要 stderr-log=1
    才进日志（/tmp/k27-top.py 解析）。当前插件仍带 NMB_FRAME_ROWS=1，收尾要去掉重编。
  待做：iconservicesagent 首登仍占 ~400 MiB 显存、仍有少量失败（60 次）和 80–100% CPU（建图标缓存）；VTDecoderXPCService 解动态壁纸
  约 170 MiB；GPU 池 1 GiB 固定预留与实际用量的取舍。GPU kext 与 0021 已提交（主仓库 cebad87、NativeMetal 45c8294 / UniXNU c9afde8）；
  部署的插件仍带 NMB_FRAME_ROWS=1，收尾要去掉重编。
- [~] 无池（droidvm-gpu-pool-mib=0，BO 直接用 guest 内存逐 BO 导入）"冻结"（10-31）：不是冻结，是 panic 卡在打印路径。
  `pmap_assert_free: Found at least one mapping ... User CPU mapping`，栈：exit → task_terminate_internal → ipc_space_terminate →
  AGXDeviceUserClient::clientClose → releaseAll → freeBo → IOBufferMemoryDescriptor::free。进程退出时先关 IOKit 连接、后拆地址空间；
  dropViews 的 removeMappingForDescriptor 返回带引用的 IOMemoryMap 却从不 release → 用户 PTE 留着，页已还给 VM。有池时页回池不回 VM，
  所以一直没暴露。修：build-droidvm-gpu.py staged edit（unmap + release），pool=0 wc=0 连续运行 9 分钟以上不再冻结（之前 72/87/~100 s）。
  排查手段：`k27/dbg-state.sh`（debugger_current_op=3 即 panic 中）+ `k27/panic.sh`；research/debug-2026-10-31/k27-threadwalk.py 从宿主遍历线程表/各 CPU 状态
  （偏移按 out/k27 dSYM 与反汇编，kc-k27.nm 是旧的别用，内核符号取 kernel-k27.macho）。另：TLockTimeOut=0（ticket 锁不超时）。
  无池第二个问题"回到锁屏"（已修，cebad87）：首登时 WindowServer 纹理 OutOfMemory(Device) → SkyLight 断言 AddMemorylessTarget
  → 会话结束。BoAlloc 在 inTaskWithOptions 失败，kmem_alloc_guard 直接返回 KERN_NO_SPACE（2.6 ms，非缺页）：IOBMD 的缓冲区都映射在
  内核 DATA_SHARED 区间（kmem_ranges[6]，约 1.5 GiB，所有 kext 共用），DroidVMGpu 的 VM tag 峰值 973 MiB 把它占满（此时空闲物理页
  仍有）。修：池外的用户 BO（pooled && !contiguous && !wc）走 vm_page_alloc_list(KMA_ZERO) 拿页，不建内核映射，mapping_=nullptr；
  缓存维护走物理直映射（maintainImported），释放 vm_page_free_list。修后 DroidVMGpu tag 峰值 70 MiB，首登到桌面不再掉回锁屏。
  注意：这些页不再经过 pmap_assert_free，释放时若还有用户映射会静默破坏内存（靠 dropViews 修复 + mapping_leases 保证）。
  诊断：research/debug-2026-10-31/build-droidvm-gpu-alloc-diag.py.txt（失败返回点行号/状态 + kmem_alloc_guard 复试的 kr）、
  research/debug-2026-10-31/k27-kmapwalk.py（遍历 kernel_map 按区间/VM tag 统计）、research/debug-2026-10-31/k27-tagname.py（vm_allocation_sites → OSKextAccount 的 task_<bundle id>）。
  另：反复强停 VM 后 Data 一次因 unclean unmount 卡在 AppleAPFSContainer::start 等服务、占住 IOConfigThread，根盘永远等不到；
  旧 data-store 已改名 data-store.img.unclean-20261031 备份、新建空 store。导出头文件跨构建保留，构建脚本改头文件要可重入。
  待做：无池下长时间使用（设置/多应用/拖动）、画面正确性、导入耗时与内存占用（BO 缓存）；之后决定是否默认去池（pool-mib=0 wc=0）。
- 停 VM 时要连 xnu12377-smoke.sh 子进程一起杀：只杀 try.sh 会留下孤儿，它结束时会停掉/干扰新启动的 VM（10-31 一次会话被停）。

## GPU 迁 virtio-gpu 3D（drm2kgsl）（2026-11-02，方案 docs/k27-virtio-gpu-3d-plan.md）
- [x] P0 9f59276：传输层+3D 编进 DroidVMDisplay；NativeAdreno 挑入 virtgpu 提交（0x4149、0x7200 方法）；ADT drm-host-pool。
- [x] P1 28a93b8：patches/mesa-macos/0004（turnip-darwin-virtgpu）；启动参数 `vgpu-3d=1` 全部 Metal 进程走 virtgpu（不设=旧 droidvm-gpu 路线）。
  坑：DroidVMDisplay 扫描 blob 的资源号必须用传输层 resourceId()（自带计数撞 3D blob → ResourceCreateBlob InvalidResourceId）。
- [x] P2 fcc7b5a：swap_submit 记 droidvm_virtgpu_submitted()，拷贝线程扫描前等 droidvm_virtgpu_finished()（100 us 步长、200 ms 上限）。
  登录界面约 1/5 帧要等，均值 3–6 ms，0 次放弃。上游 display hold（编码线程晚提交）未移植。
- [x] 换插件不丢 Data 1914f41：`stage-gpu-plugin.py --base out/metal/stage/scratch-data.img --store 拉回的 data-store.img` +
  `droidvm-app.py store-patch`（旧块存手机 data-store.undo.*）。拉 store：VM 停后 `adb shell su -c 'cat …/data-store.img | gzip -1' | gzip -dc | cp --sparse=always /dev/stdin out/tmp/data-store.img`（约 2 分钟），用完删。
  用户 Data 已 >1.6 GiB，超出打包种子 256 MiB 上限；换种子 = Data 清空。
- [ ] **锁屏动态壁纸抽动 → 推迟到做硬件解码时一起修（11-02 用户决定，所有修改已撤回）**。两条路线都有；只在登录后锁屏出现。
  - 素材：系统卷 `/System/Library/Wallpapers/.default/Golden Gate.mov`，4096x2160 HEVC Main10、BT.709 SDR、240 fps 码流 60 s。guest 无硬件解码，
    VTDecoderXPCService 软解占 130–240% CPU。
  - 根因（已证实）：前端 convertedYCbCrTexture（NativeMetal a9531ab，为修桌面壁纸拒绝而加）把 >1 Mpx 双平面 YCbCr surface 在 CPU 上转成一份
    RGBA 快照，按 (surface ID, seed) 缓存，而且对**所有进程**生效。① WindowServer：CA 一直沿用同一 surface 的纹理，快照不随新帧更新 →
    画面在解码池几块 surface 的旧帧间来回跳；② VTDecoderXPCService 也开 Metal，用这种纹理（格式 543）读参考帧，CPU 在编码时转换、
    GPU 写还没完成 → 参考帧错，录屏里周期性出现"静止区域全灰、只有海浪有纹理"的坏帧，到下一个关键帧恢复。
    旧结论"stderr-log 下一次转换都没发生"是错的：那条日志是 NSLog，守护进程里不进 stderr。
  - 试过（research/debug-2026-11-02/）：
    - 绑定时按 seed + 稀疏亮度和重转、多核并行，并且快照转换只给 WindowServer 用（ycbcr-refresh-server-only.patch）：**抽动消失**。
      但解码进程改走运行时 YCbCr 纹理后，每张 4K 约 100 MiB（RGBA16F 图像 + 暂存拷贝），被 jetsam highwater 1000 MB 杀掉 → 壁纸变黑。
    - 给 IOSurface 加使用计数 + 不给 VTDecoderXPCService Metal 设备（no-metal-vtdecoder.patch）：解码进程照样涨到 1000 MB 被杀
      （疑为使用计数让池不能回收），第一帧花屏；WindowServer 每帧 CPU 重转约 40 ms，CPU 占用很高。
    - 去掉 ca-free-wakeup/ca-triple-buffer：无关。spindump 采样 VTDecoderXPCService 会让 guest 内核 panic 重启（另记）。
  - 硬件解码时要做：解码输出不再经过 CPU 快照（GPU 侧转换或直接采样平面）、解码器内存不超 1000 MB、首帧不花屏。
    诊断工具：research/debug-2026-11-02/wp-procs.sh（--file/--run 进程与 CPU/内存记录）、video-sample.patch（WindowServer 逐帧 surface 校验）、
    data-files.py/data-find.py（从 store 只读取文件，如 Library/Logs/DiagnosticReports/JetsamEvent-*.ips）；录屏用 /tmp/fv 的 imageio-ffmpeg 分析。
- [x] 开机偶发卡死（Waiting on IOMedia，根盘不出现）+ 每次开机根盘晚 20 s——已修（11-02，8/8 次 stop/start 正常，修前约一半卡）：
  - 死锁（stall-dump=75 抓栈）：AppleAPFSContainer::start → external_module_resources 拿 APFS 全局锁（+0xd0）后
    `waitForMatchingService(resourceMatching("IOBSD"))`；而 IOResources 本轮匹配正卡在 com_apple_filesystems_apfs::start 等同一把锁
    （模块 personality = IOResources + IOResourceMatch IOBSD，分数 0）。waitForMatchingService 要求 IOResources 有 kIOServiceMatchedState，
    这个位要等整轮 doServiceMatch（含模块 start）结束才置，所以容器先到就永远等不到。触发者：NativeRamBlock（IOResources+IOBSD，分数 1000）
    在同一轮里先 start 并发布 Data 盘，或 virtio 盘在这一轮里发布。旧注释"APFS 同时挂两个容器会死锁"就是这个，误判。
  - 20 s：NativeVirtioBlock 按 0xa000000..0xa002000 排 rank，但 0xa002000 现在是 DroidVMDataStore，rank 0 永远不发布 → 两块盘各等满 20 s。
  - 修：两个块驱动都等 IOResources 匹配完 IOBSD 再 registerService（条件单调，之后容器的等待必不阻塞）。NativeRamBlock 在 start 里起线程做
    （它自己就在 IOResources 匹配里，不能同步等）——scripts/build-native-ram-block.py；NativeVirtioBlock 在 start 里同步等，rank 改为
    0xa000000..0xa001000、去掉每盘 1.5 s 睡眠——overlay/kext/NativeVirtioBlock.patch（编法：pristine 源打补丁到临时目录，
    `build-native-kext.py NativeVirtioBlock <tmp>/NativeVirtioBlock.cpp overlay/kext/NativeKextGlue.cpp -I sources/UniXNU/drivers/NativeVirtioBlock
    -I out/x12377/storage-abi/include -D U:TARGET_OS_OSX -D TARGET_OS_OSX=1`；旧 .o 带未入库的请求统计日志，新编的没有）。
  - 结果：根盘 27.5 s → 7–16 s，launchd 13–24 s；Data store 读写打开。启动盘已去掉 stall-dump。
- [ ] P3 性能与内存对齐：拖动帧率对比旧路线（kc292 111–121 帧），提交往返、首登内存、blob 分配耗时。止损：低 15% 以上或 blob 拒绝杀进程。
  - 11-02 同日 A/B（两次都全新启动，登录后等 1 分钟，同一窗口拖 30 s；宿主上限都是 2.92/3.51 GHz；指标=DroidVMDisplay 每 10 s 的 shown 差值和
    "at most N frames"，/tmp/p3-collect.sh + /tmp/p3-analyze.py）：新路线 vgpu-3d=1 拖动窗口 80–109 帧/s、峰值 108–115；
    旧路线 84–88 帧/s、峰值 90–101。新路线不慢于旧路线，止损未触发。扫描前等 GPU 平均约 5.3 ms（P2 的等待），是下一步可优化处。
    旧路线这次没到 kc292 的 111–121（窗口或会话状态不同，没对齐），比较只看同日数据。
    未测：首登内存、blob 分配耗时、提交往返（拖动帧率已过线，按需再测）。
- [x] P4 拆旧路线（b0558b7，11-02）：App VM 配置只删了 --droidvm-gpu（没用 register，保留用户的绑核等设置；改前备份 /tmp/vms.before-p4.json）、
  重导 FDT（窗口 data store 0xa002000、net 0xa003000、virtio-gpu 0xa004000），ADT 无 gpu 节点；DroidVMGpu.cpp=上游 4284c6c 式只发布
  （UniXNU-droidvm 补丁 0002，硬件类永不 attach，0x4147 被拒），starter 挂 IOResources；GPU_ARGS=vgpu-3d=1+ca-*；删 diag/submit-times。
  上机：3.6 s 发布+加速器，25 次打开全是 0x4149，桌面出帧。
- [x] NativeAdreno 去代理改动（b502540）：旧 0001/0002/0009（未跟踪）全删，分支 droidvm-macos=805c7e4+6 个 virtio-gpu 3D 提交（无冲突），
  旧分支备份 droidvm-macos-old-p4。上游已改名 drivers/Adreno740 走 iOS 构建，整体跟随不划算，未做。WindowServer 的 type 0x5 打开被拒是 P4 前就有的。
- [ ] 上游 Droid-VM GPU 同步（11-02 核对）。内核侧已齐：NativeAdreno 的 virtgpu 提交 6 个都有（wip/hackintosh、wip/merge-up-1101 其余是 KGSL 路线），
  UniXNU-droidvm 的 DroidVMVirtioGpu*/ABI 自 59ec0a8 未变，NativeMetal droidvm/macOS 的 3 个提交已在 45c8294 里。未合：
  - [x] 1 Turnip（6e2d067）：sources/UniXNU-turnip 工作树（UniXNU 803a014）+ Droid-VM/mesa cecc0e9 + 17 补丁，旧构建留 out/metal/mesa-tu-85fda3b；
    mesa-macos 只剩 0001(tu_cs 日志)+0002(virtgpu 后端按 TU_DARWIN_SERVICE 找 AGXAccelerator，上游写死 IOAcceleratorES)。上机全 0x4149、无崩溃；
    拖动（开机约 13 分钟后）69–72 帧/s、峰值 83–91，P3 旧 turnip 80–109/108–115：疑似回退约 3 成，GPU 等待只多 0.5 ms，提交率 200→155/s（CPU 侧）。
    头号嫌疑 turnip-darwin-bo-cache-budget（空闲 BO 缓存上限 96 MiB，原先不限）；对照 `MACOS_EXEC_ENV=WindowServer:TU_DARWIN_BO_CACHE_MB=0`
    已做进当前手机启动盘，用户决定跳过测试（11-02）。未定论；要回旧 turnip 用 out/metal/mesa-tu-85fda3b。原记录：UniXNU wip/droidvm 的 mesa pin 85fda3b→cecc0e9，新补丁 turnip-darwin-{deadline-queue,queue-priority,bo-cache-budget,va-exhausted-note}、
    mesa-darwin-total-memory-sysctl、turnip-{msaa-resolved-prefers-gmem,render-mode-for-attachment-memory,host-import-images,rotated-copy,gmem-mutable-swap}，
    另有 7 个已有补丁改过（含 turnip-darwin-kmd）。本地 sources/UniXNU（macos-droidvm）停在 c9afde8（10-31）。只改 guest，先做。
  - [x] 2 宿主 virglrenderer（11-02 用户选"两套都保留"）：external/virglrenderer 新分支 wingpu-droidvm-1102（c6738fd4）= wingpu + droidvm/droidvm 899a4e17，
    4 处冲突手解：wingpu 的进程级速率约束（NCTX_PWR_CONSTRAINT，≥130/s）保留但跳过 deadline 队列，上游 deadline 约束/优先级位/uclamp 加入，
    所有 context 仍带 KGSL_CONTEXT_PWR_CONSTRAINT。编法：build_crosvm.sh 的环境 + `m out/soong/.intermediates/external/virglrenderer/libvirglrenderer/android_arm64_armv8-a_shared/libvirglrenderer.so`
    （`m libvirglrenderer` 会编全部变体，libc 依赖缺失失败）。已部署到 App usr/lib（同目录 rename，旧的备份为 libvirglrenderer.so.wingpu-1021）。
    macOS 验证：WindowServer 队列 "constrained"，动画时 "power constraint at the highest level" + vCPU uclamp 1024，停下即撤。**Windows VM 未验证**。原记录：Droid-VM/virglrenderer 10-31~11-01 的 drm2kgsl deadline queue 功耗约束 + vCPU uclamp、VA 32 切片、DRM2KGSL_NONCOHERENT、
    u_thread 亲和；手机 usr/lib/libvirglrenderer.so 不含这些（旧）。turnip 的 deadline 补丁要它才生效；换 App 文件要先问。
  - [ ] 3 NativeMetal/AdrenoMetal：**以 Droid-VM/NativeMetal wip/hackintosh 为主**（11-02 用户定；= Droid-VM/UniXNU wip/droidvm 锁的 drivers/AdrenoMetal，
    当时 f4ce342），比我们的 45c8294 多 109 个（参数编码器、间接绘制、动态库、WebGPU Apple4、内存压力、帧跟踪……），分批评估。
    UniXNU/NativeMetal main（= UniXNU/AdrenoMetal main，当时 171d30b，含 PR #12 fix/gpu-scheduling-and-metal）与它已分叉（各自独有 62/67 个），
    不直接跟：等 Droid-VM 合过去，或只挑调度相关的单看。子模块远端：droidvm=Droid-VM/NativeMetal、origin=UniXNU/NativeMetal、adrenometal=UniXNU/AdrenoMetal。
    - 11-02 已上（b7db62b，部署到手机）：登录界面出来、全 0x4149、无崩溃；这次开机全程慢（launchd 71 s，上次 11.6 s；宿主 kswapd 忙），性能未测。
      sources/UniXNU/drivers/NativeMetal 本地分支 macos-hackintosh = f4ce342 + a9531ab（YCbCr 一次转换，cherry-pick 无冲突）；
      45c8294（bridge 写死 16 MiB）不再带，改用上游板级 0019 的 METAL2VULKAN_BLOCK_MIB，由 overlay 插件设 16（可用 /private/var/ngpu/debug/block-mib 覆盖）。
      风险：上游 8f735a2 在 iPad 上 16 MiB 块 5 次开关 FaceTime 挂 GPU 3 次，故默认回 64；macOS 一直 16 未见挂，若出现 GPU hang 先试 64。
      build-metal-bridge-macos.py：NativeMetal 自带补丁去掉 0020（同上游，依赖未打的 turnip render-mode），加 UniXNU-turnip 的 patches/metal2vulkan 0011–0021。
      插件：WindowServer 设 METAL2VULKAN_QUEUE_PRIORITY=high（上游给 backboardd）；trim/hold-back 在共用 frontend 里自动有。
      上游 iOS 插件其余改动（WebGPU Apple4、family blockers、per-task 优先级转发、pass reporter、log-gpu）未移植。
  - [x] 4 硬件编解码（方案 docs/k27-vt-paravirt-plan.md）：720p H.264/HEVC 编解码全通（11-02）；**锁屏 4K 航拍壁纸已有画面（11-04 晚，用户确认）**。
    - 11-04 晚：msm_vidc 直写 IOSurface（P3）+ Apple vtpv 语义（解码顺序、同步 dfrm 等 Demt、异步在途 ≤3）。已提交：crosvm fe24182b6/b7960bae6、
      virtio-media d509294、macos 2f7c955（0004–0010）/b6cc61b（0011）/3623549（P4 原型）/0855e2a（启动修补）。详情 docs/k27-vt-p3-status.md。
    - [x] P4：WindowServer 原地读 YCbCr 平面，3623549 已生效（11-04 晚核实：无 RGB 转换副本，池 surface 直接导入）。端到端零拷贝。
    - P0 宿主 crosvm：external/crosvm wip/macos-virtio-gpu 已 rebase 到 droidvm/wip/hackintosh（备份分支 backup/wip-macos-virtio-gpu-1102），
      之前的未提交改动拆成 WebRTC / kms msm_prime 两个提交；external/virtio-media 与 external/rust/crates/v4l2r 都换到 Droid-VM 的 wip/hackintosh
      （本地分支 droidvm-hackintosh）；e3ce85e38 让 --pre-alloc 可重复、键合并（App 已传 drm-host-mb，extra_options 再补 media-host-mb）。
      手机 usr/bin/crosvm 已换（旧的 crosvm.bak-1102），Windows VM 还没回归。
    - P1 配置：App 的 vpu_enabled 不生成任何参数（界面写着后端未实现），不用它。`MACOS_MEDIA=1 droidvm-app.py media` 往 extra_options 加
      `--pre-alloc media-host-mb=128 --virtio-media kind=decoder,uid=10641 --virtio-media kind=encoder,uid=… --virtio-mmio-media`（改前 vms.json 在 out/app/vms.json.before-media），
      media 窗口排在 virtio-gpu 之后（0xa005000/0xa006000），ADT /arm-io/virtio-media-0/1 带 media-host-pool；ADT DRAM 少 128 MiB。启动盘要带 MACOS_MEDIA=1。
    - P2 kext：10efcda DroidVMVideo（k27/build-native-video.sh，MACOS_VIDEO=1 k27/try.sh），patches/droidvm-video 0001 不自己做模块加载、0002 IOSurfaceRoot 按类名找
      （macOS 不叫 IOCoreSurfaceRoot，否则 stage 97 每帧查不到 IOSurface）。Apple 自带的 AppleVideoToolboxParavirtualization.kext 只匹配 virtio PCI 0x1a03106b，不会加载。
      guest 内看状态：peek droidvm_media_status（两个设备 "droidvm decoder caps 0x4004000 out: H264 HEVC VP90 AV01 cap: NV12"）、droidvm_vtpv_*、droidvm_vthost_*、droidvm_vthost_trace。
    - P3 探针：research/vt-probe（上游 gfxprobe vtdecode/vtencode + main，stage-gpu-plugin.py --probe 当 launchd 任务，stderr-log=1）。
      720p 30 帧（多次开机的范围）：H.264 编码 141–218 fps、HEVC 编码 142–302 fps、H.264 解码 156 fps、HEVC 解码 172–234 fps；
      解码的是编码器自己的输出（/private/var/tmp/enc.*），亮度与编码图案一致，VT 都报硬件。
      上游探针两个坑（不是移植问题）：内置 64x64 H.264 低于 c2.qti 最小 96x96（宿主日志 "without a SOURCE_CHANGE"）；
      HEVC 判定看前 4 个 NAL 有无类型 32，H.264 P 帧 0x41 按 HEVC 规则就是 32，H.264 文件被当 HEVC（-12714）。research 版已改为只看首个 NAL。
      手机 Data 里现在有这个探针的 launchd 任务（org.droidvm.metal-probe 标签，开机 40 s 后跑一次），启动盘带 stderr-log=1。
    - 4K：壁纸原片前 2 s（4096x2160 HEVC Main10，480 帧）硬解 0 失败，420v 105 fps、x420 92 fps；720p Main10 也通。
      宿主 c2.qti.hevc 对 Main10 直接出 8-bit YUV420Flexible（col 1），后端照 NV12 重排即可，VTHost 不用改 10-bit。
      VTHost 输入队列 128 帧满了就回 -12911（stage 6），VT 收到后会挂住；内核里不能阻塞等待（guest 的发帧和像素缓冲回复走同一线程，
      试过 1 s 背压：每次都等满超时），已撤回。真实播放器自己限在途帧，探针改为在途 ≤16。
    - 壁纸抽动修复：NativeMetal 工作树已打 research/debug-2026-11-02/ycbcr-refresh-server-only.patch（未提交），插件已编，**未上机验证**。
    - **11-02 事故：用户 Data 被清空**。build-metal-plugin.sh 重新生成了种子；cycle.sh 没 pipefail，--store 被拒后仍写入了旧 store-patch，
      启动盘换成新种子，PersistOverlay 种子不符→覆盖层重置，回写的 20 万页覆盖了旧块，旧 Data 基本不可恢复。事故后存储备份在 out/rescue/。
      手机现在是新种子 eeda768f + 新覆盖层（generation 4）。
    - 用户选择在全新 Data 上继续。事故后的种子缺 --setup-done/--user：黑屏=Language Chooser 等被禁用的 bluetoothd（不是插件补丁，撤补丁对照也黑）。
      已用 --store 补写 `--setup-done --disable-job audiomxd/apsd/AppSSODaemon/fskitd --user droid:droid`（种子不变），登录界面恢复（55 fps）。
      cycle.sh 现在：pipefail、先删旧 store-patch、种子与手机存储头不一致就不开机；STAGE_EXTRA 传 stage 参数；collect.sh 从开机起累积 msgbuf；counters.sh 读计数。
    - macOS VT 会发 `dsts` = ParavirtualizedVideoDecoder_StartTileSession（HEIC 网格等分块解码），VTHost 不认识、回 -12900，VT 作废后走软件；无害。
      上游 706338e（11-02）：开机默认发布、dsta 对解码器做不了的尺寸/非 4:2:0 直接拒绝走软件（64x64 就能解了），未合入本地。
    - 11-03 用户锁屏：壁纸确实走了硬解（4K HEVC c2.qti），但同时开了两个 4K 会话，128 MiB 池耗尽。
      7800f43：缓冲改为 guest 内核内存 + USERPTR（0003，droidvm_media_ioctl_sg 把页表放在负载后的独立描述符），池默认 8 MiB；
      探针 4K 480 帧 0 失败，但 420v 105→88 fps、x420 92→74 fps（疑为宿主每次 QBUF 重新映射 13 MB 页表，待查）。
    - 宿主卡顿（11-03 实测，research 外的 /data/local/tmp/hostmon.sh 采样）：开机 70 s 内可用内存 6.7→2.7 GB，kswapd 3.5 min 用 36 s CPU，
      3 min 杀 19 个后台；guest 5 GB 以 2 MB shmem 大页常驻。是 VM 内存规模对宿主的压力，与视频改动无关；crosvm RSS 10.4 GB 是双重映射重复计数。
    - USERPTR 4K 变慢已查清（11-03）：宿主每次 QBUF 新建 arena 映射，每帧缺页约 3200 次。crosvm b4f3cf04d 让单段缓冲走 GuestMemory 现有映射。
      同一次开机交错 A/B（research/vt-ab，droidvm-vt-ab=1 每隔一个会话走 MMAP）：USERPTR 均 106.4、MMAP 均 106.1 fps，等速。
      跨开机比较噪声达 20%，A/B 必须同开机交错。手机已回正式 KC、池 8 MiB。
    - 11-03 旧 Data（1 GiB）写满：tzinit ENOSPC 后 MACH Reboot 循环。经用户同意换新种子 --data-size-mib 3072（旧种子/存储备份在 out/tmp）。
      新 Data 里还留着 A/B 探针任务（每次开机 40 s 后解 8 轮 4K），正式使用前用 --store 去掉。
    - **锁屏壁纸仍抽（11-03 查清）**：锁屏时 VT 建的硬件会话全部在 stage 11 失败（6.6 MB 码流缓冲分配不到，累计 10169 次），帧全走软件解码。
      根因是 guest 物理内存被占光：wired 2.9 GB / max_mem 5.2 GB，free 45 MB。wired 里 DroidVMDisplay（GPU blob）1937 MiB，其中 WindowServer 1468 MiB：
      19×40 MiB（4K 32 位纹理，即插件 YCbCr→RGBA 的 CPU 转换副本，每个视频池 surface 一份）+ 20×20 MiB（待查）。
      看法：peek droidvm_virtgpu_client_memory（按进程），gClients 在 0xfffffff00acab290（由 _droidvm_virtgpu_close 的 adrp 反解）；脚本 /tmp/k27-gpumem.py、/tmp/k27-gpures2.py。
    - （11-04 晚：P3 已通、壁纸有画面；P4 原型已提交待核实，见上方「4 硬件编解码」。）
    - **方案：着色器直接读 YCbCr 平面（用户 11-03 选定）**。metal2vulkan 已有 PlanesInPlace（集成 GPU、格式 500/505、槽只 sample/读尺寸时，
      着色器用 uniform texel buffer 直接读 IOSurface 平面并按 Metal 算法转换）。但运行时建纹理时总是先分配 RGBA16F 转换图 + 平面暂存（4K 约 100 MB），
      WindowServer 每帧新建纹理，所以插件当初拒了 >1 Mpx 改走 CPU 转换。步骤见 docs/k27-vt-paravirt-plan.md「壁纸纹理」：
      1 metal2vulkan 转换图按需分配；2 插件对 500/505 撤拒绝与 CPU 转换；3 m2vsim 验证 + 上机看 WorkCounts 与内存。
    - 下一步（其余）：去掉 Data 里的 A/B 探针。（706338e 已合：VT_REF 换到 706338e、补丁重生成，11-04 晚）
    - GPU 用户态 11-04 晚合入 UniXNU wip/droidvm ef4486d（metal2vulkan 0022 释放闲置命令池、Turnip cs 失败流修复），11-04 晚已打 Data 补丁上机：
      登录/锁屏正常，航拍一段 31 s 播完（in 942/out 900/错误 0），WindowServer 仍原地读 YCbCr。开机 60 s SecurityAgent 有一次 Metal 设备 OutOfMemory，之后正常。NativeMetal 3f8d44a 与 UniXNU-droidvm e29d087（IOSurface 锁等 GPU）不合。
    - 11-04：Safari（WebKit）的 Dbuf surface 是别的进程建的，按 ID 查找 kIOReturnNotPermitted（stage 41/42，in 9 out 0）。
      patches/droidvm-video/0012 改走进程自己 IOSurface 客户端建端口（复用 efrm 路径），suite 16 项过。11-04 B 站已正常播放：23 会话 in 2131/out 2111/丢 20，
      近期 msgbuf 无 stage 41/42。遗留：stage 31（Dbuf 回复无 surface，err 0）累计 63 次，来源未分（Safari 还是锁屏），不影响播放。
  - [x] 5 音频（virtio-snd，11-04 用户定开始做；11-05 晚有声不卡、音画同步，见 docs/k27-audio.md）。**11-04 B 站在 Safari 已能正常播放（静音设备，用户确认）**。**B 站/Safari 视频一直加载的根因**：guest 无音频输出，`CMAudioDeviceClockCreate ... Unknown route`
    err -101 → `[AVSampleBufferAudioRenderer init] returned nil`（-11800）→ WebKit DecodeError（日志：Data 的 log-stream 谓词已加 WebKit Media/MediaSource）。
    上游只给 iPadOS 27 做了：UniXNU-droidvm wip/hackintosh 的 package/DroidVMAudio.cpp（IOAudio2Device 扬声器/麦克风，1f57203/0bce497）
    + package/DroidVMVirtioSnd.c（virtio-mmio 上的 virtio-snd）；crosvm `--virtio-mmio-snd`（cc88041e5）我们分支已有。
    macOS 27（分析在 out/tmp/audio-re/）：HAL 在 coreaudiod，有 HALS_IOA2Manager；无 VirtualAudio/Aspen（UID 不用特定名）；
    kc-k27.bin 已带 IOAudio2Family（IOAVFamily 依赖）；Apple 自带 AppleVirtIOSound 只走 PCI，用不上。
    - [x] a k27/build-native-audio.sh（AUDIO_REF=e29d087）+ patches/droidvm-audio/0001（native kext 不自己做模块加载）+ overlay/kext/DroidVMAudio{.json,/DroidVMAudioStarter.cpp}，
      `MACOS_AUDIO=1 k27/try.sh`。无 virtio-snd 时设备照样发布（静音）。开机 4 s `DroidVMAudio: published Speaker=1 Mic=1`，coreaudiod 打开 2 个客户端、映射 4 块。
      计数器在 kc-k27.natives.json 的 _droidvm_audio_*（rig-dmesg 的 nm 里没有 native kext 符号，按 va: 读）。
    - [x] b（11-05 已上机）droidvm-app.py `MACOS_SND=1`（`--virtio-snd backend=aaudio,capture=true,num_output_devices=1,num_input_devices=1,uid=App`
      + `--virtio-mmio-snd`，同上游 iPadOS 模板，放在 GPU 之后、media 之前）与 `snd` 命令（只换声卡、保留其余配置、重导 FDT）；
      run-macos-vm.py make_adt(snd=) 给上游 ADT 工具补 --snd-mmio 和 /arm-io/virtio-snd 节点。手机 crosvm 已含 virtio-mmio-snd。
      上机：`out/tmp/snd-deploy.sh`（stop → 备份 vms.json 到 /data/local/tmp/vms.json.before-snd → snd 重导 FDT → 带 MACOS_SND=1 重建启动盘 → start），
      开机后 `out/tmp/snd-status.sh`（droidvm_snd_status 应为 "up: output stream ..."，再看 audio_played 是否随播放增长）。
      离线已验：snd=False 时 ADT 与线上逐字节相同（只差 /chosen/random-seed）；snd=True 要等 FDT 有声卡窗口才能验。
    - 内核截断已导出 patches/xnu-12377/0041（由工作树 diff 生成，k27 分支未提交）。
    - [x] c 恢复 audiomxd：stage-gpu-plugin.py 新增 `--enable-job`，已对 com.apple.audiomxd 打 Data 补丁。没它 AVSampleBufferAudioRenderer 报 -16155（FigXPC 连不上服务）。
      日志窗口内未见 audiomxd 报错，CPU 未测。
    - [x] 内核：coreaudiod 的 IO 线程申请实时计算量 1200000 tick（24 MHz 的 50 ms），本板 19.2 MHz 上限 960000 → thread_policy_set 拒绝、
      HAL 时钟不走、视频停在 1 s。out/k27/xnu osfmk/kern/thread_policy.c 改为超限截到上限（**未提交，补丁未导出为 0041**）。
    - 11-05 b 已上机：`droidvm_snd_status` = "up: output stream 0, input stream -1 x1"，**用户确认有声**。麦克风：宿主 PCM_PREPARE stream 1 失败
      （AAudio Failed to open stream），推测 App 无录音权限，未验证。
    - [x] d（旧，被下面的根因取代）有声但卡：宿主 12 次 "playback stream is running with nothing queued"（空 25–66 ms），guest 准时（每 5 ms 正好送一个周期，宿主零余量）。
      patches/droidvm-audio/0002：开播先垫 8 周期（40 ms）静音、output latency 加上这 40 ms。已上机（现行 KC 含 0001–0003）。
    - **11-05 视频又卡加载的根因：手机重启后 udmabuf 模块 msm_prime 回到 N**。msm_vidc 导入 udmabuf 时 mem_buf 认不出 → 当安全缓冲
      → "secure buffer mapping to non-secure region 2 not allowed"，QBUF(CAPTURE) EINVAL，所有解码会话（含锁屏 4K）一开就失败、kext 无限重启会话。
      手动 `echo Y > /sys/module/udmabuf_gki_6.6/parameters/msm_prime` 后恢复（重启手机会丢）。长期：crosvm vidc 后端复用 gpu_display_kms.rs 的 MsmPrime 自己开。
    - [x] d 有声验证（b 之后）：**11-05 晚已修好，用户确认"正常了"**（不卡、音画同步）。详情、代码状态、待办全在 docs/k27-audio.md。
      - 主因：macOS 27 CoreAudio 写死 24 MHz（AudioGetHostClockFrequency/125:3），本板计数器 19.2 MHz → HAL 每 80 ms 才写 64 ms 的量，
        每秒一次 FADC discontinuity → 隔秒卡、声音越来越落后。移植上游 5edbbfc：内核 fd327f8 = patches/xnu-12377/0042，
        启动参数 `droidvm-timebase-hz=24000000` 已进 droidvm-app.py REQUIRED_ARGS（11-06 起默认）。
      - 次因：crosvm snd helper 的 exe/AudioTrack 线程 SCHED_OTHER 被 vCPU 抢占 → 临时 /data/local/tmp/sndrt.sh 设 FIFO 2（**手机重启后要重新拉起**），正式修复待做。
      - crosvm（已提交 d7fdd3079、已部署）：AAudio 低延迟+数据回调（168→31 ms）、8 周期环、断粮后丢已排队积压；guest 0003 报的延迟加 1536 帧。
      - 临时诊断（0099、crosvm DIAG/10 秒统计、vcpusched.sh）11-06 已撤。
    - [ ] 宿主 snd helper 实时调度正式修复；验证 0041 在 24 MHz 时基下是否还需要；麦克风权限。（音频改动 11-06 已提交：macos bcf8237、crosvm d7fdd3079）
    - [ ] **（11-06 用户决定先跳过）登录前 CPU 高 = audiomxd 死循环**，Apple 自己的 bug，详见 docs/k27-audio.md「登录前 audiomxd 死循环」。
      无前台用户时 BTAudioRoutingRequest 失败→当成服务端死亡→重连，无退避；configd 跟着高（每轮查控制台用户）；登录后自停。
      已去掉 Data 的 log-stream 任务（它转发这些错误，放大约 1.4 核）：登录前总忙 2.4→约 1 核。剩余可选修法：自动登录（Apple 社区帖唯一绕过）/
      注入 dylib 让 +[BTAudioRoutingRequest isSupported] 返回假 / 登录后才 enable audiomxd。
    - 坑：k27/try.sh 先写 nm 再写 KC，rig-dmesg 见 KC 更新就用 KC 重生 nm（无符号）→ 读 msgbuf 失败；重生 nm 后 touch。WebKit Network 日志会把 1 MiB msgbuf 刷成 30 s，查完要从谓词里去掉。
- 当前手机启动盘（11-06）：kc-k27.bin 含内核 0042 与 DroidVMAudio 0001–0003，带 stderr-log=1、droidvm-vt-paravirt=1、droidvm-vt-direct=1、msgbuf=1048576，`droidvm-timebase-hz=24000000` 已是 REQUIRED_ARGS 默认（vgpu-3d=1 是 GPU_ARGS 默认）；手机 crosvm 为 11-06 音频版（备份 crosvm.bak-1105）。启动盘重建命令见记忆 macos-k27-repo-layout。

## installer / softwareupdate（2026-11-09）

- 已修（guest 内，存在 Data 覆盖层里）：Apple 签名的包 `installer` 报 Code=100 "Authorization is required"，其实不是授权问题。PackageKit 给 Apple 软件准备安装沙盒时会解析符号链接，落到 `/Library/Apple/System/Library/InstallerSandboxes`；而种子把 `Library/Apple` 链到只读的 SystemOS（`/System/Library/DroidVMData/Library/Apple`），所以 mkdir 返回 EROFS（fs_usage 抓到）。处理：在 guest 里把这个链接换成真实目录，用 ditto 拷 121 MB。之后 CLTools_macOS_SDK.pkg 安装成功。
  - 待做：`scripts/make-macos-data-seed.sh` 的 READONLY 里还有 `Library/Apple`。下次真要重做种子时得把它拷成真实目录（受种子 256 MiB 上限影响）。不要为此重做种子。
- 已修（2026-11-09，内核未提交）：softwareupdate 列不出 CLT（xcode-select 报 "not currently available"），XProtect 一类 dist 的路径检查也都失败。
  - 根因：dist 脚本访问路径要过 Install.framework 的 `IFJS_IsPathSafe`。它逐级 lstat，`st_dev` 必须等于根卷，或者等于 `+[IASFilesystemUtils dataVolumePathGivenSystemPath:@"/"]` 给出的 Data 卷。
  - 后者的做法：statfs("/") 取设备名，读 `APFSVolumeRole`（要 System），再读 IOMedia 上的 `VolGroupUUID`，经 `IORegistryEntryGetParentEntry` 在同一个容器里找同组、角色为 Data 的卷，最后用 getmntinfo 求它的挂载点。
  - 旧布局下根是 SystemOS（disk3/disk2，无角色），Data 在另一个容器，所以返回 nil，Data 卷上的路径（如 `/tmp/.com.apple.dt.CommandLineTools.installondemand.in-progress`）全被拒。
  - 布局改动（guest 内，写在 Data 覆盖层里；改前在手机上备份了 `data-store.img.before-volgroup`）：
    - `diskutil apfs changeVolumeRole disk5s1 D`
    - `diskutil apfs addVolume disk5 APFS DroidVMSystem -role S -groupWith disk5s1 -nomount`，得到 disk5s2，UUID 4646A7E0-…；卷组 UUID 等于 Data 卷的 UUID 8748FE31-…。
  - 内核改动（out/k27/xnu，未提交）：挂完 Data 后，`native_owner_root_device_prepare` 用 IOKit 找 Data 卷所在卷组里 RoleValue=1 的卷（IOKitBSDInit.cpp `native_volume_group_system_device`）。statfs/getfsstat/vfs sysctl/`ATTR_VOL_MOUNTEDDEVICE` 对代替根的那个 union 挂载报这个设备名（vfs_subr.c `virt_union_mntfromname`）。根的文件、设备号、卷 UUID 都不变；没有这个卷就照旧报 SystemOS；可用 `k27-root-system-volume=0` 关闭。
  - 没有把空 System 卷真 union 到 `/` 上：getattrlistbulk 不穿透 union，`/` 在 Finder 里会变成空目录。
  - 验证（kc 48 kexts）：`mount`/`diskutil info /` 显示 `/dev/disk5s2` DroidVMSystem 及其卷组；`dataVolumePathGivenSystemPath:@"/"` 返回 `/System/Volumes/Data`；有触发文件时 `softwareupdate --list` 列出 "Command Line Tools for Xcode 27.2"；`/Volumes/DroidVMSystem -> /`，和真机一样。
  - 余下：`softwareupdate -i` 报 "Not enough free disk space: a total of 9.54 GB is required"，而 Data 只剩 2.2 GB（要扩 Data，用 grow-data-store.py）。如果 Data 种子或覆盖层被重置，卷组会丢失，要在 guest 里重跑上面两条 diskutil（内核会自动回退）。
- 11-09 后续：根设备名替换已撤（存档 out/k27/root-rename-20261109.diff），改为真机式单卷布局：Data 扩到 48 GiB，系统内容拷进 DroidVMSystem，根直接从它启动（`MACOS_ROOT_UUID=4646A7E0-5598-41A2-B158-E1AF6D3CF7FB`）。见 docs/k27-real-disk-layout-plan.md。已起到登录界面，`df /` 是容器空间；11-10 softwareupdate 已能列出 CLT，空间够。
- 11-10 P5：单卷布局改由 launchd/APFS 原生挂载（Preboot/VM/Update/xART/Hardware/Data 各自成卷，firmlink 原生拼接），`/sbin/mount` shim 已去掉，单卷不再传 `union-hide-lower=1`。工具 k27/disk-tools/setfirmlink.c、k27/disk-tools/mkxart.c（都要进信任缓存）。细节见 docs/k27-real-disk-layout-plan.md 文末。同日删除了内核里 union 布局那一串（union-hide-lower、内核挂 Data/firmlink、SystemOS union 挂载），k27 内核只支持单卷布局，droidvm-app 默认 MACOS_ROOT_UUID=DroidVMSystem。
- 预期不可用：系统更新（scan 8401，机型 droidvm、根卷未封印）。
- 工具：在 guest 里用 `echo droid | sudo -S lldb` 调试自己编的小程序，可以在运行时把共享缓存的桩解析成符号（静态 image lookup 解析不了桩岛）；lldb Python 脚本思路是读 adrp/add 得到 GOT，再 ResolveLoadAddress。
