# xnu-12377 移植记录（2026-10-23）

目标：用开源 xnu-12377.121.6（= macOS 26.5 的 vma2 内核）替换 xnu-10063，配 macOS 原生 kext（26.5 vma2 内核缓存）。试验根目录 `out/x12377/`。

## 当前结论（先看这里）
- 已能在手机上（经 App 的持久化 VM）启动 12377 内核（arm64 和 arm64e 两种都行，后续以 arm64e 为准）：DarwinBoot 加载、`arm_init`、VM/zalloc/kalloc、`kernel_bootstrap_thread`、MACF 初始化都走通，停在 `trust_cache_init`：`panic: image4 interface not available @kern_trustcache.c:584`——这一步要靠 AppleImage4 kext，即下一步需要预链接 kext（26.5 原生 kext + 重定位器，或先借 10063 的 iPad kext 做不到，ABI 不匹配）。
- 基线树改为 `out/x12377/xnu-m`：UniXNU 社区 fork 的 `none24smu/UniXNU` 分支 `ios26`（克隆在 `out/refer-unixnu-ios26`）里的 21 个 xnu-12377 补丁（`patches/xnu-12377/`，对干净的 12377.121.6 全部可直接 apply）+ 我们自己的补丁栈三方合并（7 个冲突文件已解决）+ macOS 目标修复。旧的手工移植树 `out/x12377/xnu-work` 仅留作对照。
- 真实头文件：KDK 26.5.2（dortania/KdkSupportPkg，约 1.2 GB 镜像，只提取头文件，`out/x12377/kdk`，用 fork 的 `scripts/kdk-headers.py`）里的 `CoreEntitlements/V2`、`TrustCache`、`CodeSignature`、`TrustedExecutionMonitor`，所以不再需要手写桩头，`CEKernelAPI_t` 布局是 Apple 的真实布局。KDK 是 25F84（xnu-12377.122.8），kext 是 26.5（12377.121.6），启动原生 AMFI 前要核对 `KERN_AMFI_INTERFACE_VERSION`/`TRUST_CACHE_INTERFACE_VERSION`。
- 内核对 26.5 kext 的符号依赖：`scripts/kext-kernel-imports.py out/kc/kc265.bin KERNEL` 统计 3483 个被 kext 直接 `bl`/数据指针绑定的内核符号，macOS 目标内核只缺 23 个（OSMalloc 系、`_MALLOC/_FREE`、`csr_check`、hfs 配额 `dq*`/`qf_*`），都不在启动关键路径上。iPhoneOS MASTER + `-DXNU_TARGET_OS_OSX` 够用，不必换 MASTER.arm64.MacOSX。
- 虚表对比（`scripts/vtable-abi-diff.py KERNEL KC`）：macOS 目标 `IOService` 275/275、`IORegistryEntry` 134/134、`IOUserClient` 309/309、`IOWorkLoop` 70/70、`IOInterruptEventSource` 77/77 槽位一致；iOS 目标 `IOService` 只有 171 槽。

## arm64e 内核（2026-10-23，方案 a，已完成到与 arm64 同一里程碑）
- 26.5 kext 是 arm64e，所以内核也按 arm64e 编并真签名：`XNU_ARCH=arm64e`（`out/x12377/build-all.sh` 一键：内核对象 → libfirehose → 源码 corecrypto → ArmDTPlatform/ArmCpu → 链接 → POST 封印，产物 `kernel12377e-osx.macho`，上机冒烟 `MACOS_KERNEL=… scripts/xnu12377-smoke.sh`）。同样走到 `trust_cache_init`，panic `image4 interface not available`。
- 编译：`-target arm64e-apple-ios26.0`（`-arch arm64e` 只配 arm64 目标时不带 ptrauth 特性）；上游 LLVM 21 缺口：定义 `__PTRAUTH_INTRINSICS__=1`（Apple clang 才有，xnu 的 ptrauth.h 靠它）、加 `-fptrauth-function-pointer-type-discrimination`（上游默认关，Apple 开）、`OS_PTRAUTH_SIGNED_PTR_AUTH_NULL` 去掉第 4 个选项参数（上游不认，只影响 xnu 私有字段）。实测核对：`sysctl_handle_int` 等函数指针的类型判别值与 26.5 内核缓存一致（3630，均为 IA、非地址判别），ABI 兼容。
- 链接：`-Wl,-no_fixup_chains -Wl,-threaded_starts_section`（ld64-711 对 arm64e -static 默认出 chained fixups 而 xnu 的 `arm_slide_rebase_and_sign_image` 只认 `__TEXT,__thread_starts`；缺它时内核停在 `static_if_init` 的无故障死循环）。所有 `.a` 必须同为 arm64e（否则 ld64 静默忽略整个 archive，表现为符号未定义）：`fakeroot/usr/local/lib/kernel-{arm64,arm64e}/libfirehose_kernel.a`；firehose 不能带 `-mkernel`（会生成 PAK 子类型，与内核对象的 PAC 子类型不匹配）。
- 其他：DarwinBoot 只收 cpusubtype 0，已加补丁 `patches/darwinboot-accept-arm64e.patch`（`build-darwinboot.py` 一起应用，产物 `artifacts/boot-inputs/DarwinBoot.efi` 已重编，兼容 arm64）；`seal-source-crypto-kernel.py` 加 `--arm64e-chained`（static-if 表里的指针是 threaded 格式：认证指针低 32 位 = 相对镜像基址偏移，普通指针 43 位符号扩展）。`darwin-tool.py` 支持 `GUNYAH_TOOL_TRACE=文件` 记录链接命令；`port_exc`（locore.s 里 SP1 同步异常溢出失败时记录 ESR/ELR/FAR/SP）和 `port_crumb` 是启动面包屑（无串口时用 `rig-dmesg.py --peek`）。
- BCM2837.h 为 arm64e 定义 `CPU_HAS_APPLE_PAC`/`HAS_APPLE_PAC`。PAC 密钥没有显式编程（起始值未定义但固定，签名与验证一致）；进程的 JOP 密钥（`REPROGRAM_JOP_KEYS`）上用户态前要核对，现在还没走到。

