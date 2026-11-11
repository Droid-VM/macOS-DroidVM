# k27 原生 PCIe 桥（AppleVirtualPlatformPCIE）+ MSI 方案（2026-11-11）

## 目标

让 k27 用苹果自带的 vmapple PCIe 桥 `AppleVirtualPlatformPCIE`（`com.apple.driver.AppleVirtualPlatform`）枚举 crosvm 的 virtio-pci 设备，中断走 MSI-X，经 crosvm 的 MBI 帧（`--mbi-spis`，2f3fcf217）投递成 GIC SPI。做成后：
- 苹果自带的 AppleVirtIO（`AppleVirtIOPCITransport` 匹配任何 IOPCIDevice，再分发到 Block/Network/Console/Entropy/Balloon/9P/FS/Input/Socket/Sound…）可以直接驱动 crosvm 的 virtio-pci 设备；
- 有了 IOPCIDevice nub，USB 直通（crosvm xHCI，`AppleUSBXHCIPCI`）等 PCI 设备才有落脚点（记忆 macos-usb-passthrough-analysis）；
- 中断由设备主动送达，不再靠轮询。

## 现状

- `/arm-io/pcie` 是 `pci-host-ecam-generic`（`scripts/run-macos-vm.py` make_adt 从 FDT 抄 ECAM 窗口），只给 DroidVMInput 直接映射 ECAM 轮询 virtio-input 用；没有 IOPCIBridge，也就没有 IOPCIDevice。
- GIC 由 UniXNU ArmCpu 直接驱动：`armcpu_spi_attach()`（`sources/UniXNU/drivers/ArmCpu/ArmCpu.cpp`）只有 16 个槽，只能挂、不能摘，路由到启动核；不是 IOInterruptController，也没有向平台注册中断控制器名。
- 其余设备（Data 盘、网卡、GPU、声卡、media）都在 virtio-mmio 上，由自写 kext 轮询。
- KC：`configs/kc-keep.txt` 已经因为依赖带进了 `com.apple.iokit.IOPCIFamily`；`com.apple.driver.AppleVirtualPlatform` 和 `com.apple.driver.AppleVirtIO` 都没保留。
- `AppleARMIODevice` 只是 `overlay/kext/ARMPlatformStandIn.cpp` 里的空类；ArmDTPlatform 给 arm-io 子节点建的 nub 是 IOPlatformDevice。
- crosvm 的 MBI 帧在 0x7000（GICv2m 布局：`MSI_TYPER` 0x8 = `base << 16 | count`，`MSI_SETSPI_NS` 0x40 写 INTID 触发该 SPI），FDT 里是 intc 的 `mbi-ranges` / `mbi-alias`；Linux、Windows guest 已经在用。

## 苹果桥的接口契约（IDA，27.2 KC 抽出的 AppleVirtualPlatform）

### AppleVirtualPlatformPCIE（`IOPCIHostBridge` 子类）
- personality：`IOProviderClass AppleARMIODevice`，`IONameMatch pcie,vmapple1`。
- `start(provider)`：
  1. `provider->mapDeviceMemoryWithIndex(0)` 映射 ECAM；配置空间读写走这个映射。
  2. 读 `device-interrupt-parent`（必须是 4 字节），用 `propertyMatching("AAPL,phandle", 值)` 做 `waitForMatchingService`（无限等）。等到的服务就是"中断父"，取不到就 panic。
  3. `msi-frame-index` 是**可选**的：没有这个属性就不建 MSI 控制器，桥照样起来，只有 INTx。有这个属性时（必须是 4 字节）调用 `AppleVirtualPlatformPCIEMSIController::withMessageBasedInterruptFrameIndex(中断父, idx)`，返回空就 panic。（更正记忆 macos-usb-passthrough-analysis 里"断言 fMsiController 非空"的说法：只有写了 `msi-frame-index` 才断言。）
  4. 在自己的配置空间找 capability 9（厂商自定义），拿两位苹果私有特性开关；找不到两位都是 0，不影响启动。
  5. `IOPCIHostBridge::start`。
- `configure`：节点的 `#address-cells` 必须是 3、`#size-cells` 必须是 2，否则直接返回。`ranges` 按 28 字节一项解析，每项对 **PCI 地址**（偏移 4 的 u64）和大小（偏移 20 的 u64）调用 `addBridgeMemoryRange(addr, size, true)`；桥分配窗口时不看父地址那一列；子设备的 IODeviceMemory 仍由 IODTResolveAddressing 按 ranges 转换。crosvm 的 PCI 地址等于绝对物理地址，但 ADT 的父地址必须减去 ARMIO_BASE。只有内存窗口，没有 I/O 空间。
- `callPlatformFunction`：
  - `GetMessagedInterruptAddress`：地址 = MSI 帧物理地址 + 0x40，**数据 = 向量号本身**（范围检查 `[base, base + count)`），也就是数据就是 INTID，和 GICv2m 的 SETSPI 语义一致。
  - `GetMessagedInterruptController`：返回 MSI 控制器。
  - 另外处理 `IOPCIDeviceChanged`（热插拔）。

### AppleVirtualPlatformPCIEMSIController（`IOPCIMessagedInterruptController` 子类）
- `init(中断父, idx)`：
  - `中断父->getProperty("InterruptControllerName")` 必须是 **OSSymbol**，再用 `IOPlatformExpert::lookUpInterruptController` 取父中断控制器；取不到就 panic。
  - `中断父->mapDeviceMemoryWithIndex(idx)` 映射 MSI 帧，门铃 = 物理地址 + 0x40。
  - 读 TYPER（+8）：**bit31 必须是 1**，否则 panic；`count = TYPER & 0x1fff`，`base = (TYPER >> 16) & 0x1fff`。
  - `IOPCIMessagedInterruptController::init(count, base, 0)`。
