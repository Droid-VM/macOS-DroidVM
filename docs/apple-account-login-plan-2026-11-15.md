# DroidVM macOS Apple Account 登录计划

更新：2026-11-16 00:03（Asia/Shanghai）。用户已通过 Apple 官方网页注册账户，当前 ARM macOS guest 的“系统设置”已有账户登录仍报“未知错误”。目标是定位并修复本地 ADI 预配失败，完成登录，再验证正常重启后保留账户。系统设置内“没有账户”的注册初始化错误仍单独定位；网页注册成功不代表 guest 登录或 iCloud 已可用。iCloud 同步、App Store、iMessage/FaceTime 分开验收，不以验证码弹窗代替登录成功。

## 执行约束

- 先采集当前 guest，区分源码默认值、旧日志与本次运行结果。
- 保留当前桌面/图形路径，不全局关闭 `kern.hv_vmm_present`，不全局删除 MobileGestalt 缓存。
- 不重建 Data 种子，不清空钥匙串或账户数据库，不复制真实设备的证书/私钥。
- 改启动盘或存储前备份对应产物，确认正常关机；每次只改一个变量并保留回退路径。
- 密码和双重认证由用户在 guest 界面输入，诊断工具不收集密码或令牌。原始输出保存在仅本机可读的采集目录。
- 仓库已有未提交改动；仅修改本任务明确涉及的内容。确认一个故障修复后立即按修复分组提交，只做相关定向验证；全部已知问题修复后再跑全量测试。禁止 `cargo check`。

## 阶段与验收

| 阶段 | 状态 | 工作 | 验收与决策 |
| --- | --- | --- | --- |
| P0 当前基线 | 完成 | 记录系统/时钟、桌面会话、身份字段、网络、钥匙串元数据、launchd 禁用状态、当前内核参数和 NVRAM 线索 | 已形成采集脚本与原始报告，没有向 Apple 提交账户凭据 |
| P1 认证基础 | 基础检查完成，保留未验证项 | 对实际故障验证钥匙串测试项、账户服务/XPC、DNS/TLS；必要时在临时钥匙串中测试写入/读回/删除 | DNS/TLS、隔离的传统钥匙串、Aqua 桌面域与账户服务已验证；现代数据保护钥匙串未验证 |
| P2 注册与登录失败定位 | 进行中，失败链已确认 | 已采集注册初始化和已有账户登录各一次有界日志；继续定位 ADI 预配末尾失败 | 注册为 -43004 → UI 111；已有账户登录为 -43004 → -8004/-8001 → -7018；根因尚未闭环 |
| P3 最小兼容实验 | 待开始 | 先核对 AVP 宿主身份依赖与 ADI 持久化；仅有调用证据后才考虑定向 `vmm-hidden` 等实验 | 保留 WindowServer 的 VM 行为；一个变量一个对照；不凭 AVP 日志就隐藏 VM 或伪造证明 |
| P4 身份与保存 | 待开始 | 如证据要求，实现每 VM 稳定身份、所需 NVRAM 保存和凭据持久化 | 重启前后身份不变、测试项可恢复、账户不循环认证；不将本地校验跳过当作服务端证明 |
| P5 账户与服务验收 | 待开始 | 系统设置确认账户、正常重启后复查，再分别测试 iCloud、商店、消息服务 | 逐项记录成功/失败；若服务端要求当前平台无法提供的有效设备证明，给出确切错误与边界，不宣称登录已实现 |

P1/P2 优先于大规模 NVRAM 或身份重构；仅在实际登录依赖关系明确后扩大改动。若有基础设施故障可以独立修复，则先修复并提交，再回到登录路径。

## 已知线索（尚不代表本次运行的根因）

- [内核禁用 mobileactivationd](../patches/xnu-12377/0033-k27-deny-exec-exec-of-the-listed-paths-fails-with-EP.patch)：此前 OIC/UIK/UCRT 校验崩溃。
- [按进程隐藏 VMM](../patches/xnu-12377/vmm-hidden-processes.patch)：默认 Weather，名单外仍返回实际状态。
- [ADT 的空白易失 NVRAM](../sources/UniXNU-droidvm/scripts/make-droidvm-adt.py)：`empty_nvram_proxy()` 无控制器；[旧日志](../research/msi-affinity-2026-11-12/final-shutdown.log) 记录同步失败。
- [App 启动脚本](../scripts/droidvm-app.py) 使用固定 ECID/MAC；实际 guest 的字段须单独采集。
- 历史参数禁用过 identityservicesd、apsd；不能据此断言基本账户登录依赖这两个服务。
- [NativeKeyStoreEvents](../sources/UniXNU/drivers/NativeKeyStoreEvents/NativeKeyStoreEvents.cpp) 是有限状态兼容服务；需验证实际钥匙串操作，不以解锁状态查询成功代替密钥保存成功。