## 构建与上机
- `out/x12377/build-full.sh`：macOS 目标 + 源码 corecrypto + ArmDTPlatform + ArmCpu，产物 `out/x12377/kernel12377m-osx.macho`（22 MB，带符号，已封印 POST HMAC）。前置：`out/x12377/un`（fork 脚本目录，drivers 链到 `out/linux/UniXNU/drivers`，`.cache`/`build` 链到 xnu-m/fakeroot/m-obj）里先跑 `build-corecrypto-14.py --xnu-12377`（含 `--namespace`）和 `build-platform-12377.py ArmDTPlatform|ArmCpu`（环境 `CCC_OVERRIDE_OPTIONS='+-Wno-error=missing-designated-field-initializers'`）。
- `out/x12377/build-kernel.sh`：参数化的 make 入口（`XNU_TREE`、`XNU_OBJ`、`KDK`、`XNU_DEPLOYMENT_TARGET_FLAGS`、`XNU_NATIVE_ARCH_TIMER` 等 fork 的特性开关，默认值取 droidvm_defconfig；这些按对象的开关 make 不追踪，所以每次先删对应 .o）。部署目标 26.0（`env.sh` 的 `GUNYAH_APPLE_TARGET=arm64-apple-ios26.0`），否则驱动脚本的 "iOS 26 deployment" 校验失败。
- `scripts/xnu12377-smoke.sh [秒] [内核参数...]`：用 `MACOS_KERNEL`（默认上面的产物）重建启动盘、重启 VM、读内核 msgbuf（`rig-dmesg.py`）和面包屑（`PEEKS`）。`run-macos-vm.py`/`rig-dmesg.py` 现在认 `MACOS_KERNEL`；rig-dmesg 取串口日志里最后一次 DarwinBoot 交接行（日志会累积多次启动）。12377 向引导程序要 256 字节随机种子（10063 是 64），`make_adt` 在设了 `MACOS_KERNEL` 时用改过的 ADT 工具副本（`out/adt/`，`sources/` 不动）。
- 必需的内核参数：`vm_compression_limit=1572864`（macOS 目标的压缩池默认 16×内存 ≈ 48 GB，超过 4 KiB 布局的内核 VA）；不要给 `serial-device-name`（ADT 里没有 UART 节点，指定了会在 serial_init 里静默 panic）。调试：`startup_debug=1` 逐个打印启动函数；panic 文本在 guest PA 0x13fb80000（`rig-dmesg.py --peek 0x13fb80000 LOG 8192`）。
- 已定位修复的坑（按出现顺序）：磁盘写满 → `assym.s` 空文件；`start.s` 的 Pi 3 定时器写 0x40000040 → 必须 `XNU_NATIVE_ARCH_TIMER=1`；随机种子 64→256 字节；`kmem_range_init` 的 compressor 声明过大；`kalloc_init` 在 kt_count=0 时死循环（见下）。

## 已知的功能性折中
- 内核里没有 Apple 专有的类型签名内建函数：`__builtin_xnu_type_signature`→空串、`__builtin_xnu_type_summary`→纯数据、`__builtin_xnu_types_compatible`→恒真（`osfmk/kern/kalloc.h`、`iokit/IOKit/IOLib.h`）。所有 kalloc_type 视图都走数据堆，`kalloc_type_view_init_fixed/var` 在视图数为 0 时提前返回（`osfmk/kern/kalloc.c`）；失去按类型隔离分配，不影响运行。
- `VM_MAX_SWAP_FILE_NUM` 100→5（macOS 目标），三个 swap 常量、`compressor_is_thrashing`、`MAP_32BIT`、`pid_hibernate` 桩是 macOS 目标独有的开源树缺口。
- 面包屑/诊断代码留在 xnu-m 里（`port_crumb` 全局 + `arm_init.c`/`arm_vm_init.c`/`prng_random.c` 的赋值，`startup.c` 的无条件 `kernel_bootstrap_log`，`vm_kern.c`/`pmap.c`/`kalloc.c` 的 `kprintf("port: ...")`），固化补丁时要单独成一个诊断补丁。
- 补丁手工合并/修正（相对干净 12377）：`kern_mib.c` 去掉自带 `hw.mempath`（12377 已有）、`zalloc.c` 还原（10063 的 PGZ 补丁不适用）、`vfs_subr.c` 的 `virt_union_top` 放到文件尾、`sleh.c`、`vm_user.c`、`vm_shared_region_pager.c`、`exception.c`；`ml_device_is_prod_fused` 由 fork 的 `machine_routines_nos.c` 提供。

## 其余（早期试验，保留备查）
## 目录与命令
- `out/x12377/xnu-work`：xnu-12377.121.6 的工作树，已提交到它自己的本地仓库（`a272bb2` 补回 BCM2837 层，`2c5adf9` 打补丁栈 + 构建修复）；`out/x12377/ported-stack.diff` 是相对 `a272bb2` 的差异快照。
- 补回 Pi 3 板级层：`scripts/xnu12377-readd-bcm2837.py XNU_12377_TREE XNU_10063_REFERENCE_TREE`（12377 删掉了 BCM2837，本项目 4 KiB 机器层建在它上面）。
- 构建：`out/x12377/build-kernel.sh`（`XNU_OBJ=ios|osx`、`XNU_DEPLOYMENT_TARGET_FLAGS`）。macOS 目标：`XNU_OBJ=osx XNU_DEPLOYMENT_TARGET_FLAGS="-miphoneos-version-min=17.0 -DXNU_TARGET_OS_OSX" out/x12377/build-kernel.sh`。
- 产物：`out/x12377/kernel12377.macho`（iOS 目标）、`kernel12377-osx.macho`（macOS 目标），均约 17 MB，链接成功、未上机。
- 工具链：`toolchains/linux/bin26/linux-toolchain.json`（SDK iPhoneOS26.5，`native_compile=true` 即宿主 LLVM 21，`drop_args`、`extra_args` 在 `compat/xnu-linux/linux/darwin-tool.py` 里处理）。

## 为什么用原生 LLVM 21，不是 Apple clang
Darling 里的 Apple clang 15 对 xnu-12377 不够：asm goto 跨初始化的检查（`static_if`）、`__builtin_ctzg/clzg` 都不认。原生 LLVM 21 没有 Apple 专有的 `__builtin_xnu_type_signature/summary/types_compatible`，在 `osfmk/kern/kalloc.h`、`iokit/IOKit/IOLib.h` 里换成固定值（签名为空、摘要=纯数据、兼容检查恒真）：kalloc_type 按类型隔离分配失效，不影响运行。Xcode 26 的 clang 需要 Apple ID 下载，未取得。参考：`out/refer-xnu-linux-toolchain`（Allenwdk/xnu-linux-toolchain），其 kalloc/crypto 补丁与我们一致，还有链接垫片可参考。