- `initVector` / `enableVector` / `disableVectorHard`（本地编号 i）把 `(base + i, 本控制器的 IOInterruptVector *)` 原样转给父中断控制器的同名虚函数（vtable +2248 / +2272 / +2264，已按本类自己的 vtable 核对过槽位）。
- 本类的 `handleInterrupt` 直接 panic：父控制器收到 SPI 后必须**直接**调用 `initVector` 交给它的那个 `IOInterruptVector` 的 handler，不能再转回 MSI 控制器。

### INTx（AppleVirtualPlatformPCIEInterruptResolver）
- 桥的 `initialize` 发布 `resolvePCIInterrupt` / `setDeviceInterrupts` 两个资源。
- `resolvePCIInterrupt(桥, n, …, *out)`：`*out = interrupt-base + n`，`interrupt-base` 是桥节点上 4 字节的属性；没有这个属性就失败（设备没有 INTx，不 panic）。
- `setDeviceInterrupts`：把 `[INTID, 1]` 写进设备的 `IOInterruptSpecifiers`，控制器用中断父的 `InterruptControllerName`。
- crosvm 的 INTx 是逐设备从分配器取号（FDT `interrupt-map`），不是"基址 + n"，所以第一版**只用 MSI**，不写 `interrupt-base`。
- n 的含义（QEMU vmapple 对照，见下节）：QEMU 用 GPEX 的 4 根 INTx 线，接到 SPI 0x20..0x23 并 `gpex_set_irq_num`，所以 n 是按插槽交错后的 INTA..INTD（0..3），`interrupt-base` = 0x20 + 32。crosvm 要支持 INTx（xHCI）就得改成同样的 4 线交错。

### 依赖（决定能不能"原样加载"）
- AppleVirtualPlatform 的 `OSBundleLibraries`：AppleARMPlatform、AppleCallbackPowerSource、AppleMobileFileIntegrity、AppleVirtIO、AppleVirtIOStorage、IOAccessoryManager、IOCryptoAcceleratorFamily、IOHIDFamily、IOPCIFamily、IOSerialFamily、IOStorageFamily、IOUSBDeviceFamily、corecrypto。
- 它的其他类继承 AppleARMIO / AppleARMPE（vtable、构造/析构、约 30 个成员函数）、IOUSBDeviceController、AppleCallbackPowerSourceProvider。PCIE 桥和 MSI 控制器本身只用到 IOPCIFamily 和 IOService。
- 我们用 ARMPlatformStandIn 顶替 AppleARMPlatform，用它顶替 IOUSBHostFamily；当初正是为了不带进 IOAccessoryManager（它会拖进 AppleSMC、RTBuddy、AppleA7IOP）。所以"原样保留 AppleVirtualPlatform"的首要风险是依赖闭包和顶替符号，见 P0。

## 外部参照：QEMU vmapple（steelbrain/reims-vgpu 的 vendor/qemu）

reims-vgpu 用 QEMU 的 `vmapple` 机器启动 Virtualization.framework 的 macOS 26/27 客户机，走的正是 AppleVirtualPlatformPCIE。可以借用的是它验证过的事实（QEMU 是 GPL，只参照行为，不搬代码）：
- `hw/intc/arm_gicv2m.c` 有 `macos_compat` 属性，打开后 MSI_TYPER 置 **bit31**，和我们逆向出的检查一致。vmapple 的 GICv2m 帧在 0x1fff0000，128 个 SPI，基址 0x80（INTID 0xa0）。
- vmapple 的 PCIe：ECAM 0x40000000（256 MiB）、MMIO 窗口 0x50000000–0xffffffff 恒等映射、INTx 4 线 SPI 0x20 起。
- macOS 27 的 AppleVirtIOPCITransport 要求 virtio capability 链**按地址升序**链接，否则每秒约 10 万次配置读、设备状态一直是 0、黑屏（QEMU d235e51310）。crosvm 的 `PciConfiguration::add_capability` 每次都接在链尾、偏移递增，本来就是升序，不受影响。
- Apple 的 virtio 厂商 capability（cfg_type 9、vendor 0x106b、14 字节、带"传输加密关闭"标志）：QEMU 只给 vmapple-virtio-blk-pci 加了，说是不开 FileVault 的根盘需要；网卡没有。我们 P3 用块设备时如果卡住，先补这个。
- ADT 由 Apple 的 AVPBooter 固件根据固定内存布局生成，不在 QEMU 里，所以拿不到 ADT 参照，ADT 仍按我们的逆向写。
- GPU（apple-gfx / Metal 宿主）、VideoToolbox 设备与本方案无关；VT 协议的参照另见 reims-vgpu-vtpv-contract.md。

## 设计

### crosvm
- `devices/src/mbi_frame.rs`：`MSI_TYPER` 加 bit31（`1 << 31 | base << 16 | count`）。Linux 走 `mbi-ranges` 不读 MBI 帧；Windows 读 MADT 里的 GIC MSI Frame（GunyahMbiAcpiDxe），要确认它有没有设置"SPI 数量/基址取自 MADT"标志、读 TYPER 时会不会屏蔽高位。不确定的话，把 bit31 做成只对 macOS 开启的开关。
- macOS VM 启动参数加 `--mbi-spis N`（先用 64）。virtio-pci 设备每个 MSI-X 向量占一个 SPI（队列数 + 1 个配置向量）；64 个够 4 个输入设备加几个块/网卡设备。
- 不改 crosvm 的 PCI 分配：PCI 地址 = CPU 地址，低 32 位窗口加高 64 位可预取窗口，和桥的 `configure` 吻合。

