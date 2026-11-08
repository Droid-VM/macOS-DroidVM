# macOS on DroidVM / Gunyah — TODO

约束：工作只在 `macos/` 内（`../ios` 只读参考）；文档（TODO.md、docs/）不提交，只提交已验证的代码分组；不用 `cargo check`；内核构建 16 线程；答复用中文；构建结束要自己监视并继续，不等用户提醒。历史记录见 `docs/log-2026-10.md`，xnu-12377 移植细节见 `docs/xnu-12377-port.md`。

目标：在 Android / Gunyah / crosvm 上跑完整 macOS 用户态（目前目标版本 macOS 27.0.1 = 26A434），到 loginwindow、Finder/Dock，Data 可持久化，从 DroidVM App 重复启动。

## 交接（2026-10-28 晚，最新：开机慢 / Dock / 设置图标）

完整记录见 `docs/log-2026-10.md` 的「2026-10-28（续）」节。

- [x] 开机很久才出画面：fseventsd 认不出 union 根卷 → patch 0013（xnu-m bd5eb7a，主仓库 7a89570），SecurityAgent ~200 s → 91–153 s。
- [x] App 启动 panic（launchd 映射不了 dyld 缓存）：droidvm-app.py 默认 `MACOS_LP_SIP0=0x2`（主仓库 6e1b5e1）。
- [x] Dock 不出：kernelmanagerd 因 union 根 `mkdir("/dev")`=EROFS 从未启动，iconservicesagent 卷图标同步等它 → patch 0014（xnu-m a360f13，主仓库 6e1b5e1），已验证。
- [x] 设置图标空白：iconservicesagent 的 GPU 地址窗口 256 MiB 用尽 → build-droidvm-gpu.py 普通槽改 1 GiB（共 24 GiB / VBO 64 GiB），上机后地址报错 0 次（已提交，见 git log）。
- [ ] GPU 池（`droidvm-gpu-pool-mib=1024`）峰值 985 MiB：打开设置后 iconservicesagent 一次 +180 MiB、退出后不明显回落 —— 查是否泄漏/谁持有；必要时加大池。DroidVMGpu 只检查 VBO ≥ 3 GiB，宿主 VBO 若 < 24 GiB 后面的槽会越界，应改成按 va_size 校验或运行时分槽。
- [ ] kernelmanagerd 跑起来后 IOMatchDefer 的 Apple 驱动会开始匹配，留意新行为；其 plist 带 `PanicOnConsecutiveCrash`。
- [ ] 剩余开机慢：新 Data 首启 LaunchServices seed ~25 s；偶发 Data 卷卸载尝试后 ~20 s 等锁（带 `syscall-err-log=1` 抓发起者）；guest 时钟 1970。
- [ ] WallpaperAerialsExtension 无网时 NSException 崩溃循环（下载 Aerials 资源失败）。
- [ ] Persist unified log 只落到开机后 ~130 s，之后不落盘（logd？），影响事后分析。
- 诊断：Linux 读 unified log 用 `sources/macos-UnifiedLogs`（unifiedlog_iterator），Data 卷挂载 `/tmp/mount-data.py`；未提交：`tools/m2vsim/pull-trace.py`（含 stderr 修复）。

## 交接（2026-10-28，最新：重场景拖动 ~118 帧/s，显示 118–121 帧）

完整记录见 `docs/log-2026-10.md` 的「2026-10-28」节。**现状（kc292）**：在 kc271 配置上加了 `ca-free-wakeup=1`（插件替换 `-[CAWindowServerDisplay nextWakeupTime]`）、kext 提交不再逐 job 问宿主 fence、NativeMetal rebase 到 Droid-VM/NativeMetal wip/hackintosh（编码线程 + mimalloc + LTO）。重场景拖动（p50/p90）：帧间隔 8.4/8.8 ms、每秒 115–118 次更新、主线程更新 3.9/4.8 ms、输入→GPU 完成 11.9/15.3 ms（kc283 无替换时 60 帧、18.7/26.0 ms）。

- [x] 已提交（主仓库）：0e83307 + 6d40d19 唤醒替换；89b9753 映射表查找；7d33e8f 提交不问 fence；4666fd6 mimalloc；83c4713 LTO；55ead6c WindowServer 编码线程。NativeMetal `macos-droidvm` = 上游 7e1f149 + 0e4481d + 8ec1b85 + d811708（旧分支 `macos-droidvm-pre-hackintosh-rebase`），已推送（见下）。
- [x] App 默认参数（24af265，已推 droidvm/macOS）：`GPU_ARGS` 加 `ca-triple-buffer=1`、`ca-free-wakeup=1`、`exec-env=WindowServer:MallocZeroOnFree=0`；要 `MACOS_GPU=1 python3 scripts/droidvm-app.py boot` 重做 boot.img 才生效（未做）。1080p（droidvm-app.py WIDTH/HEIGHT + run-macos-vm.py `fdt_framebuffer_bytes`）仍未提交。
- [x] 已推送（2026-10-28）：NativeMetal macos-droidvm → droidvm/macOS d811708（force，旧 cd3bbff 留本地 `macos-droidvm-pre-hackintosh-rebase`）；UniXNU 5e85533（补丁 0021–0023）+ 789261f（指针）→ origin/macOS；主仓库 → droidvm/macOS 24af265；上游 547a07e 的高队列优先级依赖它自己的 metal2vulkan 0012，和我们的 0012 冲突，没接。
- [ ] 主线程剩余（kc284/kc286 采样）：更新内 malloc 叶子 ~12%（magazine tiny 空闲链表，mimalloc 只管 Rust 侧）、memmove/memset ~5%、objc_msgSend 3%；更新外占主线程运行 ~32%（CA prepare_layer0 ~39%、事件 ~12%）。输入→帧开始仍 4–8 ms：DroidVMInput 4 ms 轮询（`pollMs`）可改中断/更短。
- 诊断（不提交，`research/debug-2026-10-28/`）：WSLatency.mm（插件 `NMB_LATENCY=1`：每 10 s 打 in->begin / begin->finish / commit->gpu / in->gpu / begin->begin，以及唤醒询问、canUpdate、帧间空隙；1 kHz 采样更新线程写 `/private/var/tmp/ws-samples.txt`，`tools/m2vsim/pull-trace.py OUT --name ws-samples.txt` 取回，A 行全量逐地址计数，符号化要用**同一次构建**的插件二进制）；diag-kext.patch（DroidVMInput `droidvm-input-times=1` 输入时间戳、kext `DROIDVM_GPU_SUBMIT_TIMES=1` 提交分段计时）；diag-build-metal-plugin.patch（NMB_LATENCY/NMB_TRACE 构建段）。系统库地址用 `~/gotmp/ipsw/ipsw dyld a2s out/dsc/dyld_shared_cache_arm64e ADDR --cache out/dsc/27.a2s`。