## 本次采集

目录：[research/apple-account-2026-11-15](../research/apple-account-2026-11-15/)。

2026-11-15 初始连通性：当前 guest 为 macOS 27.2 / 26B8125，SSH 可达，`kern.hv_vmm_present=1`，控制台所有者为 root（尚无 droid 桌面会话）。这与先前基于 27.0.1 的历史分析不同，后续结论以本次采集为准。

### P0/P1 已执行结果

- [实时基线](../research/apple-account-2026-11-15/baseline-2221.json)、[补充基线](../research/apple-account-2026-11-15/baseline-refined.json)，[采集脚本](../research/apple-account-2026-11-15/collect-baseline.py)。原始文件权限 0600，目录 0700。
- 系统：macOS 27.2 / 26B8125；`hw.model=VirtualMac2,1`；平台 UUID 已存在，`IOPlatformSerialNumber` 未在根平台对象发布。
- `en0` 已联网且实时确认 `IOBuiltin=Yes`，这两项无需按黑苹果教程重复修复。appleid.apple.com、idmsa.apple.com、setup.icloud.com 的 HTTPS/TLS 校验均通过。根路径分别返回 403/200/404，仅证明 DNS/TCP/TLS 可达，不代表账户认证成功。
- 当前内核参数仍禁用 identityservicesd，并带 `sheng-aks=1 sheng-aks-sls=3`；系统 launchd 明确禁用 apsd、AppSSODaemon、fairplayd。未主动恢复服务。
- system/com.apple.akd 已注册、尚无启动记录（按需服务，不计为故障）。mobileactivationd 为 spawn scheduled，累计 runs=160，last exit=78；需围绕实际请求定位，不把它直接定为登录根因。
- login.keychain-db 存在。登录窗口状态下 `security show-keychain-info` 返回 User interaction is not allowed，不能据此判定钥匙串损坏。gui/501 尚不可用。
- [临时传统钥匙串测试](../research/apple-account-2026-11-15/keychain-isolated-2223.json)，[测试脚本](../research/apple-account-2026-11-15/probe-keychain.py)：创建、解锁、写入、读回比较、锁定/再次解锁/读回、删除均通过；临时钥匙串已删除，用户搜索列表及默认钥匙串已恢复并再次比对一致。
- 这个结果仅覆盖传统文件钥匙串，未覆盖 Data Protection keychain、Apple Account 令牌、iCloud、重启持久化；目前没有账户登录成功结论。

### 桌面与注册复现（22:27–22:31）

- 用户已进入 droid 桌面并打开 Apple 账户登录页。[桌面基线](../research/apple-account-2026-11-15/desktop-baseline.json) 确认控制台用户 droid/501，`gui/501` 为 Aqua，会话 asid=100001。
- GUI 域的 `akd`、`accountsd`、`appleaccountd`、`amsaccountsd`、`identityservicesd` 均在运行。修正初始参数推断：**启动参数列出禁用 identityservicesd，不等于 GUI 的该服务没有运行**。
- SSH 中查询 login.keychain 设置仍返回 User interaction is not allowed；SSH 与桌面安全会话不同，不能据此判定钥匙串损坏。
- [有界日志](../research/apple-account-2026-11-15/login-attempt-2227.log)、[元数据](../research/apple-account-2026-11-15/login-attempt-2227.meta.json)、[采集器](../research/apple-account-2026-11-15/capture-login.py)：240 秒采集正常结束，没有开启 private logging。guest 日志显示的 `06:28:28–06:28:33` 是其本地日志时间，不是开发机的 Asia/Shanghai 时间。
- 用户实际点击“没有账户”，AuthKit 记录 `CreateNewAppleID`。`ADIProvisioningStart` 成功；若干次 finish 请求 HTTP 200 后，`ADIProvisioningEnd` 返回 `-43004`，上层转为 `AKAnisetteError -8004`。整个采集内该 -43004 出现 7 次，包含点击前后的后台重试；不能把所有重试都算作手工尝试。
- 后续 `NACInit failed with status: -44006`，最终 `NSXMLParserErrorDomain Code=111`、`New Apple ID flow failed!`，界面显示未知错误。HTTP 200 不证明响应内容有效或本地预配成功；尚未确定 -43004 的内部含义。
- 少量 HTTP 503 与 property-list 解析失败也出现过，和上述稳定的 HTTP 200 后 -43004 分开记录。
- IDS 后台另有 P-256/SEP 密钥创建失败（OSStatus -26275、CryptoTokenKit -3、AKSError -536870212），尚无证据把它与这次注册初始化失败认定为同一根因。