### ADT（`scripts/run-macos-vm.py` make_adt，只在 `MACOS_PCIE=1` 时启用）
- `/arm-io/pcie`：
  - `compatible` / `name` = `pcie,vmapple1`（IONameMatch 看 name/compatible）；
  - `reg` = ECAM（第 0 项）；
  - `#address-cells` = 3，`#size-cells` = 2；
  - `ranges`：从 FDT pci 节点的 `ranges` 转写，每项 `struct.pack('<IQQQ', 空间标志, pci 地址, cpu 地址 - ARMIO_BASE, 大小)`。ADT 是小端，桥按 u64 读偏移 4 和 20，**不能**照抄 FDT 的大端 cell 顺序；
  - `device-interrupt-parent` = 一个 ADT 里不存在的自定义 phandle（例如 0x4d424946），见下节；
  - `msi-frame-index` = 0；
  - `dma-coherent`；不写 `interrupt-base`。
- 新节点 `/arm-io/gic-mbi`：`compatible droidvm,gic-mbi`，`reg` = MBI 帧（从 FDT intc 的 `mbi-alias` 取，0x7000，大小 0x1000）。不把 MBI 帧追加到 `/arm-io/intc` 的 `reg`：`ArmCpu::mapGic` 要求 intc 的 `reg` 长度刚好是两项。

### GIC 中断控制器 kext（新，`overlay/kext/DroidVMGicMsi`）
- `DroidVMGicMsi : IOInterruptController`，`IOProviderClass IOPlatformDevice`、`IONameMatch droidvm,gic-mbi`。
- `start`：
  1. `setDeviceMemory(provider->getDeviceMemory())`，让 `mapDeviceMemoryWithIndex(0)` 在自己身上就能映射 MBI 帧；
  2. `getPlatform()->registerInterruptController(sym, this)`；
  3. 在自己身上设 `InterruptControllerName` = 同一个 OSSymbol、`AAPL,phandle` = 上面的自定义值；
  4. 最后 `registerService()`。
  这样桥 `waitForMatchingService` 等到的一定是已经准备好的控制器。如果用 intc nub 自带的 phandle，nub 早就注册了，桥可能在属性写好之前就读，会 panic。
- `initVector(intid, v)`：记下 `intid → v`。`enableVector`：经 ArmCpu 把该 SPI 配成边沿、group 1、路由启动核，然后使能。`disableVectorHard`：关掉这个 SPI。
- 分发：ArmCpu 收到这个 INTID 后，调用 `v->handler(v->target, v->refCon, v->nub, v->source)`，然后由 ArmCpu 发 EOI。边沿 MSI 不需要清源。
- 以后同一个控制器也可以给 virtio-mmio 设备挂中断（替代各 kext 的轮询），但不在本方案范围内。

### ArmCpu（UniXNU 内核补丁，尽量小）
- 现有 `armcpu_spi_attach` 只能挂不能摘，16 个槽。改为：
  - 按 INTID 直接索引的表（覆盖 32..32+GICD_TYPER 报的数量）；
  - 新增 `armcpu_spi_set_enabled(intid, bool)`，对应 ICENABLER/ISENABLER；
  - `handler == nullptr` 表示摘除。
- 中断分发路径不变：仍在 EOI 之前调用 handler；未挂 handler 的 SPI 仍旧计数并关闭。
- `armcpu_spi_attach` 的原接口保留，现有调用方不用改。

### KC
- personality：在 overlay 加一个无代码 bundle（同 DroidVMFramebuffer.json 的做法），给 `AppleVirtualPlatformPCIE` 一个 `IOProviderClass IOPlatformDevice` 的 personality（`CFBundleIdentifier com.apple.driver.AppleVirtualPlatform`）。它的 `start` 对 provider 只用到 `mapDeviceMemoryWithIndex` 和 `getProperty`，IOPlatformDevice 就能满足，ArmDTPlatform 和 ARMPlatformStandIn 都不用改。
- keep 加 `com.apple.driver.AppleVirtualPlatform`、`com.apple.driver.AppleVirtIO`。AppleVirtualPlatform 自带的其他 personality 都不会匹配（`arm-io,vmapple1`、`AppleVirtualPlatformARM`、`avp,*`、`ARM,pl031`、`ARM,psci`、`port-virtual-1`、`ARM,pl061`+role，我们的 ADT 都没有），但匹配 `IOPCIDevice` / `AppleVirtIOTransport` 的那些（PowerSource、Identity、Provisioning、HIDBridge 的 transport）会在对应设备 ID 上和 AppleVirtIO 抢，要在 P2 看匹配结果。
- 依赖闭包按 P0 的结论处理：
  - 能顶替的：在 ARMPlatformStandIn 补 `AppleARMIO`、`AppleARMPE` 两个类（元类和 vtable 符号要真实存在，因为 AppleVirtualPlatformIO/ARMPE 的静态构造会引用父类元类；成员函数做空实现，这两个子类永远不会被实例化）；IOUSBDeviceFamily、AppleCallbackPowerSource 同样处理。
  - 顶替不了的：走止损方案（见后）。

### DroidVMInput
- 桥接管 `/arm-io/pcie` 之后，DroidVMInput 的 `IONameMatch pci-host-ecam-generic` 就匹配不到了。把它改挂到 IOPCIDevice 上：`IOPCIMatch 0x10521af4`（virtio-input），probe 分数高于 AppleVirtIOPCITransport。改用 `IOPCIDevice` 的 BAR 映射，MSI-X 先不用，保持现有轮询；要保住 Apple MT 触屏协议。
- 也可以先在 `MACOS_PCIE=1` 下不带 DroidVMInput 做 bring-up（用 AppleVirtIOInput 的键盘/鼠标/触控板），P3 再迁移。