## 交接（2026-10-27 晚，最新：重场景拖动已到 ~112 帧，未稳 120）

完整记录见 `docs/log-2026-10.md` kc240–kc271。**现状（kc271）**：宿主 8 vCPU 1:1 绑核、vCPU 6/7 在大核且 capacity 1024（guest AMP：0–5 E、6–7 P），metal2vulkan 补丁 0011–0020，WindowServer `MallocZeroOnFree=0`（内核 `exec-env`），`ca-triple-buffer=1`：重场景（53–56 pass / ~195 draw）拖动最好 20 s 窗口 112 帧/s，显示端约 50 s 内每秒 111–121 帧；enc p50 4.3 ms（每 draw 21.5 µs）、ctc 4.3 ms、gpu 2.8 ms。仍会在 60 档与 120 档间跳：enc 一过 ~5 ms（draw 多的帧）就掉 60，但也有 enc 4.2 ms 仍 60 的片段 → 主线程上还有 enc 以外的超时（CA render/事件，待采样）。
（旧现状 kc254：61–67 帧，主线程 ≈13.5 ms/帧，enc 7.5–8.7 ms。）

- [x] IOSurface 导入 1 s 强引用（已提交 8d4f6e2）。
- [x] "边界空等"= metal2vulkan 影子纹理拷进拷出；turnip host 分配图像不再要求专用分配（tu_image.cc），ctc 12→~5 ms（kc245，已提交）。
- [x] 提交上限 16→64（turnip/guest kext/`Job::handles`/crosvm MAX_IBS），每帧内核提交 7→2（kc250，已提交；crosvm 已部署）。帧率不变。
- [x] KGSL 上下文优先级 1：无效，已撤（kc240）。CPU 0–5 核提频 +20%：帧率不变（kc251，已恢复）。
- [x] CA 流水：`ca-triple-buffer=1`（插件设 CA_FORCE_TRIPLE_BUFFERED_LATENCY）有效，重场景 56–60→61–67（kc253，已提交）。
- [x] 减少透明度（`stage-gpu-plugin.py --reduce-transparency`，托管偏好）：kc254 pass 数仍 53、draw −22%、enc 8.7→7.5 ms，帧率无变化；**未确认 guest 里开关是否真生效**（待用户看 System Settings → Accessibility → Display）。**用户决定（2026-10-28）：不关毛玻璃/减少透明度**，落盘不再带 `--reduce-transparency`（kc254–kc279 带过，但 pass 数没变，大概没生效）。
- [x] 上游 NativeMetal rebase（ce5e19e，含 metal2vulkan 0008–0016）：kc255 enc 每 draw 40→35 µs、帧率 60–66 不变；已推 macOS 分支（NativeMetal force push，旧分支留 `macos-droidvm-pre-rebase`）。剩余 draw 内热点分散（record 17%、settle_draw 15%），B 收益递减。上游 `TU_DEBUG=nocb` 未跟进。
- [ ] 待用户决定：`ca-triple-buffer=1` 与 `exec-env=WindowServer:MallocZeroOnFree=0` 是否默认（App 启动的参数烧在 boot.img，不在 vms.json：改 `scripts/droidvm-app.py` 的 `GPU_ARGS` 后 `droidvm-app.py boot`；之前先用不开 `NMB_FRAME_ROWS` 的插件正常落盘）。
- [x] A 大小核 guest 侧（kc264/kc265，已提交：内核 8e94e11 = patches/xnu-12377/0011，主仓库 1d471de）：BCM2837 板 MAX_CPU_CLUSTERS 2 + `__ARM_AMP__` + CONFIG_SCHED_EDGE_OPT_OUT（sched_amp：无 CLPC 时 utility 以上的用户线程上 P 核，后台/utility/内核线程上 E 核，P 忙时溢出到 E；Edge 无 CLPC 时所有线程偏好启动集群，不用）；ml_processor_register 按设备树取每核 cluster type（ArmCpu 一律报启动核的）；只有一种核时跳过双 pset 断言。ADT（run-macos-vm.py）按 FDT `capacity-dmips-mhz` 最大者标 'P'、其余 'E'，全相等标全 'P'；`MACOS_AMP=0` 给旧内核，`MACOS_CPU_TYPES=EEEEEEPP` 测试用。验证：全 P → hw.nperflevels 1 / Performance 8；EEEEEEPP → Performance 2 / Efficiency 6，pset0 = cpu0–5 (E)、pset1 = cpu6/7 (P)，登录/WindowServer 正常。
- [x] A 大小核宿主侧（用户已配：`--cpu-affinity` i=i、capacity 6/7=1024 其余 792、cluster 0-5/6-7）：kc267 enc 7.5→4.8 ms、重场景 ~104 帧/s（与补丁同时生效，未单独 A/B）。
- [ ] B metal2vulkan 剩余：每 encoder `vkResetCommandPool`（guest 剖析 ~11%）、每 pass 建 VkFramebuffer（~6–8%，可按 pass+view 缓存，失效用 views_epoch）、每 draw 新分配描述符集 + vkUpdateDescriptorSets（turnip 有 push descriptor）；end_pass 每 encoder ~35 个一次性 Vec。都可在宿主回放上做（golden 校验）。
- [x] m2vsim 录制回放（`tools/m2vsim/`，未提交）：WindowServer 的 nmb_* 调用录 trace（`NMB_TRACE=1` 构建 + `nmb-trace=1`），同一 bridge 编 Linux 版在手机宿主回放。重帧（192 draw）bridge：guest WS 7.36 ms / guest 内单独回放 6.58 ms / 宿主小核 3.75 / 大核 1.75 → 差距是 guest 平台开销，不是 CA 抢缓存（kc256/kc261）。
- [x] cpubench（guest 大核 vs 宿主大核，ns）：alu 持平、malloc-free 41/6.7、hashmap 24/5.6、getppid 252/87、chase-2M 7.2/5.8；PAC 无影响。
- [x] ~~arm64_maxoffset 覆盖 → 无 xzone~~ 已证伪（kc263）：guest 一直是 xzone（`MallocDebugReport=stderr MallocReportConfig=1` → Enable Xzone 1/default），只是没有 VM 地址区间（安全特性，不影响速度）→ **内核补丁不做**。27 的 libmalloc 在 macOS 上要求 zero-on-free 才开 xzone（`MallocZeroOnFree=0` 会退回 magazine）。
- [x] `MallocZeroOnFree=0` 只给 WindowServer（kc270/kc271）：内核新开机参数 `exec-env=NAME:VAR=VAL[,…]`（xnu-m b5fc7f3 = patches/xnu-12377/0012，主仓库 a8112c1），WindowServer 报 `Enable Xzone Malloc: 0`（zero-on-free bincompat）。`launchctl setenv` 到不了 WindowServer；bootout/bootstrap 副本报 EIO 且 WindowServer 不再起来——用户态路线都不行。效果：在补丁之上 104→112 帧/s，每 draw enc 21.9→21.5 µs（噪声内），即锦上添花。
- [x] 桥接层减分配（UniXNU b5d3ffa，patches/metal2vulkan/0011–0020，宿主回放 golden 逐行一致）：draw_indexed 分配 40.9→11.2、render_draw 54.6→13.9、encoder_end 111.5→91.6、commit 200→120；宿主时间不变（malloc 便宜）。guest 同配置 A/B：无补丁（即使 MallocZeroOnFree=0）75 帧/s、每 draw 24.2 µs；有补丁 104 帧/s、21.9 µs（kc270/kc267）。
- [ ] 压主线程（2026-10-28 计划）：重场景拖动 guest 侧延迟约 30 ms = ① 输入等主线程开始本帧（约 8 ms，主线程 96% 忙 + vsync 对齐）+ ② 主线程一帧（约 16 ms，其中 enc p50 4.4 ms）+ ③ commit→GPU 完成（ctc p50 6.5 ms，GPU 4.5 ms）；宿主显示另估 8–17 ms（未测）。② 每少 1 ms，① 平均也少约 0.5 ms。主线程采样（kc277+kc273 共 114 个，太少只能看排序）：bridge+turnip 约 49%（draw_indexed 16%、commit 11% 其中约 7% 卡在提交 ioctl、encoder_end 8%、encoder_new 4%、texture_new 3.5%），CA/SkyLight 约 43%（遍历、GlassBackgroundFilter、事件约 6%，很分散），空闲约 8%。不关毛玻璃，只让同样的工作变快。目标：② 16→12–12.5 ms、① 8→3–4 ms、guest 延迟 30→约 22 ms、重场景 60→75–80 帧。按顺序：
  - 进展（kc282–kc284，2026-10-28）：诊断 `research/debug-2026-10-28/WSLatency.mm`（插件 `NMB_LATENCY=1`，每 10 s 打 in->begin/begin->finish/commit->gpu/in->gpu/begin->begin，主线程 1 kHz 采样写 `/private/var/tmp/ws-samples.txt`，`pull-trace.py --name ws-samples.txt` 取回，A 行是全量逐地址计数）+ DroidVMInput `droidvm-input-times=1` + kext `DROIDVM_GPU_SUBMIT_TIMES=1`。重场景拖动 p50/p90 ms：kc283（无唤醒替换）帧间隔 16.6/17.6、in->gpu 18.7/26.0；kc282（开）10.4/12、14.7/19.5；kc284（开 + 提交不问宿主 fence）10.2/11.5、13.4/17.8，begin->finish 6.2→5.2。kext 每次提交 hold 97→8 µs（根因是 retireCompleted 对每个在飞 job 发 DROIDVM_GPU_OP_RETIRED 往返，不是扫表），剩 ring 宿主往返约 100 µs × 每帧 2–3 次。帧间隔现在卡在替换的下限 8.33 ms + SkyLight updater 0.5 ms + 定时器余量 ≈ 10.2 ms。kc284 采样：更新内 drawIndexed 路径约 65%、malloc 叶子 12%、内核叶子 12%；更新外占主线程运行 32%（CA prepare_layer0 约 39%、事件处理约 12%）。
  - 进展（kc286–kc289，2026-10-28）：NativeMetal rebase 到 Droid-VM/NativeMetal wip/hackintosh（编码线程 + mimalloc + LTO fat，WindowServer 开编码线程；旧分支备份 macos-droidvm-pre-hackintosh-rebase）：更新 5.2→4.0 ms、in->gpu 13.4→12.2 ms，帧间隔仍 10.0 ms（约 100 帧，DroidVMDisplay 也是 ≤100）。100 帧上限排查：canUpdateWithFlags: 从不拒绝（0 次 NO）；SkyLight 每帧约 30 次问 nextWakeupTime，最后一次在上帧 begin 后 9.0 ms，之后 0.9 ms 是回调内准备工作（不是二次定时器）；答案再提前 0.5 ms（kc289）无效已撤。下一步要看 SkyLight `WS::Updater::UpdateDisplays` 里 `WSDisplayUpdateQueueSchedule` 的排程条件（Display 虚表 +1368 就绪、+1376 next_wakeup_time、+1400 帧时长，`last < wake − 1.25 帧` 的判断）和 `update_display_callback` 的 backoff（earmark 0.9、上限 2 ms，按理未触发）。
  - 进展（kc290–kc292，2026-10-28）：100 帧上限的来源是 SkyLight `WS::Updater::UpdateDisplays`：只有 last < nextWakeupTime + 0.5 ms − 1.25 帧 才立即画，否则排到唤醒时间。插件唤醒答案改成两段（以 SkyLight 回调开始 = 它在 begin 前最后一次询问为起点）：到点前答 起点+8.33−0.5 ms，到点后答 max(现在, 起点+1.25 帧+1 ms)。kc292：帧间隔 8.4/8.8 ms、每秒 115–118 次更新、DroidVMDisplay 118–121 帧、in->gpu 11.9/15.3 ms。答"现在+1.25 帧"（kc291）会在无新内容时把下次唤醒推到 11 ms 后，出现 20 ms 长尾。
  - [x] 0 测量：DroidVMInput 收事件、DroidVMDisplay 上屏各打时间戳，按帧配对出 ①+②+③ 实测，作后面各项 A/B；重采主线程（降频、拉长到几百样本），拆清 CA 那 43%。
  - [x] 1 替换 `nextWakeupTime`（见下条），缩 ①，约 4 ms。已做（0e83307）：插件 `ca-free-wakeup=1`，60→约 98 帧。kc285 试过把下限提前 1.5 ms（6.83 ms）：帧间隔 p50 仍 10.4–10.5，p90 反而 11.5→14–16、更新 p90 6.2→9、in->gpu p50 13.4→15.2，已撤；10.2 ms 不是下限卡的，是主线程本身（更新 5–6 ms + 更新外约 2.5 ms + 调度）。
  - [~] 2 异步提交：turnip darwin 后端加提交线程，`queue_submit` 交出即返回，完成仍走 fence（或 kext 发出不等宿主回复）。约 1 ms/帧。更正旧判断"价值已下降"：那测的是 scheduled wait 0.12 ms/commit，不是提交 ioctl 本身的宿主往返（采样约 7%）。 **部分完成（2026-10-28）**：kext 提交路径不再逐个 job 向宿主问 fence（7d33e8f，hold 97→8 µs）、映射表查找有提示（89b9753）；上游编码线程（55ead6c）把运行时那半连同提交挪到后台线程，主线程不再等提交。剩每次提交约 100 µs 宿主往返（在编码线程上）。
  - [ ] 3 每 draw 改 push descriptor（B 项），0.5–1 ms。宿主回放 + golden。
  - [ ] 4 encoder 固定开销：VkFramebuffer 按 pass+view 缓存或 imageless framebuffer、end_pass 一次性分配复用、查 `tu_BeginCommandBuffer` 为何每 encoder 都 `tu_init_hw`/`tu6_init_static_regs`、残留小纹理影子拷贝。约 1 ms。
  - [ ] 5 纹理复用池（描述符相同跨帧复用；`texture_new` 走 `memory::keep_room`）。先补测真实占比（计时 5 次/帧×15 µs 与采样 3.5% 对不上），0.3–0.5 ms。
  - [ ] 6 液态玻璃 pass（GlassBackgroundFilter）的编码与 GPU 开销专项，等第 0 步拆出来再定。
  - [x] 远期：完整命令流线程（encoder 结束 + primary 录制 + 提交挪后台，commit 时同步），bridge 的 30–40%；只挪 draw 已证实无效（每 encoder 平均 3.3 个 draw）。 **已由上游做掉**：NativeMetal wip/hackintosh 的编码线程（c5df8de..fd9fbe1），WindowServer 默认开（55ead6c），`/private/var/ngpu/debug/no-encode-thread` 关。