### 离线二进制核对（22:33–22:38）

- 从原始只读 SystemOS 缓存提取 AppleVirtualPlatform、AuthKit、AppleIDAuthSupport；从原始只读 OS 提取 `CoreADI.framework/Versions/A/adid`，在 IDA 分析，未修改 guest 文件或任何认证返回值。
- 原始 launchd plist 指定 adid 路径为 `/System/Library/PrivateFrameworks/CoreADI.framework/adid`，运行用户/组 `_fpsd`；后续采集须检查实际路径，不能沿用 `/usr/libexec/adid` 的假设。
- AppleVirtualPlatform 的 `_AppleVirtualPlatformGuestHasHostKey`（`0x2620a31b8`）先检查缓存的 `kern.hv_vmm_present`，再匹配 `AppleVirtualPlatformARMPE`，并读取 `UDID` 属性；匹配不到平台服务的错误分支记录源码行 215。见 [IDA 读回](../research/apple-account-2026-11-15/re/avp-line215.json)。
- 同库另有消息长度溢出的行 215，正常记录长度的请求不应触发该分支。因此当前大量成对的行 215 **倾向于**找不到平台服务，但 private-redacted 日志本身不能唯一证明具体分支，仍须恢复连接后用 ioreg/调用结果确认。
- `_AppleVirtualPlatformGuestCopyStrongIdentityData` 还依赖 VM 模式及对应 IdentityService；隐藏 VM 只会更换调用路径，不会生成有效宿主密钥或证书。相关 [初步反编译](../research/apple-account-2026-11-15/re/avp-initial.txt)、[服务检查](../research/apple-account-2026-11-15/re/avp-service.json)。
- AuthKit 的 NAC 初始化封装返回 -44006，但内部实现混淆，当前静态分析不足以给该码命名。见 [NAC 调用](../research/apple-account-2026-11-15/re/authkit-nac.json)。
- 两个研究用途的原始镜像只读挂载（loop23/loop24）已卸载；没有挂载或修改运行中的 guest Data。

### 当前动作与最新状态（22:40）

1. 用户在手机浏览器访问 `account.apple.com`，选择“创建你的 Apple 账户”，自行验证邮箱和手机号。来源：Apple 官方《如何创建新的 Apple 账户》，`https://support.apple.com/zh-cn/108647`（2026-11-15 通过 Tavily 搜索和正文提取核对）。不在聊天中收集密码、验证码、账户令牌。
2. 22:33 左右 guest `192.168.1.196:22` 暂时 No route to host，手机 ADB offline；22:38 执行一次 `adb connect 192.168.1.203:33445` 成功，SSH 同时恢复。App 状态仍为 RUNNING；没有重启 guest 或改网络配置。
3. [恢复连接后的检查](../research/apple-account-2026-11-15/provisioning-baseline-2239.json) 确认 adid 运行于 `_fpsd`，PID=1823、runs=1、never exited，launchd Mach endpoint active。IORegistry 中 AppleVirtualPlatformARMPE、IdentityService、ProvisioningService、AppleKeyStore、AppleSEPManager 均未找到实例。
4. [ADI 文件系统元数据](../research/apple-account-2026-11-15/adi-filesystem-2240.json) 确认 `/private/var/db/fpsd/adi/adi.pb` 与锁文件已存在，当前大小均为 0；目录/文件归 `_fpsd`，目录 0777、文件 0666。`_fpsd` 对其 home 和 Library 的 `test -w` 通过，但没有实际写入测试，也没有读取预配文件内容。空文件与未完成预配相符，尚不足以判定文件写入是失败源头。
5. 补采的 adid 日志只有 `A6: <private>`、`A7: 2`、`A4/A5: 4294922244`（按有符号 32 位为 -45052）及 `4294922240`（-45056）等混淆标签，不能未经调用证据就把数字 2 命名为 errno。一次 10 秒 fs_usage 正常结束，但没有取得能解释本次错误的 adid 文件调用。
6. [日志采集器](../research/apple-account-2026-11-15/capture-login.py) 已补入 `adid` 进程，下一次登录采集会同时覆盖预配守护进程；未开启 private logging。后续优先通过一次有界调用跟踪区分响应验证失败和状态落盘失败。
7. 23:03 用户确认官方网页注册成功。已复查 guest 连通、控制台仍为 droid/501，System Settings、akd、adid 均在运行；开始围绕一次已有账户登录采集 300 秒日志（account-signin-2303.log），凭据与验证码由用户自行在 guest 输入。注册 UI 的结果不能代替已有账户路径验证。
8. 本轮没有实现或验证修复，没有生产代码提交。P3–P5 尚未完成；账户已注册，但 guest 登录仍失败，具体结果见下文。