## 阶段

### P0 验证（不上机，先逆向/离线推演，见 feedback-fewer-smoke-tests）

**11-11 结果：依赖闭包可行。**
- 离线试建 KC：多保留 10 个 kext，即 AppleVirtualPlatform、AppleVirtIO、AppleVirtIOStorage、IOPCIFamily、IOAccessoryManager、AppleOnboardSerial、IOSerialFamily、IOUSBDeviceFamily、usb.AppleUSBCommon、AppleCallbackPowerSource。**没有**带进 AppleSMC、RTBuddy、AppleA7IOP。
- 顶替缺 51 个符号，全是 AppleARMPlatform 的：AppleARMIO、AppleARMPE 两个类，以及 11 个 `gAppleARMUSBCable*` OSSymbol。已补进 `overlay/kext/ARMPlatformStandIn.cpp`，KC 建成，重绑了 70 个指针、0 个 branch，产物在 `out/k27/pcie-p0/`。
- 新 kext 的 personality 都匹配不到我们的 ADT：IOAccessoryManager 的 `IOPort Auto Match` 要求节点名是 `port`，ApplePSCI 要求 `ARM,psci`，我们的是 `arm,psci-1.0`。

待办：
- 离线用 `k27/kc-build27.py ... --keep <现有> com.apple.driver.AppleVirtualPlatform com.apple.driver.AppleVirtIO` 试建 KC：
  - 记录新增的 kext 列表和顶替缺失的符号；
  - 判断闭包是否带进 IOAccessoryManager / AppleSMC / RTBuddy。
- IDA 看 KC 里 IOPCIFamily：
  - `IOPCIHostBridge::start` / IOPCIConfigurator 对 `ranges` 的使用、是否重分配 BAR、是否需要 `bus-range`；
  - `resolvePCIInterrupt` 第二个参数的含义；
  - MSI-X 分配的流程：`allocateInterruptVectors`、`GetMessagedInterruptAddress` 的调用参数。
- IDA 看 AppleVirtIOPCITransport：
  - 中断类型选择（MSI-X / MSI / INTx），每个设备要几个向量；
  - 对 virtio 1.0 现代 capability 布局的要求（crosvm 是现代 virtio-pci）。
- 查清 Windows 读 MADT GIC MSI Frame 的规则，决定 TYPER bit31 是不是要做成开关。
- **止损点 1**：如果闭包要带进 IOAccessoryManager 那一串，或者顶替 AppleARMIO 不够（例如 mod_init 里还调用了 AppleARMPlatform 的函数），就转止损方案。

### P1 crosvm + ADT
- TYPER bit31（或开关）；macOS VM 加 `--mbi-spis 64`（App VM 配置用最小替换，见记忆 macos-k27-virtio-gpu-3d-route）。
- make_adt 在 `MACOS_PCIE=1` 下生成新的 `/arm-io/pcie` 和 `/arm-io/gic-mbi`。离线解析 ADT，核对 ranges 的字节布局。
- Linux guest 回归：`--mbi-spis` + MSI 跑一次 fio，确认 TYPER 改动无影响。

### P2 中断控制器 + 桥起来
- ArmCpu 补丁 + DroidVMGicMsi + 无代码 personality bundle + KC keep。
- 验收：
  - ioreg 里 `AppleVirtualPlatformPCIE` 已注册，下面有 crosvm bus 0 上的各 IOPCIDevice（vendor 0x1af4 的 virtio-input，加上 xHCI 1b36:000d，如果开了）；
  - AppleVirtIOPCITransport 已匹配；
  - `GetMessagedInterruptAddress` 给出 0x7040 / INTID；
  - ArmCpu 的 SPI 计数在增长。

### P3 设备
- 先加一个 virtio-pci 设备来验证完整数据路径：
  - 优先 `--block` 只读的小盘（AppleVirtIOBlockStorageDevice），看中断驱动的读延迟和吞吐；
  - 或者 virtio-console / entropy，最简单。
- DroidVMInput 迁到 IOPCIDevice，恢复触屏。
- 验收：触屏和键盘可用；块设备读写正确；无丢中断（观察 SPI 计数和 crosvm 的 irqfd 计数是否一致，长时间空闲后第一次 I/O 的延迟）。

### P4 收益项（各自单独立项）
- xHCI 直通：xHCI 只有 INTx，需要给 crosvm 加"INTx = 基址 + n"的分配方式，或者在桥上补 `interrupt-base`。
- 把 Data 盘、网卡逐个从自写 virtio-mmio 驱动迁到 virtio-pci + AppleVirtIO，前提是 P3 测出中断路径比轮询好。
- MSI 向量按 CPU 分散路由（现在全部送启动核）。

## 风险