- [x] 掉 60 帧时采 WindowServer 主线程（`sample` 2–3 s，不要 20 s，会拖帧率），看 enc 以外（CA render/事件/prepare）谁超 8.33 ms。 已由 WSLatency 的主线程采样替代（research/debug-2026-10-28）。
- [x] 帧起点不对齐 vsync：插件（已在 WindowServer 进程里，同 `ca-triple-buffer` 的做法）用 ObjC 运行时替换 `-[CAWindowServerDisplay nextWakeupTime]`，返回 max(现在, 上一帧开始 + 8.33 ms)。依据（IDA，2026-10-28）：SkyLight `update_display_callback` → `WSDisplayUpdateQueueSchedule` 的时间取自 `SLCADisplay::next_wakeup_time` = `nextWakeupTime` + `updater_wakeup_delay`(0.5 ms)；CA 侧 `IOMFBServer::next_wakeup_time` = `previous_vbl()`（现在对齐到 VBL 格点）+ 帧周期 → 13 ms 的帧下一帧从 16.7 ms 开始；返回 0 时 SkyLight 用"现在"（基类 `Server::next_wakeup_time` 就返回 0，虚拟显示器因此不锁 vsync）。SkyLight 那处调用是桩 0x1880D56E0，推断为 objc_msgSend$nextWakeupTime，实现前先核实。预期：8.5–12 ms 的帧 60→83–118 帧，消掉 60/120 断崖；kc277 最重场景主线程 60 帧时已 96% 忙，只到 ~62–65。风险待上机：`can_update_` 在非对齐起点可能拒绝→SkyLight 退避重排、动画时间戳仍按 vsync、宿主 120 Hz 下帧间隔不均。已排除：`CA_VSYNC_OFF`（只是全屏直出的撕裂 swap 标志，DroidVMDisplay 本来就收到即上屏）、VRR（只对全屏 app）、ProMotion 档位（要 MobileGestalt SupportsPerseus）、240 Hz 刻度（用户否决）。 **已完成**：0e83307（60→96 帧）+ 6d40d19（按 SkyLight `UpdateDisplays` 的 1.25 帧规则两段作答，→ 115–118 次更新/s、显示 118–121 帧，kc292）；`can_update_` 从不拒绝、动画时间戳问题未见。
- [ ] 着色器缓存：NMB_RUNTIME_ID 随补丁变 → 缓存全失效，kc267 管线编译共 37 s、最长 19.8 s（拖动开头的卡顿）。发布前考虑预热或不随补丁失效。
- [ ] 提交 `tools/m2vsim/` + build-metal-plugin.sh 的 NMB_TRACE 段 + stage-gpu-plugin.py `--file`（待用户同意）。
- [ ] guest fence 自旋轮询（~6000 次/s VM exit）改等待。
- 帧数据：`NMB_FRAME_ROWS=1 bash scripts/build-metal-plugin.sh --no-deps`（主仓库 1936854，默认关）→ WindowServer 每 20 s 打 telemetry 表 + K 行带 `gpu=`/`enc=`（每次只含最近 ~20 个 commit 的快照）；拖动帧率用表里 `S c<N>` 计数差 /20 s 和 DroidVMDisplay `at most N frames in a second`。分析脚本 `/tmp/kan.py`。research/ 的 macos.patch 已与现代码打不上，别再整体 apply。
- 首次登录偶发卡转圈（Dock.agent/Finder 未被 loginwindow 拉起）：`/tmp/restage-kick.sh`（= restage.sh 但 `--run 60 "$(cat /tmp/kickcmd.sh)"`：登录后未运行就 kickstart Dock/Finder/SystemUIServer，且不带 20 s WindowServer 采样）。
- 诊断代码已从提交剥离，完整版在 `research/debug-2026-10-27/`（turnip `tu-pass-timing=1` pass/步骤计时、插件 K 行 gpu/enc、`ca-latency-probe=1`、异常栈、`tu-debug=`、bridge 影子纹理通知、crosvm droidvm-gpu 统计）：`git apply research/debug-2026-10-27/macos.patch`（crosvm.patch、nativemetal-unstaged.patch 同理）。
- 上机：`/tmp/boot3.sh TAG [内核参数]`（同 boot.sh 但不用 `pkill -f`；起 tail → `/tmp/run7-all.txt`，tail 时限已改 4 h，1 h 时会丢拖动数据）；插件重编后跑 `/tmp/restage-kick.sh`（不带 `--reduce-transparency`）。刚停 VM 立刻再起会遇到 droidvmd "Huge-page control is busy"（大页回池竞态），smoke 脚本识别不出、会空等 `sleep 900`，结束那个 sleep 让 kc-try 重试即可。看拖动：WSLatency 行（`grep "WSLatency: in"`，每 10 s）+ DroidVMDisplay `at most N frames in a second`。