### 已有账户登录结果（23:03 起）

- 用户确认官方网页注册成功后，在系统设置尝试已有账户登录，反馈“未知错误”。[300 秒日志](../research/apple-account-2026-11-15/account-signin-2303.log) 及[采集元数据](../research/apple-account-2026-11-15/account-signin-2303.meta.json) 确认采集于 UTC 15:03:21 就绪、15:08:21 正常结束，returncode=0；本次没有 CreateNewAppleID，和注册入口复现区分。
- 本次关键失败链：`ADIProvisioningStart` 成功，finish 请求收到 HTTP 200；`ADIProvisioningEnd -43004` → `AKAnisetteError -8004` → 认证参数生成失败 `-8001` → `AKAuthenticationError -7018`。没有证据表明这是密码校验拒绝；也尚不能证明密码正确或服务器已经接受账户登录。
- 日志内较早还有 -7012，周边信息是旧 UI 请求未传入 username/DSID 的上下文，不能把它覆盖稍后实际提交时的 -7018。已有账户这次没有 NACInit -44006 或注册 UI 的 NSXMLParserErrorDomain 111，不能把上次所有错误都合并到本次。
- 对实际 ARM64e akd（通用 Mach-O 显式提取 subtype 2）核对方法 `_tq_processEndProvisioningResponse:...`：[反编译记录](../research/apple-account-2026-11-15/re/akd-arm64e-end-response.json)。只有 PTM、TK、routing 三项存在且 `setIDMSRoutingInfo` 返回 0，才会调用失败日志对应的 `endProvisioningWithSession:...`。这将范围缩小到后续预配处理，但仍不能区分元数据/会话/密码学验证或持久化问题。
- 早期直接打开通用 akd/adid 时 IDA 默认分析了 x86_64 切片；它们仅保留作辅助记录。后续 ARM 结论使用 `akd.arm64e`、`adid.arm64e` 与带 `arm64e` 的索引/反编译文件，不以 x86_64 地址推断 guest 路径。
- [登录后检查](../research/apple-account-2026-11-15/signin-followup-2306.json)：没有找到 MobileMeAccounts 的第一条 AccountID 标记，adi.pb 仍为 0 字节。该单个 plist 标记只能佐证，不能代替完整账户和服务验收；未读取或记录账户地址、密码、验证码或预配文件内容。

### 隔离文件操作与诊断边界

- [临时探针源码](../research/apple-account-2026-11-15/probe-adi-filesystem.c)、[修正后报告](../research/apple-account-2026-11-15/adi-isolated-filesystem-2312.json)：以实际 `_fpsd` 用户，在其 home 内新建独立临时目录，open/独占创建、flock、fcntl 记录锁、F_GETPATH、ftruncate、共享 mmap、msync、fsync、F_FULLFSYNC、重命名、读回比较和清理均通过。现有 adi.pb/锁文件均未打开或修改。这个结果排除基本文件操作普遍失效，不能证明 ADI 特有文件布局或协议正确。
- 初版探针同时持有 flock 和 fcntl 锁而得到 EAGAIN；已把两个机制分开后再测并通过。[初版结果](../research/apple-account-2026-11-15/adi-isolated-filesystem-2310.json) 不计为 guest 故障或已修复代码问题。
- DTrace 默认加载系统脚本时缺少 uthread_t；禁用默认脚本后，系统明确拒绝 syscall 探针（SIP）。[诊断结果](../research/apple-account-2026-11-15/dtrace-nolibs-2313.json)。没有关闭 SIP 或修改系统 DTrace 脚本。
- [本地状态查询探针](../research/apple-account-2026-11-15/probe-anisette-local.m) 仅调用 `fetchAnisetteDataAndProvisionIfNecessary:NO`，不遍历/输出返回数据或令牌。通过 SSH 启动的客户端返回 NSCocoaErrorDomain 4099，没有得到有效预配状态；[同时采集的文件跟踪](../research/apple-account-2026-11-15/local-anisette-fs-2316.json) 没有取得可用的 adid 文件访问。这是探针服务连接失败，不能当作系统设置内失败的新根因。
- [调用后日志与清理核对](../research/apple-account-2026-11-15/local-query-followup-2317.json) 显示探针确实连接到了现有 akd 的 anisette Mach 服务，但 XPC 随即失败；服务器另有客户端准入检查，见 [ARM64e 调用方检查](../research/apple-account-2026-11-15/re/akd-arm64e-client-gate.json)。不能只凭 4099 认定 GUI/bootstrap 错误，也没有放宽鉴权来使探针通过。两个临时可执行文件均已删除，临时文件测试目录没有遗留。