- **依赖闭包**（最大风险）：AppleVirtualPlatform 是整个 vmapple 平台 kext，不是单独的 PCIe kext。
- **Gunyah 投递**：MBI 是边沿 irqfd，经 Gunyah vGIC 注入。Windows 上没有丢中断，但 Windows 的空闲 vCPU 会回到宿主睡眠，macOS 的空闲 vCPU 一直留在虚拟机监控器里 WFI（记忆 gunyah-idle-vcpu-host-accounting），唤醒路径不同，要在 P3 实测空闲后的第一次中断。宿主侧 halt-poll 模块对 macOS 无效（它只作用于回到宿主睡眠的 vCPU）。
- **SPI 预算**：`--mbi-spis` 在创建 VM 时就要定好；向量用完时 `allocateInterruptVectors` 失败，设备回退到无中断。
- **匹配冲突**：AppleVirtualPlatform 里多个 personality 也挂在 `AppleVirtIOTransport` / `IOPCIDevice` 上，可能和 AppleVirtIO 抢同一个设备 ID。
- **ADT 字节序**：ranges 写错时，`addBridgeMemoryRange` 拿到错误的窗口，BAR 分配失败，但不会 panic，要看 IOPCIConfigurator 的日志。

## 止损方案（P0 失败时）

自写 `DroidVMPCIE : IOPCIHostBridge`（IOPCIFamily 开源），**沿用同一份 ADT 契约**（`pcie,vmapple1` 改成自己的名字即可）：
- ECAM 映射 + `ranges` → `addBridgeMemoryRange`；
- MSI 控制器子类化 `IOPCIMessagedInterruptController`，逻辑同上（门铃 +0x40，数据 = INTID）；
- `callPlatformFunction` 响应两个 MSI key。

crosvm、ADT、DroidVMGicMsi、ArmCpu、DroidVMInput 的工作全部复用，只把 KC 里的 AppleVirtualPlatform 换成这一个约 300 行的 kext。

## 不做

- 不给 AppleVirtualPlatform 补 AppleARMPlatform 的真实行为（时钟、电源域、PSD），也不实例化 AppleVirtualPlatformIO/ARMPE。
- 不改 Gunyah 或宿主内核。

## 2026-11-11 接管：BAR 地址转换修复

原先 `ranges` 的父地址用了绝对物理地址，外层 `arm-io/ranges` 又加上 `ARMIO_BASE=0x1000`。
例如 input 的 assigned-addresses 是 `0x2020000`，IODeviceMemory 却是 `0x2021000`；
common config 的状态访问因此落在 BAR+0x1014，MSI-X 表写入落在 PBA 区域。
父地址改为物理地址减 ARMIO_BASE，PCI 地址保持不变。

定向实机验证：同一 KC，仅替换启动盘 ADT 后，AppleVirtIOInput 的四个实例和键盘、鼠标、两个 Trackpad 子驱动成功发布；
AppleVirtIOBlockStorageDevice、IOBlockStorageDriver、IOMediaBSDClient 也成功发布，队列 MSI-X 向量配置及 DRIVER_OK 完成。
这修复了原来的 input/block start 失败；端到端 I/O、中断计数与触屏行为继续分别验证。
采集见 [修正后启动日志](../out/k27/pcie-p1/parent-fix-dmesg.log)。

## 2026-11-11 接管：Block ABI panic 修复与原生 I/O 验证

原生 HID 开始加载后，`com.apple.AppleUserHIDDrivers` 经
`AppleUserHIDEventService::completeCopyEvent → OSAction::SetAbortedHandler → _Block_copy`
触发 data abort。Apple kext 传入带 PAC 的 Block descriptor，而移植编译器生成无签名
descriptor；运行时将签名位当地址使用。XNU 补丁 0048（内核提交 `1168d2b`）
兼容两种格式：读取时认证带签名指针，复制 Block 时按新字段地址重新签名。

内核和 KC 构建通过，部署 `out/k27/pcie-p1/boot-pcie-block-descriptor.img` 后：
- SSH 可用，运行超过 6 分钟，`kernel_debugger_entry_count=0`；
- `hidutil list` 列出 4 个 AppleVirtIOInput 设备；鼠标和两个 Trackpad 的
  AppleUserHIDEventService 已 active，越过原 panic 点；键盘事件服务与实际输入仍待确认；
- 原生 AppleVirtIOBlockStorageDevice 发布 `/dev/disk0`（402.7 MB）；
- 对 `/dev/rdisk0` 做 8 次 512 字节只读读取，4096 字节与启动镜像头逐字节相同；
- 同期 SPI 64 从 18 增至 26（+8），其他已挂接 SPI 计数不变。

这已验证 PCIe → AppleVirtIO → 队列 → MSI → GIC SPI → 完成回调的磁盘读取路径。
本轮未计算文件散列、未跑烟测；尚未验证写入、吞吐、长期空闲唤醒和触屏端到端行为。

## 2026-11-11 原生 PCIe 下恢复 App 输入

AppleVirtIOInput 将 App 的多点触屏发布为 Trackpad/指针，丢失了原 DroidVMInput 的
内建触屏协议；键盘只有 IOHIDInterface，没有事件服务。原 DroidVMInput 又只匹配
旧 ECAM nub，桥启用后不再启动。这是“设备已发布、实际输入无反应”的原因。

保留原生 PCIe 桥及块设备，将 DroidVMInput 增加为 IOPCIDevice 客户端：
- 仅匹配 `0x10521af4`，分数 20000，高于 AppleVirtIOPCITransport 的 10000；
- 用 IOPCIDevice 的配置空间接口与 BAR 映射，每个函数各驱动一个输入设备；
- 保留既有轮询和 Apple multitouch 协议，旧 ECAM 模式仍可用；LocationID 使用 PCI slot，避免各实例重号。

定向验证：四个 DroidVMInput 均 active，键盘/鼠标/tablet 挂 IOHIDEventDriver，
触屏挂内建 AppleMultitouchDevice，保留 displayUUID/HSTouchHIDService；通过 App 键盘
完成 droid 控制台登录，键盘服务 EnqueueEventCount=12，事件类型 3。
部署镜像 `out/k27/pcie-p1/boot-pcie-droidvm-input.img`。