## 交接（2026-10-26）

现状：macOS 27.0.1 在 xnu-12377 + 26.5 kext 上能到登录界面，droid/droid 能登录，WindowServer 经 DroidVMDisplay 出画面。登录后 loginwindow 不拉起 Dock/Finder/SystemUIServer（手动 `launchctl kickstart gui/501/com.apple.Dock.agent` 后 Dock 正常、壁纸出来）。本轮完整结论见 `docs/log-2026-10.md` 的「2026-10-26」节。

### 优先级 1：开机慢 —— 已拆成两个独立问题

**A. SIGPdisabled 从未清除 → 8 个 vCPU 空转（已修、已提交、已验证）**
- 根因：XNU 只在核收到第一个 IPI 时清 `SIGPdisabled`（`osfmk/kern/machine.c:528`）；Gunyah 上板级驱动从不给核发 IPI，`cpu_idle()` 每次因 `idle_disallowed` 立刻返回，`machine_idle()` 立刻再进 → 8 个 vCPU 全速空转，guest 记成 idle，宿主 800% CPU。
- 修复：`patches/drivers/ArmCpu-idle-wfi.patch`（主仓库 `0983b9f`，`gSelfIpi` 默认开，每个核自投 SGI 0；`waitClear` 加超时；`for(;;) wfe` → `parkCore()`）+ `patches/xnu-12377/0010-…patch`（内核 `6136ce7`，虚拟板所有 idle 路径以 WFI 结束，`idle-wfe=1` 可回退做 A/B；pc-sample 报告 idle 分支）。
- 效果：loginwindow 85.0 → 73.4 s，WindowServer 85.2 → 74.2 s；宿主 idle 3% → 396%。
- 注意 `idle-wfe=0` 单独改无效（`Idle_load_context()` 在 `if (idle_proximate_timer_wfe == 1)` 外面，关掉 WFE 会变成更紧的空转），三处必须一起门控。