### 官方平台边界与后续工作

- 核对 Apple 官方《Using iCloud with macOS virtual machines》：受支持的新 VM 身份源于 Apple 芯片 Mac 宿主的 Secure Enclave，并由 Virtualization.framework 管理；该机制不同于仅发布 UUID/序列号。资料说明 macOS 15 起的相关支持条件，但并未解释本次 -43004 的内部含义，因此**不能仅凭此文档就宣布本次根因是缺少 SEP 证明**。
- 来源检索说明：Tavily 搜索找到了官方文章，但正文提取只有导航内容；因此回退到直接读取 Apple 官方 DocC JSON。URL：`https://developer.apple.com/tutorials/data/documentation/virtualization/using-icloud-with-macos-virtual-machines.json`；[正文快照](../research/apple-account-2026-11-15/apple-icloud-vm-doc-2026-11-15.json)，UTC 15:15:57 获取。
- 当前可确认的障碍是本地 ADI 预配未完成；AVP 平台/身份服务未实现是独立已确认的能力缺口，两者的直接因果关系仍未证明。不能靠清空账户、反复改密码、填任意序列号或把错误返回改成成功来声称登录已修好。
- 后续应优先确认独立探针所需的连接配置、会话上下文与正常客户端准入条件，或在真实系统 UI 调用期间获取仅含路径/错误码的被动定向跟踪；不修改服务的鉴权判断来掩盖差异。再定位 ADI 对机器身份、预配状态和接口语义的实际依赖。明确具体缺口后再进入 P3 的单变量兼容实验；当前不再要求用户重复提交密码。
- 系统账户登录、重启保留和各 iCloud/商店服务均未验收通过。本次没有改动生产内核、启动参数、认证文件、钥匙串或 SIP，没有可提交的已验证修复。

### adid 的 lstat/errno 已取得调用证据（23:24–23:43）

- [JSON 日志及调用点](../research/apple-account-2026-11-15/adid-log-callsite-2330.json) 中正在运行的 adid UUID 为 `4D24325F-3529-39B1-BBF8-64BBCF406049`，与 subtype 2 的 ARM64e 切片一致。152 组 A6/A7 中 A7 均为 2。后续核对以该切片为准。
- IDA 解出混淆间接调用表后，确认 `0x100108878` 内 `0x1001088fc` 调用 `_lstat`，失败后 A6 记录同一路径；`0x100108e90` 内 A7 调用 `___error` 并记录 `errno`。A7 的 2 现在可以确认为 `ENOENT`，不再只是猜测。对应的两组 S-box 变换已分别遍历 256 个输入，确认索引结果恒定。见 [errno 算术证明](../research/apple-account-2026-11-15/re/adid-arm64e-a7-errno-proof.json)、[文件调用表解码](../research/apple-account-2026-11-15/re/adid-arm64e-file-decoded-targets.json)。
- 紧接的 `0x10010906c` 再读取 errno，并专门区分 `ENOENT` 分支。因此缺文件可能属于未初始化状态的正常处理；尚未知道路径，也未证明它直接造成 `ADIProvisioningEnd -43004`。不能盲目新建文件或把 lstat 返回值改成成功。
- [AOSKit 本地查询](../research/apple-account-2026-11-15/aos-local-query-2343.json) 仅调用 `retrieveOTPHeadersForDSID:` 获取本地 OTP 状态，不调用预配函数，也不输出返回头内容。adid 先记录 `CNE! Client Process Path: <private>` 并返回 `-45070`，因此没有进入目标文件调用。该探针被客户端准入检查拒绝，不能把它当作系统设置的实际登录失败；临时可执行文件已删除。没有修改服务准入、签名或 entitlement。
- `fs_usage` 未提供可用的 adid 路径；System Events 的只读按钮名称查询超时，也没有因此修改 TCC。避免继续依赖这些无效探针。