构建输入 kext（各 include 路径需绝对路径，因为编译器在内核对象目录运行）：
```sh
python3 scripts/build-native-kext.py DroidVMInput overlay/kext/DroidVMInput/DroidVMInput.cpp overlay/kext/NativeKextGlue.cpp --obj k27-obj -I "$PWD/out/x12377/inc-hid" -I "$PWD/overlay/droidvm/drivers/NativeVirtioInputPci" -I "$PWD/toolchains/sdks/MacOSX26.1.sdk/System/Library/Frameworks/Kernel.framework/Headers"
MACOS_PCIE=1 MACOS_DISPLAY=1 MACOS_GPU=1 MACOS_VIDEO=1 MACOS_AUDIO=1 K27_NO_BOOT=1 bash k27/try.sh 0
```

CPU 采样同时确认登录前 audiomxd 位于 BTAudioRoutingRequest::_ensureXPCStarted，
循环查询 SCDynamicStoreCopyConsoleUser，连带 configd 高占用（既有问题见 k27-audio.md）。
登录后两者高占用消失；仍持续占用一核的 rpcsvchost 另行定位，不能视为本轮已解决。

## 2026-11-11 高 CPU 定向定位

输入恢复、完成登录后，audiomxd/configd 高占用消失。另有
`rpcsvchost -launchd netlogon.bundle` 持续占约一核，采样落在
DCERPC `timer_loop → dcethread_cond_timedwait → _pthread_cond_wait → __gettimeofday`。
该进程启动时间为 1970 年，校时后重启同一服务，CPU 从约 99% 降为 0%，
累计 CPU 时间随后维持 0.08 秒。未禁用服务，也未修改 RPC 二进制。

PL030 RTC 补齐方案：
- ADT 从 FDT `arm,primecell-periphid=0x41030` 生成 rtc 节点；父地址 0x1000，实际物理地址 0x2000；
- ArmDTPlatform 在发布设备时解析 RTC 资源并映射，getGMTTimeOfDay 读取 PL030 RTCDR；
- `k27/build-platform-rtc.sh` 从未改动的上游源生成带补丁副本，独立重建平台 archive，
  `build-kernel27.sh` 自动调用；不会重编或覆盖已打 SPI 补丁的 ArmCpu archive。

目的：让 clock_initialize_calendar 在启动时即得到当前时间，避免用户态校时前建立
1970 年的绝对等待截止时间。部署镜像 `out/k27/pcie-p1/boot-pcie-input-rtc.img`。

RTC 定向上机结果：clock_initialize_calendar 不再报 UTC=0；launchd 从
2026-11-11 06:17:48（guest 本地时区）启动，configd 与 netlogon 也从当前时间启动，
netlogon CPU=0%。四个输入服务保持正确挂接。早期 6×8 核采样 95.8% idle，
该数值仅代表采样当时，后续登录前 audiomxd 的独立问题仍需观察。

## 2026-11-11 P3 磁盘写入、吞吐与空闲唤醒定向验证

在原 VM 上临时追加独立的 512 MiB `--block` 稀疏文件，不修改启动镜像、Data seed 或 Data 盘。
AppleVirtIOBlockStorageDevice 将测试盘发布为 disk0（启动盘变为 disk1），测试程序用容量检查限定目标；
直接访问 `/dev/rdisk0`，同步 pread/pwrite，QD=1。该轮没有计算文件散列或执行烟测。

| 项目 | 本次结果 |
| --- | --- |
| 1 MiB 顺序写，256 MiB | 1023.56 MiB/s |
| 1 MiB 顺序读，256 MiB | 1770.45 MiB/s |
| 4 KiB 随机写，2048 次 | 8590.50 IOPS，33.56 MiB/s |
| 4 KiB 随机读，2048 次 | 9346.82 IOPS，36.51 MiB/s |
| 顺序/随机数据校验 | 按绝对偏移生成数据，逐字节比较全部 256 MiB 和 2048 个随机块，通过 |
| 测试盘无 I/O 300.005 秒后首次 4 KiB 读 | 2.558 ms，内容正确 |
| 随后首次 4 KiB 写 | 0.734 ms，回读正确 |

空闲期多次读取 SPI 计数，测试盘 SPI 97 始终为 6679；唤醒后为 6687（+8），
对应 IOBlockStorageDriver 的 Operations (Read) 4374→4381、Operations (Write) 2304→2305，
包括窗口内系统额外读取。启动盘 SPI 64 一直为 18。读写 Errors/ Retries 均为 0，
`kernel_debugger_entry_count=0`。未直接采集宿主 irqfd 次数，不能据此声称完成 irqfd 与 SPI 的独立计数核对。

停止测试 VM 后，将宿主的完整测试镜像拉回，再按同一偏移模式逐字节核对：
前 256 MiB、2048 个随机块以及空闲唤醒后的写入块全部通过，确认数据到达后端文件。
随后移除测试盘配置并恢复原 VM 配置、启动 VM，测试镜像留在采集目录供复核。

范围：单次虚拟盘路径测量，宿主文件缓存开启，以上不是闪存裸盘吞吐。
raw-device fsync 返回成功不等于完成物理介质持久化保证，本次未验证掉电耐久性。
空闲采样为 67.7% CPU idle；audiomxd/configd 仍有负载，故此项是测试盘空闲 5 分钟后的
MSI 完成路径验证，不是整机休眠恢复或数小时空闲压力测试。