**B. 新种子首启多出的 ~130 秒 = Data 卷缓存生成（已定位、未修，用户决定暂时不做）**
- 时间表（kc165 新种子首启）：WindowServer/loginwindow exec 74.9 s → frame 1 @115.3 s → **81 秒一帧不交** → frame 3 @196.5 s → SecurityAgent exec 206.1 s → **frame 50 @244.6 s 才是登录界面**。复用种子约 75~93 s。
- 空档期间宿主 vCPU 近乎全闲（秒 111–145 每轮只 +4~26 ticks），WindowServer 294 个采样块全 `state 0x1` + `mach_msg`：它在等 SecurityAgent，不是在算。
- 同期真正在干活的是 Data 卷写入：首启共写 198,055 块 = 774 MB，最大单次 998 ms；空档的核心在 137–148 s（两次 23k/35k 块）。
- 取回 overlay 解析：**106,272 改动页 = 415 MiB**，集中在 200–700 MB，350/600 MB 处是 C++ 符号名 → **LaunchServices 数据库 + dyld 闭包缓存**。
- 修法（未做）：stage 时把这些缓存预置进种子。`scripts/fold-overlay.py` 已写好（未提交，在工作树），卡在 `packed_ramdisk.py` 的 `MAX_INPUT = 256 MiB`（折叠后需 625.3 MiB）。备选：A 提高 `MAX_INPUT`、B 只预置缓存目录、C 改批量写。

**C. launchd 的 27 秒空档（排第二、未修）**
- 32.4 → 59.5 s 一个 exec 都没有，launchd（pid 1）自己卡住；`state=0x4`（running）但宿主 vCPU 每轮只 +3~8 ticks，user 0%，PC 停在 dyld `__TEXT` 末尾 `+0xc0000`。修好 SIGPdisabled 之后仍在 → 不是同一个原因。下一步：读 34–58 s 之间 launchd 各线程的 kN 帧。

**已排除（都有数据，别再追）**：`ml_get_timebase` 单次 19.6 ns（不 trap）；日志量 55 KB≈5 s；`machine_delay_until` 改 WFI（2.67 s 卡死，已回退）；`powergate_latency`（1.6 s，噪声内）；NativeVirtioBlock 自旋（1.3 s）；`fcntl`；xprotectd/digest-service 循环（首次 exec 全在登录界面之后）；诊断工具自身污染（kc162 去干净后空档仍在）；WindowServer 自身瓶颈。