### 现有内核诊断开关的有界实验（23:48 起）

- 发现当前内核已有 `sc-trace` 的按进程失败系统调用日志，可记录 syscall 340/lstat64 的路径和错误码。[只读校验](../research/apple-account-2026-11-15/kernel-trace-validation-2350.json) 确认 guest `kern.uuid` 与本地 `out/k27/kernel-k27.macho` 的 LC_UUID 完全一致（`7ABC9B3A-0A81-3734-9826-7B89082776FF`）；IDA 的 `_unix_syscall` 起始 16 字节也与 live memory 完全相同。
- 通过当前 VM UUID 精确定位 crosvm PID、DarwinBoot handoff 和 guest memfd 映射；没有使用旧默认内核或 llvm-nm。只允许写现有 `virt_sc_trace_state/name/all` 三个诊断全局变量，并要求原状态为关闭、空名单、failure-only。
- [诊断脚本](../research/apple-account-2026-11-15/trace-adid-kernel.py) 保存原始 104 字节，配置仅 `adid`、仅失败调用，使用 `finally` 恢复，并在手机上另设有时限的恢复看门狗。仅保存筛选后的 `sc: adid` 记录，不保存任意进程内存或认证内容。原始文件仍为 0600。
- 首次看门狗启动方式等待后台子进程，未到达启用步骤就已终止；未修改诊断状态。修正为独立计时进程并正确处理 `/proc/PID/stat` 中含空格的 comm 后，第二次有界采集开始：[采集状态与结果](../research/apple-account-2026-11-15/kernel-trace-adid-2351.json)。恢复结果以该报告的 `restored` 字段及后续独立校验为准。
- 已重新打开账户页，尚未提交凭据。为触发共用 ADI 初始化，已请用户仅点击一次“没有账户／创建 Apple 账户”，不用填写资料或再次注册。本次对运行内核的修改仅是临时诊断状态；没有修改机器身份、认证逻辑、SIP、账户数据或生产代码。

### 路径取证结果与因果边界（23:51–23:57）

- 用户确认再次点击“没有账户”后仍显示未知错误。[按进程内核日志](../research/apple-account-2026-11-15/kernel-trace-adid-2352.json) 实际采到 129 条唯一记录，其中 syscall 340/lstat64 的 `ENOENT` 共 87 条：`/var/db/.AppleSetupUser` 21 条、`/var/setup/.AppleSetupUser` 21 条、`/var/db/fpsd/adi/adi-gb` 15 条、`/Users/Shared/adi/adi-000001F5.pb` 30 条。`000001F5` 对应十进制 UID 501。[统计](../research/apple-account-2026-11-15/adi-path-trace-summary-2357.json)。本次没有捕获 EACCES/EPERM，也没有捕获失败的 open/mkdir/write；这不代表没有成功的写调用或 IOKit/Mach 错误。
- [独立元数据检查](../research/apple-account-2026-11-15/adi-new-paths-metadata-2353.json) 确认上述文件均不存在，连 `/Users/Shared/adi` 目录也不存在；`/Users/Shared` 为 root:wheel/0777。现有 `/var/db/fpsd/adi/adi.pb` 仍是零字节。只读取 stat 元数据，没有读取预配数据内容，也没有新建这些目录或文件。
- syscall 170/csops 的 ERANGE 另有 42 条。当前源码的 `csops_copy_token` 在调用者先查询 entitlement 长度、缓冲不足时会正常返回 ERANGE 并提供所需长度，故这些记录不能单独认定为签名/准入缺陷；需要和后续成功调用对照。
- [同次 unified log 时间线](../research/apple-account-2026-11-15/adi-timeline-2356.json) 给出关键反证：guest 本地 `2026-11-15 07:51:31.136` 出现 A6/A7=2，随后 `07:51:31.138` 的 `ADIProvisioningStart` 成功；另几个 Start 同样如此。缺文件检查并不会立即阻止 Start，因此不能直接把 ENOENT 当成 End -43004 的根因。时间为 UTC−08:00，对应 Asia/Shanghai `23:51:31`。
- 同次多轮 End 仍返回 -43004，注册初始化还出现 NACInit -44006；这些是共用初始化路径复现，不是用户再次提交已有账户密码。用户只进行了一次手工点击，不能把程序自动重试次数当成多次手工尝试。
- 第一轮 90 秒无事件，报告 `restored=true`；取得 129 条记录的第二轮在取证完成后主动结束，`finally` 已恢复原始 104 字节，报告 `restored=true`。[独立再次校验](../research/apple-account-2026-11-15/kernel-trace-restored-2354.json) 确认诊断状态恢复为关闭/空名单/all=0。
- 随后 45 秒记录成功调用、只切换到 General 再返回账户页的实验没有触发 adid，已恢复，不能当作写入路径通过或失败的证据：[空白对照](../research/apple-account-2026-11-15/kernel-trace-adid-all-2354.json)。因此已准备仅 `akd,adid`、同时含成功/失败调用的 180 秒采集，并请用户再做一次无需凭据的初始化：[下一轮采集](../research/apple-account-2026-11-15/kernel-trace-adi-all-2357.json)。不记录 syscall 数据缓冲区、密码、OTP 或返回头。
- 精确路径及 -43004 的 Tavily 搜索未找到能解释当前 ARM64e 错误的权威映射；补充回退的内置搜索也没有提供有效的官方错误码解释。第三方旧版/其他平台的描述不作为修复依据。