## 在 xnu-work 里做过的移植修改（尚未固化为 overlay 补丁）
- 配置/构建：`config/MASTER.arm64.iPhoneOS` 加 `nos_arm_asm nos_arm_pmap`（否则 start.s/locore.s/cswitch.s 等不编）；`makedefs/MakeInc.def` 的 BCM2837 加 `-march=armv8.5a+crypto`，板级库 `lib$(MACHINE).os.$(CONFIG).a` 改为存在才 force_load；`san/memory/kasan-denylist` 的 `[*]` 改 `[.*]`。
- 头文件：`arm64_isa_compatibility.h`（向量写法）、`apple_arm64_cpu.h` 补 include regs、`board_config.h`（BCM2837 补 `CPMU_PMC_COUNT`，MAX_CPUS=8）、`BCM2837.h` 的串口宏改为 `PL011_UART`（12377 按设备树节点 + `serial-device` 选串口）、`pmap.h` 重名成员、macOS 分支的 `vm_compressor_backing_store.c`/`vm_compressor.c`/`bsd/sys/mman.h`。
- 桩/外部输入：`EXTERNAL_HEADERS/CoreEntitlements/V2/{API,Kernel}.h`（编译用桩，`CEKernelAPI_t` 布局不是真的）、`EXTERNAL_HEADERS/TrustCache`（拷自 10063 参考树）、`osfmk/kern/link_compat.c`（`__cxa_atexit`、`ml_device_is_prod_fused`、`pmap_pending_preemption`、macOS 目标的 `pid_hibernate`）、`out/x12377/fakeroot` 里的 `libfirehose_kernel.a`（用 `refer-libdispatch` 的 `firehose_buffer.c` 编）和 `os/*.h`。
- 补丁手工合并/修正：`kern_mib.c` 去掉自带 `hw.mempath`（12377 已有）、`zalloc.c` 还原为原版（10063 的 PGZ 补丁在 12377 不适用）、`vfs_subr.c` 的 `virt_union_top` 挪到文件尾、`sleh.c`、`vm_user.c`、`vm_shared_region_pager.c`、`exception.c`。

## 验证结果
- 补丁落点审计：44 个带函数名的补丁块只有 `vfs_subr.c` 一处放错（已修）。
- 虚表对比（`scripts/vtable-abi-diff.py KERNEL KC`，与 `out/kc/kc265.bin` 的内核条目逐槽比）：macOS 目标 `IOService` 275/275、`IORegistryEntry` 134/134、`IOUserClient` 309/309、`IOWorkLoop` 70/70、`IOInterruptEventSource` 77/77 槽位一致；iOS 目标 `IOService` 只有 171 槽。原生 kext 必须配 macOS 目标内核。`IOMemoryDescriptor`/`IOBufferMemoryDescriptor`/`IOMemoryMap`/`OSMetaClassBase` 有 3~5 处名字不同，疑似按地址反查符号时相同函数合并造成，待核实。
- 内核里没有板级驱动：线上 10063 内核的 ArmCpu、ArmDTPlatform、ArmVirtPlatform、NativeUfs 等（`out/linux/UniXNU/drivers`）由 UniXNU 的 `build-arm-driver.py`/`kernel.py` 在 `make` 之后链入；12377 要整体迁到新头文件。

## 磁盘
宿主 `/` 曾写满导致 `assym.s` 生成成 0 字节、一批 `static_if` 假错误；构建前先看 `df`。构建日志只保留 `error:` 行（原始日志几十 MB 的警告）。


## fileset KC 方案（2026-10-23）
- UniXNU 的 NativePrelink 只做普通 arm64 旧式 prelink 的数据指针重绑（`instruction_relocation_complete: False`），12377/zeta 板因此不预链接；26.5 是 arm64e fileset，没有现成做法，需要自己写。
- xnu 路径：`arm_init.c` 在内核属于 fileset 时 `kc_mh = VM_KERNEL_LINK_ADDRESS + slide`，调用 `kernel_collection_slide`（只认 KC 头里的 chained fixups）、`kernel_collection_adjust_mh_addrs`（所以引导器不能滑动 load command）；`arm_vm_init.c` 要求内核 `__LAST` 落在 KC `__TEXT_EXEC` 内、`__LASTDATA_CONST` 在 KC `__DATA_CONST` 内、`__PRELINK_DATA` 在 KC `__DATA` 内，内核 `__TEXT_EXEC` 必须在所有 kext 的 `__TEXT_EXEC` 之后（±128 MB 内）。
- 决定：kc265 里保留的 kext 位置不动（段间 ADRP、kext 间调用没有重定位记录，移动会静默坏掉），丢掉不用的 kext 让出空洞；内核用显式 `-segaddr` 重链进空洞（我们的段比 Apple 的大：`__TEXT` +0x88000、`__TEXT_EXEC` +0x1c000、`__DATA` +0x4c000、`__BOOTDATA` +0x4c000）；内核线程化指针转成 format-8 链式（复用封印脚本的 `--arm64e-chained` 解码器）；整体平移 KC 免费（目标按 KC 基址相对、代码 PC 相对）。基址冲突：内核链接在 `0xfffffff007004000`，kc265 在 `0xfffffe0007004000`，二选一。
- 步骤：里程碑 0（只含内核的 KC 启动到同一 panic）→ 里程碑 1（AppleImage4+CoreTrust+corecrypto 的重定位器）。