**已知外部因素**：手机前台放视频时 HyperOS 把大核压到 1.02 GHz（`adb shell 'su -c "cat /sys/devices/system/cpu/cpu6/cpufreq/scaling_max_freq"'` 先看，正常应更高；不要替用户切前台应用）。

### 优先级 2：loginwindow 不拉 Dock/Finder/SystemUIServer
- 只有 `-[Login1 continueLaunchWorkspace]` 调 pokeDock/pokeFinder/pokeSystemUIServer（`_kickstartJobWithLabel:`）；调用链 `-[LWMounter mountStartupVolumesFromPrefs]` → `continueLaunchWorkspaceAfterServerMounts` → `continueLaunchWorkspace`，另一入口是 setupAssistantFailureContinueLogin。说明登录流程停在这之前。
- 已打好诊断镜像（当前 `out/metal/stage/scratch-data.img`）：`--run 60` 任务等 gui/501 出现后 120 s，`log show` 抓 loginwindow 的 Login1/ERROR/LoginTransition/Setup/ait/ApplicationManager 消息（前缀 `LW `），再 kickstart Dock/Finder/SystemUIServer（前缀 `KS `），结束打 `DIAG-END`。kc136 已用它启动，用户需登录。看 `LW` 行最后一个 `| enter` 停在哪。注意 grep 不要用 `[^\[]*`（消息里有 `-[Class sel]`）。
- 临时方案：在 run 任务里 kickstart 三个 agent（已在诊断里）。

### 本轮已做（2026-10-25）
- 已提交并推送 droidvm 远端（a5831b3/2a829e2/59659e4）：Data 盘接 DroidVMDataStore（黑屏/内存耗尽根因）、Metal 插件 gpuCoreCount/协议/bitCodeHash、跳过设置助理、DroidVMGpu 上限与日志、turnip 诊断日志。
- 未提交（已上机验证有效）：
  - 内核 `out/x12377/xnu-m/security/mac_base.c`：`virt_sandbox_allow_all_profile`，call 0 遇到 204 操作的 macOS 27 配置，换成 26.5 格式「全允许」配置（424 字节：16 字节头、198 项操作表、1 个终结节点 01 00..）。修复所有 .appex 扩展崩溃（libxpc「XPC service requested sandbox, but is not sandboxed!」）。需导出为 patches/xnu-12377 新补丁再提交。`osfmk/kern/zalloc.c` 的 zone-sample 诊断不提交。
  - `overlay/metal/NativeAdrenoMetalPlugin.mm`：`featureProfile` 返回 0（Core Image 拼接库路径）。iconservicesagent 仍崩，下一个缺 `NBFunction libraryData`；建议让 newLibraryWithStitchedDescriptor 返回 nil+NSError 而不是继续补方法。
  - `scripts/run-macos-vm.py`：有 data-store 时 ADT `/chosen` 不写 `ephemeral-storage`（否则 usermanagerd 不建 persona 管理器，登录时断言 `_gPersonaManager != nil` 崩）。已验证 usermanagerd 不再崩。
- 其它待查：WallpaperAerials NSException、fseventsd 在 DiskArbitration 回调里空指针、mobileactivation 崩溃循环、Keychain Not Found 对话框、IDSBlastDoorService。

### 上机流程（当前用法）
- 启动（会先编 KC）：
  `python3 scripts/droidvm-app.py stop; for p in $(pgrep -f "^bash scripts/kc-try\|xnu12377-smoke\|^bash /tmp/tail8.sh\|^python3 /tmp/tail7.py\|^timeout [0-9]* python3"); do kill $p; done; rm -f /tmp/run7-all.txt; (setsid nohup bash /tmp/tail8.sh >/dev/null 2>&1 &); (MACOS_MEM_MB=4096 MACOS_DATA_SEED=$PWD/out/metal/stage/scratch-data.img MACOS_TRUSTCACHE=$PWD/out/metal/stage/kernel.macho.trustcache MACOS_TAG=27.0.1 MACOS_GPU=1 MACOS_DISPLAY=1 setsid nohup scripts/kc-try.sh 900 rootauth=0 crash-log=1 msgbuf=2097152 stderr-log=1 -arm64e_preview_abi exec-log=1 droidvm-gpu-pool-mib=1024 > /tmp/kcNNN.log 2>&1 &)`
- 内存 4096（5120/6144 在 UEFI 崩）；msgbuf 保持 2 MB（8 MB 早期日志会丢）。
- guest 内核日志：`/tmp/tail8.sh` 等新 crosvm 后跑 `/tmp/tail7.py`，全量写 `/tmp/run7-all.txt`（`LC_ALL=C grep -a`，宿主 grep 是 ugrep）。`/tmp` 是 tmpfs，脚本丢了要重写（tail7 用 `/tmp/rig.py` 的 `since(pos)` 读 msgbuf）。
- 关键日志：`exec: pid N name`、`crash: pid ...`（`scripts/crash-symbolize.py LOG out/dsc/dyld_shared_cache_arm64e /home/qiuqiu/gotmp/ipsw NAME`）、`DroidVMDisplay: frame N: X pixels lit`（登录界面/桌面是否有内容）、`top:`（`--top 30` 任务）、`sandbox-call: ... applied as allow-all`、`sample:`（`sample-name=NAME sample-period=S`，`/tmp/samplesym.py` 符号化最后一个周期）。
- 重打包镜像（会换种子 → data-store 从空白开始，首启慢）：`STAGE_ARGS="--setup-done --top 30 --disable-job com.apple.audiomxd --disable-job com.apple.apsd --disable-job com.apple.AppSSODaemon --disable-job com.apple.filesystems.fskitd --user droid:droid" bash scripts/build-metal-plugin.sh --no-deps`；带含空格的 `--run SECONDS CMD` 时直接调 `scripts/stage-gpu-plugin.py --probe out/metal/probe/metal-probe ... --run 60 "$CMD" out/metal/plugin/NativeAdrenoMetal.bundle`。不重打包时 data-store 按种子 SHA-256 续用，上次的登录状态保留。
- 内核：`cd out/x12377; XNU_KC=1 XNU_KEXT_CRYPTO=1 bash build-full.sh`（约 4 分钟，后台跑）。NativeRamBlock：`python3 scripts/build-native-ram-block.py`。
- 系统卷只读挂载在 `/tmp/tmp.lAN7hN76DR`（27.0.1 OS 卷，逆向 loginwindow/usermanagerd 等从这里取）；IDA MCP 可用。
- 习惯：等待用 `timeout N bash -c 'until ...; do sleep 5; done'`，单次 ≤ 2 分钟；不要读宿主上的 guest 帧缓冲（会重启手机），看画面让用户截图；不要切手机前台应用；不用 cargo check、不做格式化工具改动；文档不提交。