### 成功/失败调用完整采集（2026-11-16 00:00–00:03）

- 前一轮 180 秒窗口已结束并恢复后，用户才在 23:58:37 触发初始化；[当时的补采日志](../research/apple-account-2026-11-15/final-health-2359.json) 确认又一次 Start 成功、End -43004。这是窗口与用户操作错开，不能把 21 条后台成功调用当作覆盖了预配。已向用户明确说明，并把下一轮最长窗口延长到 600 秒；没有隐瞒空白采集。
- [完整采集](../research/apple-account-2026-11-15/kernel-trace-adi-all-2359.json) 在 UTC 15:59:23 启动，记录指定的 `akd,adid` 成功和失败系统调用，用户确认完成一次无需凭据的初始化后主动结束。共捕获 2,975 条可解析调用：adid 800 条，akd 2,175 条；[汇总及覆盖边界](../research/apple-account-2026-11-15/adi-full-trace-summary-0002.json)。
- **真实文件访问已验证：** adid 对 `/var/db/fpsd/adi/adi-gb.lck` 的 16 次 open、对 `/var/db/fpsd/adi/adi.pb` 的 28 次 open 均返回 errno=0；16 次 read 也返回 errno=0。日志不记录 read 的字节数/返回值，不能把它说成读到了有效预配内容。事后 stat 仍确认 adi.pb 为零字节。
- adid 的非零错误仅有 csops/ERANGE 与前述 lstat/ENOENT，没有 EACCES、EPERM、ENOSYS 或 EINVAL。该进程没有记录到 write、rename、mkdir、ftruncate、fsync 等选定持久化调用。[同轮 unified log](../research/apple-account-2026-11-15/adi-final-timeline-0002.json) 在北京时间 11 月 16 日 `00:00:31–00:00:40` 记录六次 Start 成功、六次 End -43004；它们属于同次手工操作的内部重试。guest 日志的日期仍是 11 月 15 日、时区 UTC−08:00，不能和北京时间混淆。
- 这一组合证据支持“尚未观察到通过常规写调用提交新预配状态”，不支持“已有文件打不开或写调用遭权限拒绝”。但 logger 明确跳过 mmap/mprotect/close 等调用，也不跟踪 Mach/IOKit、用户态错误或缓冲区内容，因此不能扩大成“所有持久化机制都已排除”或“响应密码学验证失败已被证明”。
- akd 另有 4 次 unlink/EPERM；相同 a0 地址紧接着成功打开 `Caches/com.apple.akd/fsCachedData_remove`，后续继续遍历，属于缓存目录清理上下文，尚无其导致 ADI End 失败的证据。不能把它混入 adid 的预配文件权限结论，也未为此修改 VFS 权限语义。
- [共享父目录隔离探针](../research/apple-account-2026-11-15/shared-parent-probe-0001.json) 以 `_fpsd` 在 `/Users/Shared` 内创建独立随机临时目录，写入固定测试文本、重命名、读回比较和清理全部通过；没有创建 `/Users/Shared/adi` 或更动任何 ADI 文件。探针继承 SSH 当前目录时出现 getcwd 权限警告，但操作使用绝对路径且 exit=0；这不是 adid 的运行日志，不另列为 guest 故障。
- 采集报告 `restored=true`；[独立 live memory 复查](../research/apple-account-2026-11-15/kernel-final-restored-0002.json) 再次确认原始 104 字节一致，状态关闭、名单为空、all=0。[事后健康检查](../research/apple-account-2026-11-15/adi-final-timeline-0002.json) 确认 droid/501 桌面仍在，adid PID 1823、runs=1、never exited。没有重启 VM 或账户服务。