### 里程碑进展（2026-10-23）
- 里程碑 0 通过：`scripts/kc-build.py` 生成只含我们内核的 fileset KC，`XNU_KC=1 out/x12377/build-full.sh` 用 `kc-segaddrs.sh` 的 `-segaddr` 排布重链内核；DarwinBoot 补丁（`patches/darwinboot-accept-arm64e.patch`）放行 filetype 12。手机上启动到与之前相同的 `trust_cache_init` panic。
- KC 是平铺镜像（文件偏移 = vmaddr − 基址），链式指针 format 8 的目标是相对 KC 基址的 30 位偏移；内核的线程化重定位在 `kc-build.py` 里转成链；全局平移 `0x1f000000000` 把 kc265 的 `0xfffffe00…` 搬到我们的 `0xfffffff0…`（头里的 vmaddr、符号值、预链接 plist 地址、`kmod_info.address` 都要加；`kmod_info_t` 是 packed，`address` 在 +156，是 kext 里唯一一个未链式的绝对地址）。
- 里程碑 1 发现（AppleImage4 + CoreTrust + corecrypto + IOCryptoAcceleratorFamily）：
  - 26.5 的 217 个 kext 里没有任何一个用 `adrp` 取内核数据地址（全走 `__got` 的链式指针），所以重定位器只需改写 `b/bl`（按符号名，非符号目标视为 text 里的数据）和链式指针目标（按符号名，+偏移），不需要 adrp/consumer 配对。`scripts/kc_reloc.py` 即此。
  - corecrypto 的 `__text` 里夹常量表（`K256` 被列为函数起点），所以“指向内核但不是符号的 b/bl”按数据跳过。
  - corecrypto 的 POST 完整性校验是对 `__TEXT_EXEC,__text` 的 HMAC-SHA256（key = 一个 0 字节）与 `__TEXT,__fips_hmacs` 比较；改写分支会改变字节，所以 `kc-build.py` 重新计算（`seal_fips`，同 Apple 的 hmacfiletool）。
  - 预链接 plist 里 `com.apple.kpi.*`（`OSKernelResource`，无可执行体）必须保留，否则 “library kext com.apple.kpi.bsd not found”。
  - 真 corecrypto kext 启动成功（POST 全过）后会 `register_and_init_prng`，而我们内核自带的源码 corecrypto 引导已经把 PRNG 初始化过了（`prng_random.c:340 !prng_ready`）。结论：这条线上内核不再链入源码 corecrypto（`XNU_KEXT_CRYPTO=1`），像 macOS 一样由 kext 提供。

### 里程碑 2：安全扩展与 BSD 启动（2026-10-23）
- KC 里保留 AppleImage4、AMFI、Sandbox、Quarantine、AppleSystemPolicy、pthread（及依赖闭包）后，内核启动到 BSD 初始化完成、8 核全部上线，停在“Waiting on IOMedia UUID …”（等根盘）。`scripts/kc-try.sh SECS [bootargs…] -- BUNDLE…` 重做 KC 并上机一次，`scripts/kc-panic.sh` 读 panic 文本，`scripts/kc-disasm.py` 反汇编 KC 内任意地址并按各 entry 符号命名。
- 沿途修掉的内核侧问题：
  - AMFI 引用 `_csr_check`：`config/MASTER.arm64.bcm2837` 的 SECURITY_BASE 加 `config_audit config_csr config_csr_from_dt config_supplemental_signatures second_static_trust_cache`（arcade 编不过，先不开）。macOS 的完整配置（`MASTER.arm64.MacOSX`：sysv ipc、volfs、searchfs、quota、basesystemroot 等）与现用 iOS 派生配置差别很大，后面要逐项审计。
  - AMFI 只在 Sandbox 的启动里经 `amfi_register_mac_policy` 注册，所以 `trust_cache_init` 前必须带上全部 `AppleSecurityExtension` kext（AppleImage4、AMFI、Sandbox、Quarantine、AppleSystemPolicy）。
  - kext 的 `__kalloc_type` 视图带着 Apple 的真实类型签名，内核自己的全是“纯数据”，混用会在 kalloc 初始化里静默挂死；统一走数据堆（`kalloc_type_view_copy`，`BCM2837`）。
  - 4 KiB 页下内核 `__TEXT` 在 `__PRELINK_TEXT` 内被 contiguous hint 映射，`arm_vm_prot_finalize` 重设整段会触发断言，改成绕开内核 `__TEXT`。
  - 上游 LLVM 没有 `__builtin_load_member_function_pointer`，iig 生成的 `SimpleMemberFunctionCast` 回退到 union 强转，成员函数指针的 PAC 判别值和 C 函数指针类型不一致（`IOService::_Dispatch` PAC failure）；`iokit/DriverKit/Makefile` 里用 sed 换成 `OSMemberFunctionCast`（注意编译读的是 `iokit/DEVELOPMENT/DriverKit/` 的拷贝，要一并改并删掉旧 `.cpo`）。
  - `ml_unsafe_kernel_text`：设备树没有 `kernel-ctrr-to-be-enabled` 时默认 false。
- 下一步是根盘：宿主 VM 只有 virtio-mmio（`crosvm-mmio`，无 PCI），所以 Apple 自带的 AppleVirtIO（走 PCI 传输）用不上。26.5 的 IOBlockStorageDevice 有 51 个自有虚函数槽，与公开 IOStorageFamily 337.100.1 头在 `TARGET_OS_OSX=1` 下完全一致（`doLockUnlockMedia/reportLockability/reportPollRequirements/doDiscard` 只在 OSX 下有），所以 NativeVirtioBlock 可以按公开头编译，但它必须作为 KC 里的一个 kext 条目（要引用 IOStorageFamily kext 里的符号和签名指针），不能链进内核：需要把 `kc-build.py` 扩展成能把我们编译的 MH_OBJECT 链接成 fileset 条目（外部符号按内核/kext 符号表解析，arm64e 认证指针重定位，kmod_info、预链接 plist、个性字典）。

### 里程碑 3：根盘、launchd、ignition（2026-10-23）
**现状**：fileset KC（我们的 xnu-12377 arm64e 内核 + 26.5 原生 kext）在手机上启动到 launchd 的 dyld 阶段；根卷（OS 卷，UUID C73696D4-…）由 APFS kext 挂载，`/sbin/launchd` 经 4 KiB→16 KiB 签名哈希缓存验证后执行。当前卡点：dyld 找不到共享缓存（缓存在 SystemOS 卷里，需要 union 挂载到 `/`）。