## 现状（2026-10-23）
- 在线路线（已上机）：xnu-10063 内核 + iPad 17.7 kext + macOS 27.0.1 用户态，经 App 的持久化 VM 启动（id 3307dca0-8a10-59af-8abf-1a1501cd5b40，镜像在 `/storage/emulated/0/DroidVM/MacOS`，8 核）。launchd 已拉起 200+ 进程；无 WindowServer/GPU。
- 新路线（用户选定）：内核换 xnu-12377.121.6（macOS 目标）+ macOS 26.5 原生 kext。12377 内核（UniXNU 社区 fork 的 ios26 补丁 + 我们的补丁栈，`out/x12377/xnu-m`）（arm64e，`out/x12377/build-all.sh`）已在手机上启动到 `trust_cache_init`，panic `image4 interface not available`——需要 AppleImage4 等 kext。细节见 `docs/xnu-12377-port.md`。

## 待办（按顺序）
1. 预链接 kext（做成 fileset KC：kc265 的 kext 原位不动，只替换内核；写 `scripts/kc-build.py`）。xnu 12377 在 fileset 路径下要求 KC 头在 `VM_KERNEL_LINK_ADDRESS+slide`、不会调 `rebase_threaded_starts`（内核指针必须是 format-8 链式）、DarwinBoot 不得滑动 load command。设计与里程碑见 `docs/xnu-12377-port.md` 的“fileset KC 方案”。
   - 里程碑 0：只含我们内核的 fileset KC 启动到同一个 `trust_cache_init` panic（验证 KC 路径、链式指纹转换、DarwinBoot、段布局，内核段 `-segaddr` 显式排布）。
   - 里程碑 1：带 AppleImage4 + CoreTrust + corecrypto。先跑 `kext-kernel-imports.py` 看 `missing_in_ours`/`unnamed_targets`；再写重定位器（`bl` 直接按符号改；ADRP 与其 lo12 使用者成组，目标=旧符号+偏移；落到不同页就硬失败；数据指针按符号名重绑，签名不动）。注意内核已链入源码版 corecrypto 与 trust cache 运行时（fork 默认在 BCM2837 上跳过 `trust_cache_init`，我们用 `XNU_TRUST_CACHE_RUNTIME` 打开），要确认与 kext 提供的 crypto/image4 不会重复注册。
   - 之后加 AMFI、Sandbox、APFS、pthread 等。KC 产物约 80 MB，别堆积（磁盘仅 3 GB 空闲）。
   - 已通（2026-10-23）：KC 带 26.5 原生 kext 启动到 launchd 的 dyld 阶段；我们自己编译的 kext（NativeVirtioBlock、NativeAES）经 `kc-build.py --native` 链进 KC；根卷（OS 卷）挂载、launchd 执行、ignition 通过。细节与用法见 `docs/xnu-12377-port.md` 里程碑 2、3。
   - 现在（2026-10-23 晚）：launchd 起完整启动流程，Data 卷（NativeRamBlock 内存盘）挂上，xpcproxy 起守护进程到 pid ~200；在崩溃重启：fskitd(exit 1)、xpcproxy(78)、endpointsecurityd(35)、opendirectoryd（缺 identitysvc=config_ext_resolver）、tccd（confstr/dirhelper）。详见 docs/xnu-12377-port.md「里程碑 4」。
   - 正在做：只加 `config_ext_resolver` 的内核干净重编。完整 macOS 配置补全被 KC 段布局卡住（`__DATA_CONST` 洞零余量、`__TEXT_EXEC` 余量 ~96 KiB，选项一多 ld64 断言 addressA!=addressB）：要先重排 KC 段布局。
   - 临时手段要记账：`MACOS_LP_SIP0=0x2`、`rootauth=0`、owner 链验证桩、JOP pid 强制 1、插件宿主不关 JOP、CE 栈检查摊平、kqworkloop 限额忽略、NativeUfsStoreStub（Data 易失）；正式做法是 boot manifest / owner policy 等。
2. 核对 KDK(25F84) 与 26.5 kext 的接口版本：`KERN_AMFI_INTERFACE_VERSION`、`TRUST_CACHE_INTERFACE_VERSION`、CoreEntitlements API 版本。
3. 把 `xnu-m` 的改动固化成 overlay 补丁（fork 的 21 个 + 我们的合并 + 诊断补丁分开），并让构建能从干净的 `sources/xnu-12377` 复现。
4. 其余板级驱动迁到 12377（`build-platform-12377.py` 之外的：NativeAES、NativeVirtioBlock、NativeRamBlock、virtio-pci、显示/GPU），经 fork 的 `build-xnu-12377.sh` 流程（`out/x12377/un`）链入。
5. 核对 4 KiB 页补丁（共享区域、`mach_loader`、用户 VA 512 GiB、pmap）在 12377 上的语义；审计 PPL/`config_pmap_ppl` 是否会触发 GXF 指令。
6. 核实虚表对比里剩余的 3~5 处名字差异（`IOMemoryDescriptor` 等）。
7. 启动链收尾：owner policy、root pins、内核内嵌签名密钥随 SystemOS 变化需重新生成；用 `droidvm-app.py` 经 App 上机。
8. 并行遗留（在线路线）：Sandbox kext 杀 dasd/bluetoothd、runningboardd 崩溃循环、8 核定时器中断风暴（`ArmCpu.cpp:567` IRQ drain panic）、WindowServer/Metal。