原始记录与复现程序：[采集目录](../research/pcie-io-2026-11-11/)，
[测试程序](../research/pcie-io-2026-11-11/disk-io.c)、
[吞吐与校验](../research/pcie-io-2026-11-11/bulk.log)、
[空闲唤醒](../research/pcie-io-2026-11-11/idle.log)、
[宿主文件校验](../research/pcie-io-2026-11-11/backing-verify.log)。
后端镜像副本：`out/k27/pcie-p1/pcie-io-test-after.img`。

## 2026-11-11 P4：网卡迁到 AppleVirtIONetwork

增加 `MACOS_NET_PCI=1`（同时启用 `MACOS_PCIE=1`）：App VM 保留原 br-wifi 网络和
MAC `02:44:56:4d:00:01`，去掉 `--virtio-mmio-net`，让 crosvm 将同一网卡放到 PCI。
ADT 不再生成 `/arm-io/net`，按新 FDT 移动后续 GPU、声卡、media 的 MMIO 地址。
KC 不再包含 DroidVMEthernet 占位驱动及其 TimeSync 资源依赖，避免先占用 en0；
AppleVirtIO 中已有的 AppleVirtIONetwork 直接挂接，无需修改苹果驱动或 crosvm。

构建使用 `MACOS_PCIE=1 MACOS_NET_PCI=1 MACOS_DISPLAY=1 MACOS_GPU=1 MACOS_VIDEO=1 MACOS_AUDIO=1 K27_NO_BOOT=1 bash k27/try.sh 0`。
修改已停机 VM 的网络用同样的 `MACOS_NET_PCI=1` 调用 `scripts/droidvm-app.py net`，
它会重新采集 FDT；随后必须更新启动盘中的 ADT 和 KC 再启动。
本次复制已验证的 `boot-pcie-input-rtc.img`，仅用 mcopy 替换 KC/ADT，未重新生成 Data seed。
当前部署镜像为 `out/k27/pcie-p1/boot-pcie-net.img`。

定向上机结果：
- AppleVirtIONetwork active，DroidVMEthernet 实例不存在；en0 的 MAC 不变，DHCP 仍为 192.168.1.196，SSH 恢复。
- TimeSyncRootService 和 TimeSyncClockManager 正常启动；PCI 网卡协商 RXCSUM/TXCSUM/TSO4。
- 同一 Linux 主机（192.168.1.184）、同一程序双向各传 64 MiB，两个方向均逐字节校验通过。
- MMIO 基线上传/下载 21.30/25.73 MiB/s；PCI 首次 13.60/42.51 MiB/s，因上传偏低复测为 20.80/38.38 MiB/s。
  此为经手机 Wi-Fi 桥的单次对比，存在启动负载和无线波动，不代表驱动最大吞吐或稳定收益。
- ping 网关 10/10 成功；网卡 Ierrs/Oerrs/Drop 均为 0；复测 TCP 输出未报告重传或校验错误。
- 第一次传输及 ping 窗口内，SPI 84 为 193→2122、SPI 85 为 156→1917；磁盘 SPI 64 保持 18，
  `kernel_debugger_entry_count=0`，收发完成走 MSI。

回退保留 `boot-pcie-input-rtc.img` 和原 VM 配置 `/tmp/codex-pcie-net-vm-original.json`。
停机后恢复原配置与旧启动镜像即可；后续构建不设置 `MACOS_NET_PCI` 时仍使用旧 MMIO 路径。
Data 盘、xHCI 和 MSI 多 CPU 路由尚未迁移。

采集与定向验证程序见 [pcie-net-2026-11-11](../research/pcie-net-2026-11-11/)，
包括 MMIO 基线、PCI 两次传输、接口信息和 SPI 前后计数。

## 2026-11-12 P4：System/Data 容器迁到原生 PCIe 块设备

现有启动盘的 scratch-data.img 是 32 字节 DBRDISK1：48 GiB 逻辑容量、0 个数据区段。
System/Data 的有效内容全部位于 SHNGDATA store，不能把带标签/位图的 store 直接作为 APFS 磁盘。
在 guest 正常卸载 APFS、报告 CPU halted、VM 停止后，转换为独立的 `data-pcie.img`：
- 保留原 `data-store.img`，不原地修改、不重新生成 seed；新盘复制所有位图标记的页面，空页保持稀疏。
- 添加真实 GPT，APFS 容器位于 1 MiB 起的 Apple_APFS_ISC 分区中，保留所有 APFS 容器/卷 UUID。
- 实际复制 30,166,941,696 字节，输出 fsync 后再读源文件与新盘，逐字节核对全部有效页面，通过。
- 手机侧执行静态 aarch64 转换工具，避免把约 28 GiB 的副本先拉到 Linux；GPT 的 CRC32 是格式必需字段，未计算文件 SHA。

`MACOS_DATA_PCI=1` 控制 App 磁盘配置、ADT 和 KC：
- `disk_options()` 使用 `--block data-pcie.img,lock=false`；`disks` 支持在新旧路径间切换，并重新采集 FDT。
- ADT 不再发布 `/arm-io/data-store`，不将持久磁盘标为 ephemeral；GPU/音频/media 的 MMIO 地址跟随 FDT。
  第一 MMIO 窗口不再保留给 Data store，修正 last_virtio_mmio 对它的旧限制。
- KC 不再加载 NativeVirtioBlock/NativeRamBlock，System/Data 均直接走 AppleVirtIOBlockStorageDevice、IOGUIDPartitionScheme、APFS。
- 诊断工具 rig-dmesg 原先只按 `virtio-mmio-block` 找进程，现也能识别纯 PCI 存储的 macOS VM。