**我们自己编译的 kext（`kc-build.py --native`）**
- `scripts/build-native-kext.py NAME 源码… [-I 目录] [-D 宏]`：按内核同样的编译参数把驱动编成可重定位 arm64e 目标文件（`out/x12377/native-kexts/NAME/`）。`overlay/kext/NativeKextGlue.cpp` 提供 `native_kext_start/stop`。
- `scripts/kc_native.py`：小型静态链接器。处理 BRANCH26/PAGE21/PAGEOFF12/GOT_LOAD/ADDEND/UNSIGNED/AUTHENTICATED_POINTER；未定义符号按名字解析到内核和 KC 里各 kext 的导出符号；指针变成 format-8 链式重定位；`__got` 槽、`kmod_info`（packed，`address` +156）、Mach-O 头（MH_KEXT_BUNDLE）、预链接 plist 条目（个性字典、库依赖）都由 `kc-build.py` 生成；位置从 kc265 里被丢弃 kext 腾出的空洞里首次适配。JSON 描述见 `overlay/kext/*.json`，可带 `vtable` 校验（驱动类的虚函数槽必须与基类 kext 里的槽逐个一致，`ignore_slots` 例外）。
- `NativeVirtioBlock`：只读 virtio-mmio 块驱动（fork 源码）。26.5 的 IOBlockStorageDevice 自有虚函数与公开 IOStorageFamily 337.100.1 头在 `TARGET_OS_OSX=1` 下完全一致（编译要 `-U TARGET_OS_OSX -D TARGET_OS_OSX=1`，头放 `out/x12377/storage-abi/include`，`TargetConditionals.h` 留空）。
- `NativeAES`：软件 AES-CBC 加速器（fork 源码）。26.5 的 IOCryptoAccelerator 比 iOS 17 多一个自有虚函数 `getAlgorithmName`，其余与 `OriginalAESABI.h` 一致（`overlay/kext/NativeAES/OriginalAESABI.h`）。**AppleImage4::start 在 `kmod_expert_finalize` 里 `waitForMatchingService("IOAESAccelerator")`，没有它 AppleImage4 不会 uncork，launchd 的 ignition 经 `security.mac.img4.ignition_blob` sysctl 永远睡眠。**

**内核侧改动（`out/x12377/xnu-m`，尚未固化成补丁）**
- `config/MASTER.arm64.bcm2837`：SECURITY_BASE 加 `config_audit config_csr config_csr_from_dt config_supplemental_signatures second_static_trust_cache`（arcade 编不过）。
- AMFI 只在 Sandbox 启动时经 `amfi_register_mac_policy` 注册：`trust_cache_init` 前必须把全部 `AppleSecurityExtension` kext 带上。
- `kalloc_type_view_copy`：kext 的视图带 Apple 的类型签名，内核自己的全是纯数据；统一当数据（登记数据堆并置 `KT_DATA_ONLY`，入口函数读视图里的标志）。
- `arm_vm_prot_finalize`：4 KiB 页下内核 `__TEXT` 在 `__PRELINK_TEXT` 内被 contiguous hint 映射，重设整段会触发断言，改成绕开内核 `__TEXT`。
- iig 生成的 `SimpleMemberFunctionCast` 在上游 LLVM 里回退到 union 强转，PAC 判别值错位（`IOService::_Dispatch`）：`iokit/DriverKit/Makefile` 用 sed 换成 `OSMemberFunctionCast`（编译读 `iokit/DEVELOPMENT/DriverKit/` 的拷贝，要一并改并删旧 `.cpo`）。
- `ml_unsafe_kernel_text`：设备树无 `kernel-ctrr-to-be-enabled` 时默认 false。
- `bsd_init.c`：开机参数 `rootauth=0` 跳过根卷认证（没有 boot manifest；临时）。设备树 `/chosen/asmb`（`lp-sip0`、`lp-sip1`=1）使 APFS 报 `ARV disabled`（`scripts/run-macos-vm.py make_adt` 注入）。
- `XNU_NATIVE_CS_HASH_CACHE=1`：macOS 用户态用 16 KiB 页签名，4 KiB 内核用 fork 的哈希缓存验证（`ubc_subr.c` 里 `vm_map_protect` 换成 `mach_vm_protect` 才编得过）。
- 诊断：`sample-pid=<pid|-1> [sample-period=<秒>]`（`osfmk/kern/exception.c`）周期性把该进程（-1 为 kernel_task）每个线程的状态、等待事件、用户 pc/lr/sp/fp、所在映射的文件路径、睡眠线程的内核栈打到消息缓冲区；符号化用 `llvm-nm -n` 的内核符号表和 `scripts/kc-disasm.py`。用法：先把 pid 1 的 pc 减去 `main`（即 mach 头）得 slide，再看 dyld/launchd 反汇编。
- owner 链（fork 的 `XNU_OWNER_CACHE_MOUNT/UNION_SYSTEMOS/BOOT_MANIFEST/CACHE_STARTUP`，在 `kern_exec.c`/`IOKitBSDInit.cpp` 里已有）：开发期用桩替掉验证——`osfmk/kern/link_compat.c` 的 `native_verified_block_root_authorized`（恒真）、`native_verified_block_manifest_sha384`（卷 UUID 文本的 SHA-384）；`IOKitBSDInit.cpp` 里 `native_verified_block_volume_device` 经 IOKit 按 UUID 找 IOMedia 得设备号和路径。`build-full.sh` 打开这些宏，并设 dyld 标志位 8（跳过 ignition）。**这一步刚接上，还没上机验证。**

**盘的角色**（沿用旧线）：OS 卷是根（`/usr/lib/ignition`、`/sbin/launchd`）；SystemOS 卷（UUID 8846FE78-…，里面是 Cryptex1,SystemOS 内容、dyld 共享缓存、firmlink 目标和垫片）在 launchd 之前由内核 union 挂到 `/`；Data 卷挂 `/private/var`（`XNU_OWNER_DATA_MOUNT`，还没接）。ignition 找 Preboot（role 0x10 的卷）失败，所以要么跳过 ignition，要么提供 Preboot+cryptex dmg。

**上机辅助脚本**：`scripts/kc-try.sh SECS [开机参数…] -- BUNDLE…`（环境变量 `NATIVE="a.json b.json"`）重做 KC 并上机；`scripts/kc-panic.sh` 读 panic 文本；上机失败常是上一轮 VM 还没停（脚本会重试）。`/tmp/keep3.txt` 里放当前保留的 kext 列表（AppleImage4 AMFI sandbox quarantine AppleSystemPolicy pthread apfs AppleFSCompression…）。

**待办（本轮发现）**：SystemOS union 挂载上机验证；Data 卷挂载；启动参数 REQUIRED_ARGS（`mac-sandbox-permissive` 等，26.5 原生 Sandbox/AMFI 下可能不再需要，要逐个试）；owner policy / boot manifest 的真实实现；NativeVirtioBlock 只读，Data 需要可写块设备；把 `xnu-m` 的改动固化成 overlay 补丁。