## 常用命令（`/home/qiuqiu/crosvm/macos`）
- 在线路线上机：`MACOS_TAG=27.0.1 python3 scripts/droidvm-app.py boot --kernel-arg exec-log=1 ...`，再 `start`；串口日志 `/data/data/cn.classfun.droidvm/cache/console_<id>_serial1.log`，`scripts/rig-dmesg.py` 读 guest dmesg。
- 12377 内核：`out/x12377/build-all.sh`（arm64e，默认）/ `XNU_ARCH=arm64`，上机冒烟 `MACOS_KERNEL=out/x12377/kernel12377e-osx.macho` `scripts/xnu12377-smoke.sh 30 vm_compression_limit=1572864`；虚表对比 `scripts/vtable-abi-diff.py KERNEL KC`。
- 改根盘：`MACOS_TAG=27.0.1 scripts/rebuild-root.sh 16`。

## 坑
- 多文件补丁改动后要把它碰的所有文件一起还原再重打；改补丁别插在别的补丁 hunk 紧邻处。
- 不要用 `pkill -f`/`pgrep -f`（会匹配自己所在 shell）；监视构建用进程退出或完成标记文件。
- 宿主 `/` 空间极紧（约 4 GB 空闲）：写满会产生 0 字节生成文件并带来一串假错误；`artifacts/27.0.1/os.raw`（14 GB）和 `systemos.img`（8 GB）是可删但需重下的大头。
- Wi-Fi adb 会掉线，`adb connect` 重连；宿主大页池不足时降低内存。

## 2026-10-24 进展
- launchd 稳定：沙盒不匹配（临时忽略）、NativeVirtioBlock 超时/串行发布、KC `__DATA_CONST` 余量均已修，详见 docs/xnu-12377-port.md 里程碑 5。
- 内核改动已按修复拆成 7 个补丁并提交：`patches/xnu-12377/`（0001~0006 修复，0007 诊断：`stderr-log`、`sc-trace`、`sc-trace-all`、`iokit-log`、`crash-log`、`sample-pid`），macos 仓库 `c467247` → `9122607`（重新导出）。NativeVirtioBlock 补丁 `overlay/kext/NativeVirtioBlock.patch`（`d8df647`）。
- 待验证：当前补丁版本（去掉调试代码 + `iokit-log` + `sc-trace-all`）还没做一次完整重编 + 烟测，开始 GPU 工作前先跑一次确认能到 WindowServer。
- 当前重点只做 WindowServer / GPU，路线 B（客户机走 Droid-VM 驱动），显示走 IOMFB（DroidVMDisplay，照 vma2 的 AppleParavirtDisplay；IOFramebuffer 只作备用），单独的计划在 **docs/TODO-gpu.md**。
- 只记录、暂不处理：xprotectd(1)、fskitd(1, "error starting up the daemon")、digest-service(1)、apsd(NSException)、endpointsecurity(35)、xpcproxy(78)、Data 卷部分路径 Read-only。
- KC 保留列表：`/tmp/keep4.txt` = keep3 + `com.apple.iokit.IOHIDFamily`（/tmp 是 tmpfs，重启会丢，要落到仓库里）。

## 2026-10-24 补丁版重编烟测
- 当前补丁版（9122607）完整重编通过。`kc-try.sh` 现在默认读 `configs/kc-keep.txt`（= 旧 /tmp/keep4.txt）、默认 NATIVE=VirtioBlock+AES+RamBlock、默认 `MACOS_LP_SIP0=0x2`（漏设时 launchd 报 "dyld cache vnode is not SIP-protected"、libSystem 加载失败）。
- 带 SIP0 的一次 360 s 烟测：launchd 起到 pid ~236，约 1 分钟后 panic `"unexpected destruction of builtin profile" @builtin.c:192`（Sandbox kext）。之前没见过，疑与 permissive 下忽略 call 0/1 的处理有关（内置 profile 引用计数被多放一次）；没看到 WindowServer。只跑了一次，是否稳定复现未知。
- 用户要求：不要动不动上机烟测，集中改完一批再测。

## 下次上机（等用户连好设备再做）——一次跑完这一批
1. 确认手机 crosvm 的 droidvm-gpu wire：`adb shell su -c "strings <App 的 crosvm-mmio 路径> | grep -c 'lost its GPU context'"`，0 说明是 wire 1，要用 external/crosvm 的 `droidvm/wip/virtio-mmio`（wire 3）重编、部署后再测。最终以客户机日志为准（版本不对会打印 "droidvm-gpu: unusable device facts"）。
2. `python3 scripts/build-droidvm-gpu.py`（已编好）；内核已带 call 68 修复、补丁 0007、`sample-name`（out/x12377/kernel12377e-osx-kc.macho 03:38）。
3. `MACOS_GPU=1 python3 scripts/droidvm-app.py register` → `prepare`（新模板带 --droidvm-gpu，重新 dump FDT）。
4. `MACOS_GPU=1 TAIL=80 scripts/kc-try.sh 360 rootauth=0 crash-log=1 iokit-log=WindowServer sample-name=WindowServer sample-period=60 drop:...`（drop 列表同前）。看：`droidvm-gpu: self-test passed`、syspolicyd 的 `call 68 skipped`、不再出现 builtin profile panic、WindowServer 的 sample 栈（pc 所在的缓存镜像用 out/dsc 的 .map 换算）。
5. 显示走 IOMFB（docs/TODO-gpu.md 第 3 步）：DroidVMDisplay 阶段 1 已写完、KC 链接通过。先按第 4 步跑一次（不开显示，确认零显示器空等），再 `MACOS_DISPLAY=1` 重新 register/boot（ADT 加 `/arm-io/display`）+ `MACOS_DISPLAY=1 scripts/kc-try.sh ... iokit-log=WindowServer`，看：`DroidVMDisplay: AppleParavirtGPU on`、`scanout`、`started, display 1280x800`、`surface ...`（首帧参数），WindowServer 是否不再空等、simplefb 上有无画面；失败时按日志定位是 start / start_hardware / 定时器 / 呈现哪一步。IOFramebuffer 备用路线默认关（`MACOS_IOFB=1` 才加 ADT 节点和 personality），本轮不开。
- 另记：上次 panic 报告的 zone 泄漏 `kalloc.type.var7.4096` 846 MB 来自 NativeRamBlock（Data 内存盘写入），内存紧时 memorystatus 在杀进程（ReportCrashService），可能影响 WindowServer。