当前决策：**保持账户及 ADI 文件不变，不伪造空的预配状态。** 本轮已取得实际文件路径与成功打开/读取证据，停止要求用户反复点初始化或提交密码。下一步应围绕 `AKADIProxy endProvisioningWithSession:PTM:PTMLength:TK:TKLength:` 的参数长度、会话生命周期、响应处理和平台身份依赖寻找直接证据；只允许采集长度/状态/错误码，不采集 PTM/TK/密钥内容，不绕过客户端准入。登录仍未修复，没有新增可提交的已验证生产代码修复。

### FairPlayIOKit 线索与上机实验（2026-11-16 00:10–00:40，Claude 接手）

- `adid` 的导入表有 `IOServiceMatching / IOServiceOpen / IOConnectCallStructMethod`，签名权限只有 `AvpFairPlayUserClient.access` 与 `com.apple.private.FairPlayIOKitUserClient.access`。原始 KC 含 `AvpFairPlayDriver`（匹配 virtio 设备 `106b:1a08`，有 `sendADIMessage`，把运算转给宿主 Mac）和 `FairPlayIOKit`（挂 IOResources，只依赖 kpi，用 IOAESAccelerator 的 UID/GID 密钥，经 host special port 17 调 `fairplayd`）。此前 `configs/kc-keep.txt` 两个都没留，`fairplayd` 也因此被禁用。
- 不重启对照：把运行内核的 vmm-hidden 名单改成 `Weather,adid`（[vmm-hidden-live.py](../research/apple-account-2026-11-15/vmm-hidden-live.py)）并重启 `adid`，结果不变（Start 成功、End -43004）。只隐藏虚拟机标志无效。
- 上机：`configs/kc-keep.txt` 加 `com.apple.driver.FairPlayIOKit`，按原开关重建 KC（旧 KC 与手机上的逐字节一致，备份 `out/k27/kc-k27.before-fairplay.bin`），只替换启动盘里的 `kernel.macho`；手机上原盘为 `boot.img.before-fairplay`。启动正常、无 panic，驱动 registered/matched。
- 结果：`adid`（pid 730）和 `fairplaydeviceidentityd` 都打开了 `com_apple_driver_FairPlayIOKitUserClient`（`kern.hv_vmm_present=1` 下也一样），证实 ADI 走这个驱动；但 `fairplayd` 仍禁用时 End 依然 -43004，内核无 FairPlay 报错行。
- 未完成：`fairplayd` 已 `launchctl enable`（按需启动，尚未运行），启用后的预配还没测到——00:37 起 Apple 的 start provisioning 连续返回 **HTTP 503**（短时间内触发次数过多被限流），用户 00:38 的点击也是 503 → UI 111。需停一段时间再测。
- 无凭据触发方法：`launchctl kickstart -k gui/501/com.apple.FeatureAccessAgent`，约 18 秒后它向 akd 取认证头并触发预配（[guest-trigger-provision.sh](../research/apple-account-2026-11-15/guest-trigger-provision.sh)）。注意 zsh 的 `log` 是内置命令，要用 `/usr/bin/log`。
- 本次改动的 guest 状态：为进桌面临时开了自动登录（`autoLoginUser=droid` + `/etc/kcpassword`），测完要关；本次开机 DHCPv4 没拿到地址，SSH 走 IPv6。自签带 `com.apple.authkit.client.*` 权限的探针会被 AMFI 杀掉，不可用。

### 暂停（2026-11-16 00:50，用户决定暂时不修）

- 限流解除后（00:47）用户再点一次：Start 200 → End 仍 -43004，`fairplayd` 虽已启用但 runs=0，从未被拉起；`lskdd` 也打开了 FairPlayIOKit 用户客户端。未验证的方向：`fairplayd` 开机时被禁用，host special port 17 可能没注册，需在开机前就启用（改 Data 里的 disabled.plist 后重启）再测。
- 已恢复：自动登录关闭（`/etc/kcpassword` 与 `autoLoginUser` 已删）、`fairplayd` 重新禁用、guest `/tmp` 探针与日志已清。
- 保留未动：手机上运行的仍是带 `FairPlayIOKit` 的内核（原盘 `boot.img.before-fairplay`）；`configs/kc-keep.txt` 多一行 `com.apple.driver.FairPlayIOKit`，未提交；本文档未提交。