### 里程碑 4：launchd 起完整启动流程（2026-10-23）

现状：fileset KC（12377 内核 + 26.5 原生 kext + 三个自编原生 kext）→ launchd → 全部早期启动任务（fsck、mount-phase-1/2、data-protection、auto-pivot-root、MobileAssetEarlyBootTask、cc_fips_test、usermanagerd、dirs_cleaner…）→ Data 卷挂 `/private/var` → `tzinit` → xpcproxy 起各守护进程（pid 已到 200 左右）。当前在崩溃重启的：fskitd（exit 1）、xpcproxy（exit 78）、endpointsecurityd（exit 35）、opendirectoryd、xprotectd、tccd、revisiond。

**真修复（按发现顺序，内核侧都在 `out/x12377/xnu-m`，快照 `out/x12377/xnu-m-uncommitted.diff`）：**
1. `load_init_program`：`scratch_addr` 在分配用户页之前就传给 SystemOS 挂载（EFAULT），分配提前。
2. dyld 缓存映射 `EPERM`：`shared_region_map_and_slide_setup` 在 CSR 未放开 `ALLOW_UNRESTRICTED_FS` 时要求文件带 `SF_RESTRICTED`；临时用 `MACOS_LP_SIP0=0x2`（`/chosen/asmb` 的 lp-sip0）。
3. 共享缓存里的认证指针没签名：我们加的 16 KiB 滑动窗口分支（`vm_shared_region_pager.c`）把 `jop_key` 写死成 0；改传 `srp_jop_key`。
4. 没有半虚拟化 PAC 时 `ml_default_jop_pid()` 返回 0，pager 不签名：改返回 1（硬件密钥各进程相同，非零只是"用户密钥在用"）；`ml_non_arm64e_user_jop_pid()` 同理。
5. **用户 VA 宽度与 PAC 宽度**：PAC 码的位置跟 TCR.T0SZ 走（内核指针也是），macOS 用户态（objc `ISA_MASK 0x7ffffffffff8` 等）按 47 位剥码，39 位（T0SZ 25）会留下 [46:39] 的残码，类指针解引用崩溃。做法：硬件 TCR 的 T0SZ 从第一条指令起就是 17（`T0SZ_HW`，proc_reg.h），pmap 几何仍按 `T0SZ_BOOT`；TTBR0 经一页只有第 0 项的 L0 表指到原来的 L1 根——引导恒等映射（`start.s`，引导页表池最后一页）和每个用户 pmap（`pmap_create` 分配 `hw_tte`，`pmap_switch` 装 `hw_ttep`）。**运行中途改 T0SZ 不行**（已签名的内核指针按旧宽度签的，改后认证失败）。
6. 插件宿主（AMFI 标 sh/bash 的 `IMGPF_3P_PLUGINS`）会把用户 JOP 关掉（keys-off）：这块硬件上没有逐进程密钥切换，关不掉，dyld 不给自己的指针签名就崩；BCM2837 构建里不对插件宿主设 `NOJOP`。
7. **AMFI 的 CoreEntitlements 栈检查**：`sp & ((1<<PAGE_SHIFT_CONST)-1) < 128` 假设栈与页同大且对齐（Apple 16 KiB）；我们的内核栈在 4 KiB 保护页之上、不与栈大小对齐，sp 落在某个对齐边界上 128 字节内就误报，任何带权限 DER 的进程（seputil 的数组值）的字典拷贝失败，AMFI panic「failed to create OSDictionary copy: 14」。`scripts/kc_reloc.py patch_stack_checks` 把那条 `cmp x8,#128` 改成 `cmp x8,#0`（栈本身有保护页）。
8. Data 卷：fork 的 `NativeRamBlock` 驱动（读 DT `/chosen/memory-map/PackedRAMDisk`，把 `scratch-data.img` 解成稀疏内存盘并发布 IOMedia）编成原生 kext（`overlay/kext/NativeRamBlock.json` + `NativeUfsStoreStub.cpp` 提供它弱引用的持久化钩子，返回"无存储窗口"）；内核 `XNU_OWNER_DATA_MOUNT`+`XNU_NATIVE_RAM_BLOCK`，`link_compat.c` 的 `native_ram_block_volume_seed` 用 IOMedia UUID（8748FE31-7E7F-4BFA-A7E2-7A4F5E14D0F6）找设备。数据是易失的（重启丢），持久化要接 fork 的 `native_ufs_store_*`（DroidVM 的 store 窗口，rig 已挂 `--data-store-mmio`）。
9. 构建器：`kc_native.py` 放置 `__literal4/8/16` 和 `__auth_ptr` 段。

**临时手段（要记账，正式做法是 boot manifest / owner policy 等）：**
`MACOS_LP_SIP0=0x2`、`rootauth=0`、owner 链验证桩、`ml_default_jop_pid()`/non-arm64e 返回 1、插件宿主不关 JOP、CE 栈检查摊平、launchd 给的 kqworkloop 软/硬限额忽略（`proc_set_kqworkloop_limits`，opendirectoryd 限额 3/10 会被杀）、`NativeUfsStoreStub`（Data 易失）。

**诊断工具（`crash-log=1`）：** 崩溃时打印 pc/lr、x0–x28、x19/x0 指向的内存、pc/lr 所在镜像；`scripts/crash-symbolize.py LOG DSC IPSW 进程名` 用 `ipsw dyld a2s` 符号化（`ipsw` 在 `~/gotmp/ipsw`；`/tmp/cx27` 是只读挂载的 SystemOS，`ipsw dyld extract … -c /tmp/ext/dsc.a2s` 可导出单个 dylib 反汇编）。AMFI 内部排障用的是"改 KC 里的指令为 `brk #N`/`bl` 到内核桩"的办法（`/tmp/ce-trace*.sh`，一次性，未入库）。

