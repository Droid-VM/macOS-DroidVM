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