ISC 容器仍需要原有的可见性修正：APFS 在 probe/reconcile 时设置 OSInternal，导致 diskutil/DiskManagement 隐藏整个主容器。
旧实现依附于 NativeRamBlock 的发布线程；改为 DroidVMAPFSVisibility，在独立匹配类别中附着 PCIe 盘下的
AppleAPFSMedia，移除该属性，并每 2 秒处理 APFS 重新设置属性的情况。它不接管 I/O，也不修改卷属性或磁盘内容。
最终上机 `diskutil list` 已正常显示 System/Data/Preboot/VM/Hardware/xART，TimeSync、PCI 网卡和 SSH 正常。

定向验证：
- 从新 GPT 盘启动，System UUID 仍为 354D4F10-9A79-4243-BA00-60FAB89D7561；System 只读，Data 和辅助卷正常挂载。
- 在 `/Users/droid` 创建 64 MiB 偏移模式文件，F_NOCACHE 写入，fsync 和 F_FULLFSYNC 均成功，逐字节回读通过。
- 首次正常关机：APFS 卸载完成，CPU halted；重启后 64 MiB 文件全部校验通过。
- 此后可见性修正重启，文件再次逐字节校验通过；磁盘读写 Errors/ Retries 为 0。
- PCI 系统盘使用 SPI 97；数据写入后计数 112681，运行期间 kernel_debugger_entry_count=0。
  磁盘编号会随枚举顺序变化，不能固定按 disk0 判断根盘。

额外关机复核暴露了尚未解决的既有 stackshot 问题：关机启动 spindump，
`stackshot_trap → kern_stack_snapshot_internal → DebuggerXCallEnter` 等待 CPU 响应超时而 panic。
已用运行时 panic-spin 保留现场，panic 中进程为 spindump，符号化栈不含存储路径。
该现象在引入可见性 kext 之前和之后均出现；首次干净关机后的文件持久化已验证，
不能把这些结果表述为“每次关机都正常”或宣称关机 panic 已修复。
异常停止后再次启动，原 64 MiB 文件仍逐字节校验通过（post-panic-verify.log），
最终运行时 debugger entry count 为 0；验证文件随后删除，VM 保持运行。

构建：
```sh
python3 scripts/build-native-kext.py DroidVMAPFSVisibility overlay/kext/DroidVMAPFSVisibility.cpp overlay/kext/NativeKextGlue.cpp --obj k27-obj
MACOS_PCIE=1 MACOS_NET_PCI=1 MACOS_DATA_PCI=1 MACOS_DISPLAY=1 MACOS_GPU=1 MACOS_VIDEO=1 MACOS_AUDIO=1 K27_NO_BOOT=1 bash k27/try.sh 0
```
转换源码、GPT 包装生成器和持久化验证程序见 [采集目录](../research/pcie-data-2026-11-11/)。
转换器只适用于已经确认没有 seed 数据区段的旧 store，源必须停机；先从当前启动盘提取原 seed，
用 prepare-gpt.py 检查其头部并生成 prefix/suffix，再用静态编译的 store-to-raw 将旧 store 转为新文件。
当前启动镜像：`out/k27/pcie-p1/boot-pcie-data.img`，保留旧 `boot-pcie-net.img` 和
`/tmp/codex-pcie-data-vm-original.json`。回退需要同时恢复旧 VM 配置和启动盘；旧 store 是切换前快照，
不会包含切换后在新 PCI 盘上的更改，两盘不能同时挂载相同 UUID 的容器。

## 2026-11-12：stackshot 的 debugger IPI 响应预算

普通运行执行 `sudo spindump <WindowServer PID> 10 1 -file /tmp/p4-stackshot.txt`，
复现同一 `DebuggerXCallEnter` panic（本次 CPU 6 等 CPU 5），不依赖关机或存储卸载。
保留的中断栈表明辅助 CPU 已进入 `DebuggerXCall/stackshot_aux_cpu_entry`；
panic 后采集不能还原超时瞬间的全部状态，不能单凭这些栈判定 IPI 丢失。

运行时读回 `debug_ack_timeout=240000`，在 24 MHz guest 时基下只有 10 ms。
源码中的 24,000,000 ticks 兜底仅在该变量为零时使用，默认值非零，实际不会走 1 秒兜底。
宿主 `/proc/<pid>/task/<vcpu>/sched` 的 `wait_max`（毫秒）为 13.21–36.35 ms（多颗 CPU），
确认正常宿主调度等待本身即可超过该预算。

App 默认启动参数加入 XNU 已有的 `ml-timeout-debug-ack-scale=100`，只调整 debugger 跨 CPU
进入/退出的响应预算到 1 秒；保留超时 panic、spindump、stackshot 和全部 CPU 参与。
不改内核代码，不改全局 timeout scale。启动后读回 24,000,000 ticks。

定向验证：
- 同一 10 秒、1 ms 请求间隔的 spindump 命令完成并生成报告；工具因处理速度主动降低采样频率。
- 完成后 debugger entry count 回到 0，未 panic。
- 随后正常关机，`vfs_unmountall(system) end`、APFS mounted volumes=0、`CPU halted`，无 panic。
- 这是已复现路径的修正验证，不代表长期压力验证或对所有关机问题的保证。

证据：[复现 panic](../research/pcie-data-2026-11-11/stackshot-repro-panic.txt)、
[中断栈扫描](../research/pcie-data-2026-11-11/stackshot-repro-stacks.txt)、
[宿主调度等待](../research/pcie-data-2026-11-11/stackshot-host-scheduling.log)、
[采样完成](../research/pcie-data-2026-11-11/stackshot-fixed.log)、
[正常关机](../research/pcie-data-2026-11-11/stackshot-fixed-shutdown.log)。