**教训：**
- 内核是按 `-segaddr` 塞进 Apple 内核留下的洞里的（`kc-segaddrs.sh`）：`__DATA_CONST` 洞与现有大小恰好相等，`__TEXT_EXEC` 只剩约 96 KiB 余量。**新增 config 选项一多就会让某个段溢出到下一个段，ld64 报 `OutputFile.cpp:3194 Assertion addressA != addressB`**（不是某个选项的错，是布局）。要补全 macOS 配置（见下）必须先重做 KC 布局（把后面的段整体挪出空间），或者精简内核其他部分。
- config 改动后 make 不会重编所有用到该宏的文件（会残留对已删符号的引用，如 `gif_init`）：**改 MASTER 后必须清掉对象目录（`rm -rf build/xnu/e-obj/DEVELOPMENT_ARM64_BCM2837`）全量重编**，不然二分结果会被污染。
- `git checkout` 会冲掉未提交的编辑（又丢过一次 `kc_native.py` 的 literal 段），还原文件先备份。
- 上机偶发"根盘没出现"（等 IOMedia 60 秒，约 1/3 概率）：重试即可，判据用有没有 `BSD root:`，不要用 `Waiting on`（成功的启动也有）。

**待办（本轮发现）：**
- macOS 配置补全（`MASTER.arm64.MacOSX` 对比）：FILESYS（`config_ext_resolver`=identitysvc，opendirectoryd 需要；`quota config_searchfs config_volfs config_appledouble nullfs config_mnt_suid config_mount_vm config_file_leases config_rosv_startup config_firmlinks config_basesystemroot config_mount_prebootrecovery`）、BSD（`sysv_sem/msg/shm`）、KERNEL（`config_delay_idle_sleep config_proc_udata_storage config_uexc`，`config_embedded` 还留着）、MACH（`config_user_notification config_voucher_deprecated config_arm_pfz`）、NETWORKING（`sendfile bond gif stf ifnet_input_chk MULTIPATH remote_vif`，同样受段布局限制）。先决条件：KC 段布局留余量。
- 先只开 `config_ext_resolver`（最小改动，修 opendirectoryd 的 SIGSYS）。
- 各守护进程崩溃逐个查：fskitd、xpcproxy 退出 78（EX_CONFIG）、endpointsecurityd 35、tccd（`confstr` 取目录失败，依赖 dirhelper）。
- 去掉诊断打印再长跑（`ents-set` DER 转储每次 exec 都打，会冲掉 DMESG 窗口；IOKitBSDInit 探针；`native_ce_dump/trap`；`exec_mach_imgact`/`reboot:` printf）。
- 固化内核改动为 overlay 补丁（按修复分组，不含诊断），Data 持久化接 store。

### KC 段余量与 iig 超时（2026-10-23 晚）
- ld64 `addressA != addressB` 断言是内核 `__DATA_CONST`（0x810000，后面紧跟 `__LASTDATA_CONST`）零余量；把它前移到 0x78c000（`kc-segaddrs.sh` 与 `kc-build.py` 的 `DATA_CONST_START` 同步，上限是 `__PRELINK_TEXT` 末尾 0x78c000）后链接通过，带 `config_ext_resolver`。
- 不要动 `__KLD/__LAST/__PRELINK_TEXT`（挪到 0x3800000 之后内核没有任何输出，原因未查）。
- `target-iig`（compat/xnu-linux/linux/darwin-tool.py）加了 180 s 超时：杀容器里的 iig（`pkill -x`）、删半成品、最多重试 3 次。
- 结果：opendirectoryd 不再 SIGSYS；烟测要跑 ≥200 s（90 s 只到 "Waiting on" 就截断）。

### 里程碑 5：launchd 稳定起来（2026-10-23 夜 / 10-24）
**修复**
- 沙盒用户态/内核不匹配：macOS 27 用户态 + 26.5 Sandbox kext。27 编译的配置 204 个 operation，kext 只认 198（`operation count mismatch`），call 264 在 kext 跳表里不存在（默认返回 45）。`security/mac_base.c` 在 `mac-sandbox-permissive` 下把 call 0/1/22 的 ENOENT/EINVAL 与 call 1/264 的 ENOTSUP 当成功（进程无沙盒运行）。**call 4（sandbox_container）不能忽略**：调用方拿未初始化缓冲区，dirhelper 会 stat 垃圾路径。264 被忽略后 dirhelper 才能建 `/var/folders/zz/...`，runningboardd/trustd/tccd/mobileassetd 等不再 exit 1。`sandbox-call-shift=N` 引导参数（调用号整体偏移）已验证无用：call 0 就是 apply，不是编号整体偏移。
- NativeVirtioBlock：请求与复位超时 1 s → 30 s（主机忙时 start() 的首次读超时，设备永不出现；读超时还会 reset 设备，之后 "device is not ready"，launchd 在 check_signature 读 dyld cache 时死亡并 panic 重启）。根卷不出现（一直 "Waiting on IOMedia UUID"）曾被当成"APFS 同时挂两个容器会死锁"，实为 AppleAPFSContainer::start 拿着 APFS 模块锁等 IOResources 匹配完 IOBSD、而那轮匹配卡在 com_apple_filesystems_apfs::start 等同一把锁（2026-11-02 查明）：现在发布前先 `waitForMatchingService(resourceMatching("IOBSD"))`（NativeRamBlock 同理，在线程里等），再按 MMIO 地址从高到低逐个发布（0xa001000、0xa000000；0xa002000 是 DroidVMDataStore），根卷（最低地址）最后出现，不再每盘 sleep 1.5 s。补丁 `overlay/kext/NativeVirtioBlock.patch`（对 sources/UniXNU 的 diff）；构建命令需带 `-I sources/UniXNU/drivers/NativeVirtioBlock -D U:TARGET_OS_OSX -D TARGET_OS_OSX=1`（少了这两个，vtable 变化，内核早期 PAC failure）。
- KC 段余量：`kc-segaddrs.sh` 的 `__DATA_CONST` 0x810000 → 0x78c000（上限是 `__PRELINK_TEXT` 末尾 0x78c000），`kc-build.py` 的 `DATA_CONST_START` 同步。`__KLD/__LAST/__PRELINK_TEXT` 不能挪（挪到 0x3800000 后内核无任何输出，原因没查）。
- `target-iig`（darwin-tool.py）180 s 超时：杀容器里的 iig（`pkill -x iig`）、删半成品、最多重试 3 次。

**新增诊断引导参数（内核，需在提交前去掉）**
- `stderr-log=1`：打印所有进程写 fd1/fd2 的内容（sys_generic.c write_nocancel）；这是定位 daemon exit 1 的最有效手段。
- `sc-trace=<进程名>`：打印该进程每个 BSD 系统调用（号、errno、a0、路径类参数）（systemcalls.c）。
- `host_reboot:` 打印、`sandbox-call:` 打印（已有）。

**教训**
- 烟测 `kc-try.sh` 里 `timeout 400`：SECS 不能超过 ~380；之前的长跑失败/重启被它截断。
- 串口日志 `/tmp/xnu12377-serial.log` 是累积的（清空命令不生效），`UNIXNU: boot: entry` 次数不是重启次数。
- dmesg 环形缓冲 128 KB，`ents-set` 等调试输出会把早期日志冲掉（mount-complete 计数会变 0），判断挂载是否成功要看 "Waiting on"/exec 数。
- 主机内存紧（手机 free ~0.4 GB）时 VM 变慢，不是内核问题；`drop_caches` 不要做。
- 遇到 "disk3s1: I/O timeout" 先看是不是 NativeVirtioBlock 超时，而不是内核/launchd。

**仍在失败**：xprotectd(1)、fskitd(1, "error starting up the daemon")、digest-service(1)、apsd(NSException abort)、endpointsecurity(35)、xpcproxy(78, file-write-create /dev)、WindowServer(1, 无 GPU)；`/System/Volumes/Data/MobileSoftwareUpdate` 报 Read-only file system。

### 追加（2026-10-24）：诊断工具与剩余失败项
- `sc-trace=名1,名2,...`（逗号分隔，最多 16 字符/个）现在只打印这些进程**失败**的 BSD 系统调用（跳过 sigaction/mprotect/mmap/close 等噪音），配合 `stderr-log=1` 使用。dmesg 环形缓冲只有 128 KB，`msgbuf=` 引导参数无效，所以不要抓全量 trace。
- 内核命令行上限 1000 字节，板级 `board.toml` 里有大量 iOS 遗留参数（`offline-legacy-*` 等）。`run-macos-vm.py` 的 `kernel_args` 现支持额外参数 `drop:NAME` 去掉板级参数（`kc-try.sh` 的引导参数处直接写 `drop:offline-legacy-register ...`）。`rootauth=0` 不能省（省掉后根卷鉴权失败，execs=0）。
- 当前失败项的结论：
  - fskitd（"error starting up the daemon: Undefined error: 0"）、endpointsecurity（35）、digest-service（1，无 stderr）、xprotectd（1）在失败 BSD 调用里没有线索，疑似 Mach/XPC（bootstrap_check_in）失败，需要 Mach trap 级别的 trace 才能继续。
  - apsd：NSException，最后的失败调用是 `mac_syscall`（Sandbox call 4 ENOTSUP）。
  - WindowServer：SkyLight 资源探测失败属正常；退出 1 前没有 stderr，预计是缺显示/GPU。
- 常见的无害噪音：csrctl(483)=EPERM、map_with_linking_np(550)=EINVAL、ioctl(54)=ENOTTY、crossarch_trap(38)=ENOTSUP、`/AppleInternal/XBS/.isChrooted` 与 Info.plist 的 ENOENT。

### WindowServer / GPU 调查（2026-10-24）
- 新增诊断：`iokit-log=进程名[,进程名]`（IOUserClient.cpp，打印 IOServiceGetMatchingService(s)、IOServiceAddMatchingNotification、IOServiceOpen 的匹配字典与结果）。注意内核日志缓冲只有 128 KB，要同时关 `stderr-log`/`exec-log` 减少噪音，WindowServer 在启动后约 2~3 分钟才被拉起，烟测要 ≥340 s。
- KC 里原先只保留 9 个 kext，没有 IOHIDFamily，WindowServer 第一步查 IOHIDSystem 就找不到。加入 `com.apple.iokit.IOHIDFamily` 后（`/tmp/keep4.txt` = keep3 + IOHIDFamily，链接无缺符号、能启动）：WindowServer 找到并打开 IOHIDSystem，然后查 `AppleDisplayManager`（kIOReturnNotFound），之后不退出，在等显示/GPU。`AppleDisplayManager` 这个类名在整个 26.5 vma2 内核缓存里不存在。
- vma2（VMApple 虚拟 Mac）设备树里 GPU 是平台 MMIO 设备：`arm-io/gfx` compatible `paravirtualizedgraphics,gpu`（reg 0x20200000 size 0x10000，interrupts 1，role APV_GFX，`gpu-sysmem-reserve-percent`），`arm-io/iosurface-mapper` compatible `paravirtualizedgraphics,iosurface`（reg 0x21200000，interrupts 0，role APV_IOSFC）；另有 `pcie,vmapple1`。KC 里已有 AppleParavirtGPUIOGPUFamily、AppleParavirtIOSurface、IOGraphicsFamily、IOSurface、IOMobileGraphicsFamily、AppleM2ScalerCSCDriver 等 kext。
- 参考项目：medfa12/apple-silicon-anyos-project（GPL-2.0；metal2vulkan 为 LGPL-3.0）在 QEMU vmapple 上跑 macOS 26，客户机不改，用系统自带的 AppleParavirtGPU，主机侧自己实现 PVG 设备（`pvg-vulkan` ~24 万行 Rust，含 wire 解码 22k 行）+ Metal AIR→SPIR-V（metal2vulkan）+ Vulkan 渲染，已渲染出 Welcome/Language 界面（CPU lavapipe）。UniXNU-droidvm 的 GPU 是 iOS 路线（NativeAdreno/droidvm-gpu wire + Metal 插件），用户空间不同。
- 结论：macOS 路线要走 PVG（AppleParavirtGPU + 主机侧 PVG 设备），不是 iOS 的 IOMobileFramebuffer。需要：ADT 加 gfx/iosurface 节点、KC 加这些 kext、crosvm 加 MMIO 设备实现 PVG 协议并渲染。许可证（GPL/LGPL 与 crosvm BSD）需要先确认。

## union 根（union-hide-lower=1）的两个后续补丁（2026-10-28）
- 0013：盖在根卷根 vnode 上的挂载在 statfs/getfsstat/vfs sysctl 里报 MNT_ROOTFS（`virt_union_visflags`），否则 fseventsd 不建全局 logger，FSEvents 客户端全部 10 s 超时。
- 0014：只读 union 层上 CREATE 查找得 EJUSTRETURN 时也下沉到被覆盖层，否则 `mkdir("/dev")` = EROFS（应为 EEXIST），xpcproxy 起不了 StandardErrorPath 在 /dev 下的服务（kernelmanagerd）。
