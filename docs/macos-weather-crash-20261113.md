# macOS Weather 闪退调查（2026-11-13）

环境：macOS 27.2 (26B8125)，DroidVM / Adreno 830，NativeAdrenoMetal + metal2vulkan。

当前状态：原启动崩溃已有代码修复。关闭天气动态背景仅是临时绕过，用户要求恢复默认云层动画并修复显示与性能；现已删除天气静态背景覆盖，系统减少动态效果保持原状。默认背景下前台持续渲染及 CPU 占用仍在调查，不能把禁用动画后的 0% 视为 GPU 修复。

## 已确认原因

1. 原版 Weather 的天文背景创建 XR10 CAMetalLayer 时抛出 `CAMetalLayerInvalid: unsupported extended range format`。NativeMetal 的 iOS 显示策略将 `supportsExtendedXR10Formats` 对大部分进程强制设为 false，误伤了 macOS 应用。macOS 构建脚本现仅对 WindowServer 保留 8-bit scanout 限制。部署后原版 Weather 已进入 `NUNIAstronomyVistaView:startAnimation`，原格式异常消失。代码提交：macos `ccd1a6a`。
2. 进入背景渲染后，渲染管线编译报 `NeedsInput(FunctionConstant)`，包括 `bloom_threshold` 的 20301 等索引，最终触发 `VFX/Bloom.swift:141: Fatal error: missing bloom_threshold`。NativeMetal 已为计算管线实现保留显式常量、对剩余读取补零后的重建，但渲染管线没有该路径。已将同一处理接入渲染管线，保留调用者的显式常量和原始描述符，并确保重建函数存活至反射完成。代码提交：NativeMetal `c6fb605`。第二版重启后由 LaunchServices 打开原版 Weather，采样确认在 NativeMetal 渲染编码路径执行，越过 Bloom 崩溃点，持续运行超过 80 秒，无新增崩溃报告，最近 30 秒无 XR10、Fatal error 或 render pipeline refused 日志，CPU 回落至约 0.5%；画面和交互等待用户确认。

## 部署和证据

插件每次重建后需把 codesign 提供的签名标识加入启动 trust cache，否则系统程序无法通过库验证；这属于部署要求。当前 Data 盘保留，关机确认 `vfs_unmountall(system) end`、`CPU halted`，daemon STOPPED 后才替换 boot.img。

原始崩溃和首次编译记录：[初始采集](/tmp/weather-crash-analysis/)。后续镜像备份、部署和关机记录：[工作目录](/home/qiuqiu/weather-crash-work/)。记录只保留本地，不提交日志或诊断 JSON。

未增加测试代码，未进行烟测、截图或文件摘要计算。验证范围为原版 Weather 的启动和相关渲染崩溃。

## 尚存限制

管线反射仍有 `metal::rasterization_rate_map_data` 不支持的记录，当前未导致上述崩溃。启动时还会记录系统二进制 archive 被拒绝、若干 SPI 为 stub；不能据此宣称天气所有特效和渲染语义均已完整实现。

## 前台高 CPU 跟进

用户确认画面看起来正常，但活动监视器中的 Weather CPU 很高。重新激活窗口后，区间采样测得 Weather 143.9%–166.3%（100% 为一个核心）；原先约 0.5% 是空闲状态，不能作为前台性能结论。此项尚未修复。

通过 `open --env NATIVE_METAL_TIMING=1` 启用已有计时，不新增插桩。前 20 秒约 3780 次提交、28072 次绘制；60 秒时管线仍为 83 个，创建总耗时 163ms、library 98ms，无持续编译。函数创建却累计到约 537 万次，两个 `com.apple.vfx.runtime-thread` 持续执行 Catalyst VFX 的图编译/函数查找路径。采样同时包含 WeatherUI 动画渲染、drawable 等待及转译开销，不能把全部占用归因于某一缺失接口。

已知 `metal::rasterization_rate_map_data` 的管线反射拒绝、`__waitUntilCompletedAsync:` stub 等仍待核对，尚无证据证明其中任何一项直接导致重复函数创建。不要仅凭相关日志增加缓存、猜测反射或禁用动画来宣称修复。

采样：[highcpu2.txt](/home/qiuqiu/weather-crash-work/highcpu2.txt)；初次采样：[highcpu-sample.txt](/home/qiuqiu/weather-crash-work/highcpu-sample.txt)。采样过程不读取截图或 framebuffer。临时计时环境已撤掉。

### 函数常量反射（已部署）

IDA 分析 Catalyst VFX 的 `CFXGPUFunctionDescriptor finalizeForDevice:`：它先读取 `functionConstantsDictionary`，给必需常量填零，再复制调用者提供的命名和索引常量，最后用整理后的描述符查询 ShaderCache。此前 NBFunction 没有实现该 getter，消息转发返回 nil，VFX 因而清掉常量。NativeMetal `36514d3` 从运行时已有的函数常量信息生成 `MTLFunctionConstant` 字典，泛型函数延迟初始化，特化函数保持运行时的空字典语义。

第三版插件重启后正常打开原版 Weather，采样确认新 getter 被实际调用，原先该处的消息转发消失。但两个 VFX 线程仍持续整理管线，区间 `top` 测得 181.2%、209.2%，不能称为高 CPU 已解决。短时 `ps` 的 54.7% 同样不能代表稳定区间。证据：[highcpu4.txt](/home/qiuqiu/weather-crash-work/highcpu4.txt)。

进一步定位：`custom_mesh_vert` 的参数 10、`particle_quad_vert` 的参数 2 都因 `metal::rasterization_rate_map_data` 缺少反射支持而使整个渲染管线反射返回 nil；前端此时仍返回管线成功。IDA 中 VFX 的 RenderPipelineFactory 对成功但反射为空单独判失败。该路径正进行修复和对比验证，尚未证实它是持续重试的唯一原因。

### 上游仓库核对（2026-11-13）

按用户要求直接 fetch 并检查 Droid-VM/NativeMetal、UniXNU/AdrenoMetal（含 feat/macos）、steelbrain/metal2vulkan development，并通过 GitHub API 检查 UniXNU/Adreno740 与 Droid-VM/UniXNU-droidvm。未找到已验证修复 Weather 持续高 CPU 的提交或关联 issue。

- [UniXNU/AdrenoMetal 8c1ea13](https://github.com/UniXNU/AdrenoMetal/commit/8c1ea136d5f756944c14661bf65724cc7baca7ff)：已有函数常量反射、资源接口和若干 completion 入口补全。不能原样覆盖当前实现：其常量对象只声明 `isRequired` getter，而本机 SDK 和 IDA 中 VFX 调用的是 `required`。当前实现保留 `required` 并缓存同一函数对象的字典。该提交没有实现本次日志中的 `__waitUntilCompletedAsync:`。
- [Droid-VM/NativeMetal 3c46b5e](https://github.com/Droid-VM/NativeMetal/commit/3c46b5eaeafc416a75ce3d1ea5d11aa018a4049e)：计算管线补零重建函数必须活到反射读取结束，修复释放后访问；上游记录 cameracaptured 崩溃消失。当前 macOS 分支尚未引入，属于值得单独移植的真实生命周期修复，不是 Weather 高 CPU 的验证结论。
- [metal2vulkan 9c80a4957](https://github.com/steelbrain/metal2vulkan/commit/9c80a4957b8d616b27b37b30f9d354d5f0e1c9c3)：处理未设置函数常量，移除 NeedsInput(FunctionConstant) 拒绝，包含 Apple M3 的观测。当前固定点 624bab391（2026-10-29）不含此提交。升级涉及语义/API 与缓存版本，不能当作单个前端补丁直接套入。
- [UniXNU/AdrenoMetal c135133](https://github.com/UniXNU/AdrenoMetal/commit/c1351337d7e4ca00c80e1b7efeaf404bddc1be9e)：Turnip 管线在请求线程创建，降低线程切换等待；证据是 macOS 27.3 sheng 的管线创建延迟，不是持续 VFX 函数查找。当前采样创建管线已停增时仍高占用，优先级低于反射失败。

已获取 metal2vulkan development 7ef17497d（2026-11-12），源码 `reflection/derive.rs` 的 size_align 与 pointee 仍在缺少元数据/未知数据类型时拒绝，无 rate-map 专门支持。UniXNU/AdrenoMetal main 73d582f 也仍会在反射失败时返回管线成功、反射 nil。

Adreno740 的 653e11c8 为 GPU fence 完成精确唤醒、5559e982 为仅映射 mailbox 时才 poll；它们针对原生 Adreno 驱动，不能直接当作当前虚拟 GPU 路径或 Weather VFX 线程的修复。

检查上游只更新远程引用，未整体替换本地分支。第四版 rate-map 反射候选已部署，但用户转向上游检查时尚未完成性能验证；当前 Weather 已退出，不能宣称候选解决了高 CPU。


### DroidVM + UniXNU integration trial (foreground high CPU persists)

The user authorized an upstream integration trial. Work is isolated from the dirty macOS checkout on branch `integrate/droidvm-unixnu-gpu-20261113`. NativeMetal first merged DroidVM `wip/hackintosh` at `312cde5` (merge `29e9e4b`), then merged UniXNU AdrenoMetal `feat/macos` with conflict resolution (merge `646a4bc`). This uses a merge so both upstream histories and the existing macOS crash fixes remain visible.

The translator is a separate worktree at the upstream-compatible pin `555b13d57e09bff70996a88cff64f1275256d5cf`, with the new NativeMetal patch stack, including consolidated runtime patch 0040 and asking-thread compilation patch 0041. The old DroidVM board patches are not appended to this stack. The rate-map reflection candidate is excluded from this first comparison.

Conflict resolution preserves the virtual GPU display-hold and IOSurface access tickets, scheduled-handler pacing, indirect command and argument-buffer entry points, cached function-constant reflection with the `required` getter, and precise function lifetime through reflection. Resource entry points now acquire the upstream live-resource guards; texture resource IDs pin their backing, as buffer GPU addresses already do. Obsolete memory-pressure wrappers were replaced by upstream purge handling. WindowServer is recognized as the render server, and is excluded from application scheduled-handler pacing.

The macOS build retains its XR10 restriction only for WindowServer and its video-plane lifetime fix. For video formats 500/505/540/543, it bypasses the CPU conversion when planes are read in place, avoids holding decoder surfaces for the entire texture lifetime, and holds them only between command submission and completion. Build outputs and observations remain in the local work directories. No smoke suite, extra test code, screenshot, framebuffer read, or checksum verification is used.

Both the arm64e Rust release build (fat LTO) and Objective-C++ plugin build/link passed. The macOS build adaptation is commit `2817ff9` in `/home/qiuqiu/crosvm/macos/out/gpu-integration`; NativeMetal is in `/home/qiuqiu/weather-crash-work/NativeMetal-integrated`, and the dedicated patched translator in `/home/qiuqiu/weather-crash-work/metal2vulkan-integrated`. Both repositories use the isolated integration branch; the original working branches were not moved.

The plugin was deployed with a new trust-cache module and boot image. The prior guest completed `vfs_unmountall(system) end` and `CPU halted`; the daemon reported STOPPED before replacing boot.img. Data was untouched. After restart, `lsof` confirms WindowServer loaded the new 31,937,632-byte plugin and the existing Turnip library. This establishes loading, not Weather correctness or a CPU improvement. WindowServer and loginwindow are alive, but no Finder/user session is available yet. The user has been asked to unlock the guest; foreground verification remains pending. The preceding guest was also locked during the attempted baseline, so its low Weather CPU is invalid as a foreground result.

Only code and documentation were committed. The patch files have upstream context lines that `git diff --check` interprets as trailing whitespace; they are preserved as patch data. The source checks excluding patch payloads passed. The imported upstream verification sources were not run, and no new test code was authored.

Build commands (the first bridge build applies the full patch stack; reuse requires the PREPATCHED flag):

```sh
cd /home/qiuqiu/crosvm/macos/out/gpu-integration
NATIVE_METAL_SOURCE=/home/qiuqiu/weather-crash-work/NativeMetal-integrated \
METAL2VULKAN_SOURCE=/home/qiuqiu/weather-crash-work/metal2vulkan-integrated \
METAL2VULKAN_PREPATCHED=1 python3 scripts/build-metal-bridge-macos.py
NO_STAGE=1 NATIVE_METAL_SOURCE=/home/qiuqiu/weather-crash-work/NativeMetal-integrated \
bash scripts/build-metal-plugin.sh --no-deps
```

The bridge's first successful build ran before the macOS worktree was moved into the linker container's bind mount. Its archive was then linked from the final path. Changing the runtime source requires a fresh `NMB_RUNTIME_ID` label for shader-cache separation; no checksum is computed by this integration build script.


#### Foreground verification after unlock

The user unlocked the guest. Initial readings of 1.2–1.9% were discarded because Activity Monitor was frontmost. Weather was then activated and its bundle identifier checked before each interval and after the final interval; all four checks returned `com.apple.weather`. Five-second interval readings were 190.5%, 163.2%, and 94.6%. The process remained alive, but upstream integration alone did not resolve the high CPU.

The timing log still reports render-pipeline reflection refusals. At the captured table, pipeline creation was 149 calls/231 ms, library creation 23 calls/102 ms, and function creation 688,658 calls/1,278 ms. An active sample again shows both VFX runtime threads repeatedly processing graph/function lookup and function constants. Background samples show those same threads waiting on a condition variable, explaining the misleading low CPU when Weather loses focus.

Evidence: [foreground intervals](/home/qiuqiu/weather-crash-work/weather-upstream1-foreground.txt), [active sample](/home/qiuqiu/weather-crash-work/weather-upstream1-active-sample.txt), [background sample](/home/qiuqiu/weather-crash-work/weather-upstream1-sample.txt). These are local diagnostic artifacts, not committed files.

The next candidate adds only the existing rate-map reflection patch to the integrated runtime: recognize the opaque `metal::rasterization_rate_map_data` parameter, use the runtime's own parameter-data size/alignment, and expose an opaque struct instead of rejecting the entire pipeline reflection. It does not disable Weather animation or add an application-specific path. Runtime cache label: `weather-upstream-rrm-20261113`. Build and hardware comparison are pending.


A later warmed foreground interval measured 200.4% and 213.0%, with Weather frontmost at both ends. Pipeline/library counts stayed at 149/23, while function creation rose from 6,023,699 to 7,179,752 between the last two timing tables. This rules out one-time pipeline creation as the sustained CPU source in this trial. See [late intervals](/home/qiuqiu/weather-crash-work/weather-upstream1-late.txt) and [full timing log](/home/qiuqiu/weather-crash-work/weather-upstream1-timing.log). Weather was quit after baseline collection while the rate-map candidate builds.


#### Rate-map candidate on the integrated runtime

The rate-map candidate built successfully with the same arm64e release profile and plugin link. Its patch is [0003-rate-map-buffer-reflection.patch](/home/qiuqiu/crosvm/macos/out/gpu-integration/patches/metal2vulkan-macos/0003-rate-map-buffer-reflection.patch), applied after NativeMetal's patch stack. The source recognizes the canonical opaque AIR type and derives its size/alignment from `RasterizationRateMap`, whose existing ABI documentation records Apple's 24,624-byte parameter data. Unknown types retain the existing refusal behavior.

The candidate has been deployed with its matching trust module and `boot-upstream-rrm.img`. Shutdown records confirm both system unmount completion and CPU halt, and daemon STOPPED before boot replacement. Data remains untouched. The guest is restarting and the user has been asked to unlock it again for a foreground comparison. The candidate patch and its build-script entry remain uncommitted until relevant runtime verification; no high-CPU fix is claimed.


After the rate-map candidate restart, SSH is available and WindowServer PID 168 has loaded the new 31,937,952-byte plugin and Turnip. Finder is not running yet (no logged-in desktop). Foreground verification is blocked on the requested user unlock, not on compilation or plugin loading.


#### Verified rate-map improvement and remaining reflection gap

After user unlock, Weather was restarted with the existing timing instrumentation. Frontmost checks before all three initial intervals and after the last returned `com.apple.weather`. CPU was 39.7%, 44.0%, and 43.7%. A later pair with Weather frontmost at both ends was 14.5% and 44.3%. These compare with the integrated baseline's warmed 200.4% and 213.0%, but differing Weather animation states mean the intervals are not a controlled frame-for-frame benchmark. No crash occurred during this verification. The rate-map fix was immediately committed as macOS `a80044a` on the isolated branch.

Function creation is greatly reduced but persists: the candidate's later timing tables show 49,915 then 60,512 calls, with pipelines/libraries stable at 88/10. The rate-map rejection no longer appears in the full remaining refusal messages. Enabling the existing public unified log via `SHENG_LOG_GPU=1` reveals the remaining failure: `REVFXLightConstantBuffer_s`, argument 10 of WeatherUI's `vfx_custom_shader_WeatherV136DefaultBackground_shader_227::vfx_fragment`.

The WeatherUI metallib was copied read-only and its fragment AIR disassembled with LLVM. Its global argument-buffer member `lights` points at that type, but the indirect argument metadata declares neither size/alignment nor struct layout. The entry does not read the global buffer in its body. Similar omitted metadata exists for `REVFXClippingConstants_s`. This differs from the canonical rate-map type, whose runtime ABI is already defined: assigning guessed dimensions or an invented empty layout to these ordinary unknown structs is not justified. The remaining reflection issue is open; a correct general treatment of unread argument-buffer pointers needs Metal reflection evidence or a compatible implementation.

Evidence: [candidate foreground intervals](/home/qiuqiu/weather-crash-work/weather-upstream-rrm-foreground.txt), [later intervals](/home/qiuqiu/weather-crash-work/weather-upstream-rrm-late.txt), [active sample](/home/qiuqiu/weather-crash-work/weather-upstream-rrm-active-sample.txt), [full reflection refusals](/home/qiuqiu/weather-crash-work/weather-rrm-reflection-detail.txt), [fragment AIR](/home/qiuqiu/weather-crash-work/weather-fragment.ll). Logs, extracted binaries, and disassembly remain local and are not committed. Temporary timing/unified-log environments were removed by quitting Weather and opening it normally again; Weather was left activated.


#### Remaining CPU: encoding placement and resource lifetime

A normal foreground launch after the rate-map fix measured 45.6% and 50.3% CPU. The main/UI thread mostly waits; active stacks traverse VFX render work, NativeMetal encoding, Vulkan draw lowering, resource imports/releases, and synchronization. CPU charged to a VFX thread includes runtime calls made on that thread; it is not an attribution of all that time to Apple's code. Function-creation timing alone grew by only 45–57 ms per 20-second interval (about 0.23–0.29 CPU percentage points); this counter does not include every function-reflection/dictionary operation.

The existing `NATIVE_METAL_FLOW` setting permits a process-local comparison: default 7 enables worker render lowering; 6 keeps the same commit submission and pipeline warmup settings but lowers render calls on the caller. No code or global default was changed.

| Mode / interval | Process CPU | Command buffers/s | Render passes/s | Draws/s | CPU µs/draw |
| --- | ---: | ---: | ---: | ---: | ---: |
| Worker, first run | 47.07% | 120.0 | 449.9 | 2969.1 | 158.5 |
| Caller, first interval | 37.74% | 120.0 | 449.9 | 2969.4 | 127.1 |
| Caller, next interval | 37.54% | 120.0 | 450.1 | 2972.1 | 126.3 |
| Caller, next interval | 38.30% | 119.6 | 448.6 | 2960.1 | 129.4 |
| Worker, repeat first interval | 38.58% | 113.2 | 422.9 | 2802.3 | 137.7 |
| Worker, repeat next interval | 38.38% | 69.0 | 258.6 | 1708.8 | 224.6 |

These are thread-CPU deltas over approximately 20 seconds, with Weather frontmost at the measurement endpoints. CPU µs/draw is a workload-normalized proxy, not isolated draw-call cost: it includes all process work. The worker repeat changed cadence and narrowed the first comparison, so the data do not establish a stable 25% saving or justify a global default change. In the first worker interval, the two VFX threads consumed 6,758 ms and the lowering worker 1,559 ms of 9,416 ms total process CPU. Caller intervals consumed about 6,233–6,637 ms on VFX threads with no worker encoder ends.

The code explains a possible overhead: worker mode checks and logs calls, retains their objects, hands batches to another thread, then replays lowering. Opening the next encoder calls `settle_ended`; `LoweringSlot::drain_locked` waits for an active batch and lowers untaken work on the caller. The active sample contains this path and worker buffer-placement lock waits. Weather's many small passes (about 6.6 draws/pass in the first comparison) are a plausible poor fit, but the worker also serves WindowServer latency and cannot be removed solely from this app's CPU result.

During another restart, the old Weather PID 2437 stayed in exiting state and a new instance waited in AppKit's display-information request to WindowServer. WindowServer's sample traversed `new_buffer_with_bytes_no_copy` → `allocate_memory` → Turnip `darwin_bo_init_host`, with both `darwin_reap_locked`/`darwin_release_native` and new-buffer creation in IOKit calls. WindowServer later progressed and the new Weather instance initialized. This establishes a temporary resource-lifetime/import stall, not a proven deadlock or its root cause. The zero-CPU startup intervals are excluded from the CPU comparison.

Evidence: [normal CPU](/home/qiuqiu/weather-crash-work/weather-remaining-cpu.txt), [normal sample](/home/qiuqiu/weather-crash-work/weather-remaining-sample.txt), [worker timing](/home/qiuqiu/weather-crash-work/weather-flow7.txt), [caller timing and sample](/home/qiuqiu/weather-crash-work/weather-flow6-sample.txt), [worker repeat](/home/qiuqiu/weather-crash-work/weather-flow7-repeat.txt), [WindowServer during restart](/home/qiuqiu/weather-crash-work/weather-exit-windowserver.txt). All raw evidence remains local. Priorities are to separate handoff/replay overhead from useful lowering, investigate imported-buffer retirement latency, and resolve the ordinary unknown-struct reflection gap with ABI evidence.


The final caller repeat is also invalid as a steady-rendering measurement: Weather was frontmost at both endpoints, but telemetry still showed zero render draws, with only 10 command buffers and 3 render passes at the final table. A frontmost bundle check alone is insufficient during a stalled startup. See [repeat after display request progressed](/home/qiuqiu/weather-crash-work/weather-flow6-repeat-active.txt). No new performance claim or default-policy change follows from this repeat. The earlier table remains the usable evidence.


#### Post-reboot measurements

The user rebooted and unlocked the guest. A normal foreground launch rendered again, with 5-second CPU intervals 61.5%, 54.0%, 49.8%, and 45.0%. The request stall from the previous session is not reproduced by this run. A read-only host-side read of the existing driver counters found 142,858 completed commands, zero command errors and zero timeouts. The recent slow-operation records included Weather 64–80 MiB allocations taking 68–110 ms, of which 39–87 ms was guest-page preparation. These counters establish this boot's state, not the cause of the earlier stall.

A new pair using identical launch arguments (`-ApplePersistenceIgnoreState YES`) had a different, substantially busier scene than the earlier 120-command/s pair:

| Mode | Interval | CPU time | Commands | Render passes | Draws | CPU µs/draw |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Caller (FLOW=6) | 20.001 s | 22,456 ms (112.27%) | 7,972 | 34,769 | 115,365 | 194.7 |
| Default worker | 20.005 s | 24,347 ms (121.70%) | 7,222 | 33,407 | 113,559 | 214.4 |

Both modes performed real rendering and ended with Weather frontmost. Draw volume is close, but render-pass/dispatch mixes still differ: these are not deterministic replay measurements. The approximately 9% lower CPU/draw in caller mode supports investigating logging/handoff overhead; it does not show that all applications or compositor latency improve if the worker is disabled. Default behavior is retained. Function creation consumed 119/117 ms in those respective intervals, about 0.6 CPU percentage points. A temporary mode's raw CPU cannot be compared with the prior 45% scene without counting its work.

Evidence: [normal launch and sample](/home/qiuqiu/weather-crash-work/weather-reboot-active.txt), [caller comparison](/home/qiuqiu/weather-crash-work/weather-reboot-flow6.txt), [default comparison](/home/qiuqiu/weather-crash-work/weather-reboot-default.txt). No new code fix is established by these measurements. The ordinary-struct reflection refusal remains unresolved; no unknown layout is fabricated.


#### Function-constant metadata reuse candidate

IDA inspection of VFX ShaderCache at `0x1D9DAA3A0` shows cached pipeline/reflection/error outcomes. Its synchronous Metal call at `0x1D9793274` requests options 3 (or 7 with archive failure enabled), including buffer type information. The internal boolean passed to ShaderCache is not Metal pipeline options. Skipping recursive types merely because only argument information was requested would therefore not address this caller. Remaining reflection refusals occur at startup; warm pipeline creation counts stay fixed. They are not established as the cause of sustained CPU.

A foreground baseline with normal saved state and default worker policy held at 47.1–52.5% CPU. Two consecutive telemetry intervals report 9,762 ms / 20.010 s and 10,080 ms / 20.009 s CPU; each performs 2,400 command buffers, 9,000 render passes and 59,400 draws. Pipeline count stays 89 while function creation increases by 13,200 each interval. Function-construction timing excludes the subsequent constants dictionary getter, which appears in active VFX stacks.

The candidate shares immutable unspecialized function-constant dictionaries per library and source function. Specialized functions retain the runtime contract of an empty dictionary. It avoids repeated bridge JSON generation, JSON parsing and Objective-C constant objects without sharing mutable function wrappers. The plugin build passed using `NO_STAGE=1 NATIVE_METAL_SOURCE=/home/qiuqiu/weather-crash-work/NativeMetal-integrated bash scripts/build-metal-plugin.sh --no-deps`. No new tests, checksums or smoke tests were added or run. Runtime benefit remains unverified.

The guest completed system unmount and CPU halt, and the daemon reported STOPPED before boot replacement. Data is preserved. Evidence: [baseline](/home/qiuqiu/weather-crash-work/weather-constants-before.log), [active sample](/home/qiuqiu/weather-crash-work/weather-next-sample.txt), [shutdown](/home/qiuqiu/weather-crash-work/shutdown-constants-cache-kernel.txt).

After restart, SSH is available and WindowServer maps the new 31,752,544-byte plugin plus the unchanged 17,693,480-byte Turnip library. No user desktop or Weather process is present yet. Foreground validation and a verified-fix commit are pending unlock; deployment alone does not establish a CPU reduction.


#### Foreground issue remains open

The user corrected the apparent success: low CPU was observed with Weather in the background. A new foreground sample of PID 1058 confirms sustained activity; 3-second top intervals include 45.8% and 50.4% CPU with `com.apple.weather` frontmost. The previous 0.7–1.7% readings were taken with Activity Monitor frontmost and a different Weather PID. They are not a successful foreground verification. The function-constant dictionary candidate remains uncommitted and is not classified as a high-CPU fix.

The current sample repeatedly enters `render_command_encoder` → `settle_ended` → deferred `Batch::lower` → `draw_primitives` → `draw_resident`. Much of what appears below encoder creation is completion of the preceding pass's queued draw work, not the cost of creating an encoder itself. Inside draw lowering, binding generation, upload placement, render-state preparation and Vulkan draw recording all appear. Existing code already memoizes views/samplers, copies inline bytes at the Metal setter, and suppresses equal Vulkan pipeline/descriptor/dynamic state where supported. An extra blanket binding cache would need to preserve resource mutation, residency and writable-sink semantics; the sample alone does not establish that such a cache is the correct fix. No new runtime change is made from this observation.

Evidence: [foreground CPU](/home/qiuqiu/weather-crash-work/weather-foreground-current.cpu), [foreground sample](/home/qiuqiu/weather-crash-work/weather-foreground-current.sample). No additional smoke tests, test code or checksum computation were performed.


#### Reduce Motion diagnostic

At the user's request, `com.apple.universalaccess reduceMotion` was temporarily enabled. Its original key was absent, recorded in guest `/private/var/tmp/weather-reduceMotion-original.txt`; restoration means deleting that key, not forcing a new permanent false value. A fresh AppKit NSWorkspace query reports true. Weather was relaunched after the setting changed, because the existing process might only read the preference during initialization.

The new Weather PID 2071 remains frontmost and continues rendering: 5-second CPU intervals 34.6–41.3%, with a complete telemetry interval of 7,684 ms CPU / 20.006 s (38.41%). Over that interval there are 2,403 commits, 4,808 render passes and 49,281 draws; pipeline creation remains at 87. Recent four-command groups repeat at about 33 ms. Thus enabling Reduce Motion does not stop this client's continuous foreground rendering. The current groups have eight passes rather than the earlier fifteen, but differing scenes and launch states preclude attributing the entire difference to the preference. An NSWorkspace true result does not prove which UIKit/VFX accessibility branch Weather takes. There is no proof yet that the remaining animation is visually correct or that its rendering is required. The setting is left enabled temporarily as the user requested; this is a diagnostic state, not a fix.

Evidence: [CPU and telemetry](/home/qiuqiu/weather-crash-work/weather-reduce-motion-relaunch.txt).

#### Continuous rendering and the application's static-background switch

The first Reduce Motion attempt changed only AppKit's `com.apple.universalaccess / reduceMotion`. Catalyst's `com.apple.Accessibility / ReduceMotionEnabled` was still 0. After setting the latter to true, Weather's own logs explicitly report `Playback coordinator updated isFrozen state (reduce motion override)`. This confirms the accessibility branch, but foreground CPU remains 43.2% and four-command groups continue at about 33 ms. The earlier AppKit-only attempt therefore did not establish that Weather had disabled animation.

IDA analysis of Catalyst WeatherUI's playback coordinator at `0x2104D06D4` explains the remaining work: the accessibility override sets media timeScale to 0, but sets isFrozen according to whether the *requested* timeScale is 0. A play request of 1 consequently leaves isFrozen false even with simulation time stopped. VFXScene's corresponding setters at `0x1DA3A6144` and `0x1DA3A6244` store distinct clock-frozen and scheduler-timeScale fields. VFXView's continuous-rendering/display-link policy is separate. The evidence establishes application-requested paced rendering; it does not establish an unbounded GPU completion/invalidation loop or a need for guessed reflection layouts.

Weather has an existing static-background gate. `Settings.VFX.animatedBackgrounds` constructs the default-true boolean key `weather_vfx_animatedBackgrounds_enabled` (`0x210710A74`), and `WeatherConditionBackgroundModel.canShowAnimatedBackground` (`0x2107996C8`) checks that setting before allowing animated backgrounds. Setting it to false in Weather's sandbox preferences and relaunching removes continuous VFX rendering:

```sh
defaults write ~/Library/Containers/com.apple.weather/Data/Library/Preferences/com.apple.weather weather_vfx_animatedBackgrounds_enabled -bool false
```

The key was originally absent, recorded in guest `/private/var/tmp/weather-animatedBackgrounds-original.txt`. To restore the original animation policy, quit Weather, delete that key with `defaults delete` using the same domain path, and reopen Weather. This is an application preference workaround for static backgrounds, not a fix to animated GPU rendering or its remaining reflection limitations. No Apple binary or driver code was patched for this workaround.

Weather PID 3047 remained frontmost during initial 0.0% / 1.4% CPU intervals and a later pair of 0.0% intervals. Its command-buffer history remained at startup command K8 rather than increasing continuously. Both endpoints of the later measurement report `com.apple.weather`. Unlike the earlier background-CPU observations, this measures a foreground app after disabling the animation gate. Visual content and city-switch/scroll verification have been requested from the user. Evidence: [foreground static-background measurement](/home/qiuqiu/weather-crash-work/weather-static-foreground.txt); the guest timing log is `/private/var/tmp/weather-static-background.log`.

The user subsequently confirmed that content, city switching and scrolling are normal. Both global accessibility settings were restored to their original states: delete the originally absent `com.apple.universalaccess / reduceMotion` key and restore `com.apple.Accessibility / ReduceMotionEnabled` to false. AppKit reports Reduce Motion false. During settings changes and interaction there was transient 38–40% CPU, but subsequent foreground intervals settle to 0.0%, 0.1%, and 0.0%; process CPU time stays at 23.22–23.23 seconds, and the last render-history group is associated with interaction rather than continuous idle submissions. The remaining override is solely Weather's own background gate. Evidence: [restored global settings](/home/qiuqiu/weather-crash-work/weather-static-global-restored.txt), [post-interaction foreground intervals](/home/qiuqiu/weather-crash-work/weather-static-after-interaction.txt). The application preference stops the observed foreground idle load; preserving animated backgrounds with lower driver CPU remains separate unfinished work.

Finally Weather was quit and opened normally, without the temporary timing environment or stderr redirection. New PID 3261 remained frontmost at both measurement endpoints. Four 4-second CPU intervals all report 0.0%, with total CPU time 3.83–3.84 seconds; AppKit still reports Reduce Motion false. This verifies that the preference survives an ordinary app relaunch. Evidence: [normal relaunch](/home/qiuqiu/weather-crash-work/weather-static-normal-relaunch.txt). No new source code, tests, checksum computation, smoke tests or binary deployment were needed for the static-background workaround.


### Opaque indirect pointer reflection (candidate; default animation restored)

Default animated backgrounds are restored by deleting the Weather container preference `weather_vfx_animatedBackgrounds_enabled`. Weather PID 3638 was confirmed frontmost (`com.apple.weather`), with roughly 51–53% CPU in spot samples. Three initial render-pipeline reflection refusals name an indirect pointer without pointee metadata. They are startup failures, not continuous recompilation.

The Weather library contains an `RLST` section, per-function `RFLT` offsets, and serialized `AIRR` reflection in `RBUF` records. A local diagnostic passes the extracted fragment reflection to the guest system Metal class `MTLFunctionReflectionInternal` with `initWithDevice:libReflectionData:functionType:`; no GPU image or framebuffer is read. Native Metal returns seven bindings, preserving `material_params` (48 bytes, alignment 16, containing a float, float4 and texture). The indirect `lights`, `vrr_map`, `probes` and `clippingConstants` pointers report element type None, size 0, alignment 0, and nil elementStructType. Complete pointer metadata remains intact (for example, `ibl`: struct, size 144, alignment 16).

The translator instead recursively refuses the entire reflection at the first pointer lacking size/alignment. NativeMetal then returns a successful pipeline with nil reflection. IDA confirms VFX's `generateBindingsForPipeline:withReflection:program:materialIdentifier:overrides:` skips argument processing when reflection is nil. This establishes a reflection compatibility defect and a plausible missing-material path; it does not yet prove the cloud rendering issue is fully explained.

Candidate `0004-opaque-indirect-pointer-reflection.patch` preserves ordinary indirect pointers with no layout, size or alignment as Metal's None/0/0 representation. It does not invent an empty struct, skip whole bindings, or use application/type names. Partially specified metadata and nested argument buffers retain the existing refusal path. The existing top-level rate-map workaround is unchanged; the new rule also corrects opaque indirect rate-map pointers before that old special case.

Native evidence: [reflection output](/home/qiuqiu/weather-crash-work/weather-native-reflection.txt), [diagnostic source](/home/qiuqiu/weather-crash-work/inspect-native-reflection.m). Consumer binaries, reflection blobs, raw logs and diagnostic source stay local and are not committed. Deployment and visible cloud validation are pending.


Candidate deployment: release bridge build passed (6m39s), followed by `NO_STAGE=1 ... build-metal-plugin.sh --no-deps`. Patch reverse-application check and Python build-entry syntax check passed. The previous frontend constants-cache candidate remains unchanged, so this comparison isolates the new pointer-reflection rule. No additional test suite, smoke run, framebuffer capture or manual digest calculation was performed.

The current phone boot image was pulled and only its trust-cache payload updated with the codesign-provided identifier. The existing guest plugin was backed up, replaced via a sibling temporary file, and the guest shut down normally. Kernel output confirmed `vfs_unmountall(system) end` and `CPU halted`; the daemon then reported STOPPED before boot replacement. Data storage was not replaced. The guest is restarting; runtime and visible-result validation remain pending.

The immediate pre-deployment baseline was frontmost Weather at 52.4% and 51.1% CPU over two valid 3-second intervals (top's initial 0% is excluded), with approximately 30 frame groups/second and 78 draws per four-submit group. Evidence: [baseline](/home/qiuqiu/weather-crash-work/weather-clouds-before-pointer-fix.txt).


Runtime verification: commit `fec8a28` contains only the opaque-pointer patch and its build registration. Weather PID 868 was confirmed frontmost; the previous reflection refusals did not recur after warm-up, pipeline creation completed, and the process remained running. It still submits approximately 78 draws per frame group at 30 Hz. Three initial foreground intervals were 43.6%, 50.4%, and 49.0% CPU; this does not establish a meaningful performance improvement over the 51–52% baseline. The user-provided image still shows a smooth gray-blue background for cloudy Shanghai without discernible cloud shapes; motion cannot be inferred from one image. Cloud rendering remains unresolved.

Next diagnostic uses the existing bounded command-buffer trace, with a default-off `NATIVE_METAL_DUMP_TEXT_ONLY` return before any texture-readback command buffer is allocated. This is needed to inspect material bindings, viewports, blending and render targets without reading framebuffer/texture pixels. It does not change rendering policy or disable animation.


Text-only diagnostic deployment passed the frontend-only build and reused the already-built reflection bridge. It retains the existing render behavior; `NATIVE_METAL_DUMP_TEXT_ONLY` is checked after text emission and before creating the readback command buffer. The guest again shut down cleanly (`vfs_unmountall(system) end`, `CPU halted`), daemon STOPPED was verified, and the updated trust bundle was booted. Guest login is pending before bounded material/draw tracing. The diagnostic edit and the prior unverified constants-cache candidate remain uncommitted in the isolated NativeMetal worktree.


### Missing Metal binding protocol conformance

The text-only trace of Weather PID 1027 captured command buffers 1000–1007. The main 786×480 scene draws a skybox, then 24 particle draws with valid viewports and nonzero instance counts, then a post-process pass. Neither vertex nor fragment stage binds material buffer slot 2 on those particle draws, although the AIR declares the 176-byte `particle_quad_material_constants` at that slot. The command trace contains no texture pixel readbacks.

The unified VFX log contains 264 `bufferBinding is invalid <NBArgument material... type 0 index 2>` errors between 00:48:17.732 and 00:48:19.128 guest time. IDA disassembly at `0x1d9f0ae48` loads `protocolRef_MTLBufferBinding`, performs the Objective-C protocol cast at `0x1d9f0ae60`, and branches directly to that error at `0x1d9f0ae64` on failure. The same check exists for the vertex binding. The guest runtime independently confirms the old NBArgument class conforms to neither MTLBinding nor MTLBufferBinding.

The frontend implemented the getters but declared only `NBArgument : MTLArgument`; selector support is insufficient for Swift protocol casts. The candidate declares base MTLBinding conformance and creates separate buffer/texture/threadgroup subclasses with the corresponding protocols. The `type` getter uses MTLBindingType to match the protocol. No app or shader names decide behavior. Frontend build passed without warnings; deployment retains the text-only tracing switch for verification. Visible clouds and performance remain pending.

Evidence: [draw trace](/home/qiuqiu/weather-crash-work/weather-text-trace.log), [VFX errors](/home/qiuqiu/weather-crash-work/weather-text-trace-unified.txt). The runtime metadata diagnostic is local only and performs no rendering.


Protocol fix committed as NativeMetal `56044ae`, staging only the reflection class/factory changes and their README contract. The unrelated function-constants cache candidate and text-only diagnostic switch remain uncommitted. The deployed runtime metadata check confirms NBArgument conforms to MTLBinding, NBBufferArgument additionally conforms only to MTLBufferBinding, NBTextureArgument only to MTLTextureBinding, and NBThreadgroupArgument only to MTLThreadgroupBinding. Guest login is pending for Weather verification.

### Binding protocol validation and missing reflected argument encoder

Weather PID 1011 accepted the protocol fix: the previous `bufferBinding is invalid` errors did not recur, and bounded command-buffer text tracing now shows material slot 2 in both stages (288 binding lines). Warm foreground CPU intervals were 44.2%, 58.3%, 49.5% and 43.3%; a 20.004-second telemetry interval accounts for 9,340 ms process CPU, approximately 46.7% of one core. These numbers are not a like-for-like performance improvement: the recovered bindings also restore more draws. The nine-pass particle/bloom command belongs to a 177×72 sidebar preview, not the 786×480 main scene; the main scene still has two passes. The user-provided image still shows a smooth gray-blue sky without discernible clouds. Neither visible cloud animation nor performance is fixed.

Evidence: [protocol trace](/home/qiuqiu/weather-crash-work/weather-binding-protocol.log), [warm CPU](/home/qiuqiu/weather-crash-work/weather-binding-protocol-warm.txt), [stack sample](/home/qiuqiu/weather-crash-work/weather-binding-protocol.sample).

Weather was relaunched as PID 1331 with the text-only guard and a four-command capture, increasing the printed bound-buffer prefix from 32 to 64 words. Main-scene material constants include valid transform, UV and frame values, but bytes 144–175 (sampler, texture and two lighting-texture handles) are zero. The system Metal reflection reader independently confirms those offsets in the particle shader. The nested texture wrapper's storage member has relative argument index 0, matching the translator's representation; changing nested indices without evidence would be incorrect.

IDA finds `newArgumentEncoderWithBufferBinding:` calls in VFX's binding setup, including `0x1d9f0aac0` and `0x1d9f0aed8`. The frontend implements `newArgumentEncoderWithArguments:` and a function's buffer-index variant, but not the reflected-binding variant. A non-rendering runtime diagnostic creates a small NBBufferArgument and calls the missing device entry point. The guest prints `stubbed NativeBridgeMetalDevice newIndirectArgumentBufferLayoutWithStructType:` and `stubbed NativeBridgeMetalDevice newIndirectArgumentEncoderWithLayout:`, and returns `encoder=nil length=0 alignment=0`. This confirms a missing bridge entry point rather than a guessed cloud-shader defect.

The candidate retains each runtime BufferBinding behind its frontend object and calls the existing `Device::new_argument_encoder_with_buffer_binding`. It preserves the reflected offsets/strides and allows the binding to outlive the pipeline reflection, rather than repacking through descriptor arrays. It covers render and compute reflection. Build/deployment and actual Weather resource-write validation are pending; no performance or visible rendering claim follows from compilation alone.

Evidence: [material trace](/home/qiuqiu/weather-crash-work/weather-material-handles.log), [native particle reflection](/home/qiuqiu/weather-crash-work/particle-native-reflection.txt), [entry-point diagnostic](/home/qiuqiu/weather-crash-work/inspect-binding-encoder.m). Raw shader/reflection inputs and diagnostics remain outside commits.

Candidate build completed: release bridge in 3m14s and frontend/plugin build with no frontend warnings. The bridge reports only the pre-existing dependency-manifest `package.readme` inference warning. The attempted later baseline was at `com.apple.loginwindow` at both endpoints and is excluded from CPU comparisons. Guest shutdown confirmed `vfs_unmountall(system) end` and `CPU halted`; daemon STOPPED was verified before replacing boot. The updated trust bundle contains ten modules, using codesign's supplied identifier. Data was preserved. Runtime validation remains pending after restart.

### Runtime result: VFX's virtual-machine gate precedes encoder creation

After deployment, Weather PID 1105 is frontmost at both sampling endpoints. Four valid 3-second CPU intervals are 39.2%, 39.4%, 41.4%, and 42.6%. The loaded plugin UUID is `5D4E98E9-17C2-3BAC-A338-E4A99AAE009C`. The four-command text-only trace still shows zero sampler/texture handles in material bytes 144–175. Therefore the bridge candidate alone has **not** fixed Weather, and its runtime path has not yet been validated by this run. It remains uncommitted.

Further disassembly qualifies the earlier conclusion: the missing device API is a real independently reproduced defect, but VFX does not necessarily call it. VFX `sub_1D9D900D4` queries `kern.hv_vmm_present` and initializes `byte_1EE95B980` to true only if that query fails or returns zero. The current guest returns 1. Material setup at `0x1d9f0ae84` first checks `bufferPointerType.elementIsArgumentBuffer`, then at `0x1d9f0ae98–aea4` requires this global byte to equal 1 before creating the reflected argument encoder at `0x1d9f0aed8`. Otherwise it keeps bufferDataSize and an encoder of nil. Resource filling in `sub_1D9F11424` only enters the texture-setting branch when the material encoder returned by `sub_1D9F15DC8` is non-null. This is a framework virtualization gate upstream of actual resource writes; changing the translator's texture sampling would not repair an absent handle.

Evidence: [post-deployment CPU](/home/qiuqiu/weather-crash-work/weather-binding-encoder-first.txt), [bound material data](/home/qiuqiu/weather-crash-work/weather-binding-encoder.log), [loaded module](/home/qiuqiu/weather-crash-work/weather-binding-encoder.sample). One sample was taken only to identify the loaded binary; it is not a CPU profile.

The user authorized temporarily enabling development debugging, then restoring it. Both ordinary and privileged SSH LLDB attach, and debugger launch of the original application, were rejected by task_for_pid with the non-interactive authorization error. SIP is enabled and has not been changed. The user reported no authorization prompt from the attempted desktop Terminal route. `DevToolsSecurity -status` confirmed disabled after that attempt.

### Isolated VFX gate diagnostic (pending runtime verification)

A temporary Weather copy with its original restricted entitlements plus debugging entitlements was rejected by AMFI because it was ad-hoc signed. A copy with only public debugging entitlements and hardened runtime did launch under LLDB, but stopped in CloudKit initialization without the application's private entitlements. That copy cannot establish Weather rendering or CPU behavior. The diagnostic process was killed, LLDB exited, normal Weather reopened, and `DevToolsSecurity -disable` followed by `-status` again confirmed disabled. Neither SIP nor the global VM identity was changed.

The alternative diagnostic is a separate local object linked with the previously built Metal plugin objects. It is absent from the source worktrees and disabled by default. It requires both process name Weather and `NATIVE_METAL_VFX_ARGUMENT_ENCODERS=1`, then matches VFX UUID `B965ACAD-3FDE-3CAF-98BF-4A81868B7EC8`. It runs the original one-time initializer and changes only the current process's cached VFX argument-encoder flag to 1. The fixed addresses are deliberately limited to this diagnostic and must not be committed or shipped as a compatibility solution. The global `kern.hv_vmm_present` value remains 1. A normal Weather relaunch without that environment restores original behavior.

Build reused the existing plugin/frontend/bridge objects and added only [the local diagnostic](/home/qiuqiu/weather-crash-work/vfx-vm-diagnostic.mm). Linking passed. This is an experiment to distinguish the VFX gate from downstream encoder or shader defects; visible clouds and foreground performance remain unresolved. The original installed plugin is preserved in guest `/private/var/tmp/NativeAdrenoMetal-before-vfx-diagnostic`. Deployment uses the existing boot image with one extra trust module based on codesign's identifier, without computing a digest or replacing Data. Shutdown evidence records both `vfs_unmountall(system) end` and `CPU halted` in [the shutdown log](/home/qiuqiu/weather-crash-work/vfx-diagnostic-shutdown.txt).

Daemon STOPPED was confirmed before uploading `boot-vfx-diagnostic.img`; the resulting trust bundle has eleven modules. After restart, SSH is reachable, WindowServer is running, developer mode is disabled, and `kern.hv_vmm_present` is still 1. The console is owned by root, so foreground Weather validation awaits user login. The temporary debug copy is not running. No new production fix has been committed: the retained-binding encoder candidate still requires runtime verification.

### VFX gate experiment: resources and cloud shapes recovered

After user login, the original system Weather app launched as PID 800 with the opt-in diagnostic and text-only tracing. Its diagnostic line reports `argument encoders 0 -> 1`; the global VM sysctl remains 1 and developer mode remains disabled. Material bytes 144–175 now contain nonzero sampler and texture resource IDs, where the previous run was all zero. The loaded plugin UUID is `003093FD-86CB-34BB-9540-AD9948ECCB51`. The user confirms that clouds are now visible, but initially reports them as static. This establishes the missing-resource cause and recovery of cloud shapes; it does not establish correct visible motion or a completed production fix.

The retained-reflection argument encoder implementation is committed separately as NativeMetal `2fc55d5` (`fix(metal): implement reflected buffer argument encoders`), with only its code and README contract. Runtime evidence now exercises the path and shows resource writes; the unrelated constants-dictionary cache, text-only trace guard and temporary fixed-address diagnostic are not part of this commit. Evidence: [resource trace](/home/qiuqiu/weather-crash-work/weather-vfx-gate.log), [foreground intervals](/home/qiuqiu/weather-crash-work/weather-vfx-gate-first.txt), [sample](/home/qiuqiu/weather-crash-work/weather-vfx-gate.sample).

Valid initial foreground CPU intervals are 37.9%, 39.0%, and 38.1% of one core. This is not a demonstrated performance fix. Both endpoints of the later five-second sample identify Weather as frontmost. Sampling finds ordinary VFX frame production plus driver binding/lowering work; there is no basis to label all sampled waiting time as CPU use.

For the reported static clouds, Weather PID 1027 was relaunched with a bounded 160-command text capture and one detailed particle draw per pass. In consecutive main-scene commands 1002, 1006, 1010, 1014, and 1018, scene time advances from 2.664 to 2.798 seconds and material `uvScaleBias.z` advances from 0.01332 to 0.01399, approximately 0.005 per second. The source AIR uses this value in the vertex texture-coordinate calculation. The scene then changes render target and resets its clock during a city/scene switch, so those frames must not be treated as a stationary-scene comparison. The clock and input UV update are verified; visible motion still awaits confirmation over a longer observation of one city. No framebuffer or texture pixels were read. Evidence: [motion input trace](/home/qiuqiu/weather-crash-work/weather-vfx-motion.log).


### Post-reboot diagnostic restoration and async completion defect

After the requested reboot, normally launched Weather PID 451 had no `NATIVE_METAL_VFX_ARGUMENT_ENCODERS` environment value. Default animation preferences remained intact; the VM sysctl remained 1 and developer mode remained disabled. Relaunching the original app with the opt-in gate diagnostic as PID 830 restored nonzero material resource handles in the main 786×480 scene. The user again confirms cloud shapes but no visible movement. The gate experiment is process-local and is not a persistent compatibility fix. Evidence: [post-reboot bindings](/home/qiuqiu/weather-crash-work/weather-vfx-after-reboot.log).

A longer text-only capture from PID 949 shows main target t7293aa during commands 1500–1676: time 13.74–15.21 seconds, UV bias 0.06870–0.07604, with unchanged particle data in the captured prefix. Main-scene draws then disappear while sidebar scenes continue. Whether this coincided with user navigation is unconfirmed, so this is not yet evidence of an autonomous rendering stop. No pixels were read. Evidence: [long capture](/home/qiuqiu/weather-crash-work/weather-vfx-motion-stationary.log).

The Weather log also records a stubbed `NBCommandBuffer __waitUntilCompletedAsync:`. IDA of the system Metal implementation at 0x19416249c shows it appends a command-buffer callback to Swift concurrency waiters, or invokes it immediately if completed callbacks are already done. `didCompleteWithStartTime:endTime:error:` at 0x193fa6170 runs ordinary completed handlers, sets the completed-callbacks-done flag at offset 331, then delivers those waiters.

A bounded local diagnostic using an empty command buffer reproduces the defect in the installed plugin: status=4, ordinary completed handler=1, async=0, registration during completion=0, late registration=0; the async semaphore wait times out. This checks the actual completion API without drawing, screenshot capture, or texture reads. It is local diagnostic code, not committed test code. Evidence: [before result and codesign output](/home/qiuqiu/weather-crash-work/async-wait-before-and-codesign.txt), [diagnostic source](/home/qiuqiu/weather-crash-work/inspect-command-completion.m).

The candidate adds a separate waiter list and a completion-delivered state protected by the command buffer lock. After ordinary completed handlers run, it marks completion and detaches the pending waiters; late registration invokes its callback immediately. These waiters cannot use early render-server completion. The frontend-only build and link passed, retaining the existing runtime and opt-in VFX diagnostic object. Runtime validation and visible motion remain pending. No production fix is committed yet.

Deployment preserves the previous plugin as `/private/var/tmp/NativeAdrenoMetal-before-async-wait`. The current phone boot image was pulled in full; one trust-cache module was added from codesign's supplied identifier, producing twelve modules. Shutdown confirmed `vfs_unmountall(system) end` and `CPU halted`, followed by daemon STOPPED before replacing boot. Data was not replaced. Evidence: [shutdown](/home/qiuqiu/weather-crash-work/async-wait-shutdown.txt).


Post-deployment verification passed on the actual guest plugin: status=4, ordinary completion=1, async=1, registration during completion=1, late registration=1, timeout=0, exit=0. The previous stub message is absent. Developer mode remains disabled and the global VM sysctl remains 1. The defect fix is committed separately as NativeMetal `689d937` (`fix(metal): resume asynchronous command completion waiters`), containing only fifteen frontend lines and four README lines. The constants dictionary cache, text-only tracing guard, fixed-address VFX gate diagnostic, logs and local inspection program are excluded. Evidence: [after result](/home/qiuqiu/weather-crash-work/async-wait-after.txt).

SSH and WindowServer are up after the clean boot. Guest login is pending, so neither visible cloud movement nor foreground CPU improvement is claimed. The opt-in VFX argument-encoder gate remains necessary for the pending Weather comparison and has not become a production workaround.


### Continuous motion inputs and numeric GPU verification

After login, Weather PID 908 produced 452 main-scene frames while the user still reported static clouds. Foreground CPU remained approximately 62–65%; the async completion fix does not resolve visible cloud motion. Subsequent PID 3258 continues rendering with default animated-background preferences and the opt-in, process-local VFX resource-binding diagnostic. A temporary `caffeinate -di` prevents lock-screen changes during comparison.

The complete material trace covers main-scene command buffers 1001–1498 (786×480). Draw 2's UV bias changes from 0.04766 to 0.0695. Fixed UVs in other draws do not imply fixed geometry: a wider, text-only capture of draw 3 covers 253 main frames, command buffers 1503–2499, with scene time advancing approximately 2.742–11.51 seconds. Six particle X coordinates in slot 5, byte 1008 onward, change from `[-39.03, -25.92, -6.321, 12.92, 28.7, 47.53]` to `[-42.17, -32.9, -9.005, 8.345, 22.92, 42.42]`. Earlier short buffer prefixes were insufficient to establish whether those particles moved.

Two local GPU diagnostics read numeric buffer results only, without attachments, rasterization, framebuffer reads or texture-pixel reads. A uniform-buffer diagnostic passes all 32 reads across four binding offsets and eight updates. A second diagnostic retains the actual particle vertex AIR and redirects its returned clip position and UV to a writable numeric buffer. Reconstructed input values come from the four-significant-digit text capture, so this is not a bit-exact replay of the original pipeline. Both commands complete successfully; particle clip-X changes are approximately `[-13.08, -29.09, -11.18, -19.06, -24.09, -21.29]`, with valid positive clip W. This demonstrates motion through that vertex-computation path, but not through the original rasterization, blending or final presentation.

A transient `top` result of 0% was contradicted by active rendering stacks and subsequent 68.9% / 67.9% intervals. It is excluded as evidence of a stopped renderer or performance improvement. The sample includes substantial `CAMetalLayer nextDrawable` / `get_unused_drawable` / `allocate_drawable_texture` work and repeated IOSurface imports. A separate IOSurface-ID lookup did not obtain the target surface from another process, even as root; it provides no evidence about seed updates.

IDA inspection confirms VFXCoreView creates `CAMetalLayerRenderOutput`. At VFX address 0x1D9D9A4CC it acquires `nextDrawable` and registers a command-buffer scheduled handler; the handler reaches 0x1D9D90498, adds a presented handler and calls `presentAfterMinimumDuration:` when a preferred frame rate is set. The presented-time handler feeds optional statistics. Therefore a fixed main-scene IOSurface ID or a missing framebuffer-only flag does not establish that the scene bypasses CAMetalLayer. Actual drawable acquisition, submission and presentation still require correlation.

Evidence: [complete material trace](/home/qiuqiu/weather-crash-work/weather-all-material-motion.log), [wide particle trace](/home/qiuqiu/weather-crash-work/weather-particle-positions.log), [uniform numeric results](/home/qiuqiu/weather-crash-work/uniform-motion-gpu.txt), [particle numeric results](/home/qiuqiu/weather-crash-work/particle-motion-gpu.txt), [active sample](/home/qiuqiu/weather-crash-work/weather-async-stopped.sample), [surface lookup result](/home/qiuqiu/weather-crash-work/surface-seed-motion.txt). These diagnostics and raw inputs remain local and uncommitted. No production rendering or performance fix is established by this phase.


### Bounded drawable presentation trace (prepared)

A separate local Objective-C diagnostic hooks the actual QuartzCore `CAMetalLayer nextDrawable` and `CAMetalDrawable` presentation methods, recording only the first 1,600 acquisitions and their drawable IDs, IOSurface IDs, dimensions, layer visibility, presentation method and presented callback timestamps. It calls the original methods unchanged and does not inspect image bytes. This object is outside the source worktrees and is enabled only for Weather with `NATIVE_METAL_PRESENT_TRACE`; no production fix or diagnostic commit is made.

Compilation and plugin linking passed. The plugin retains the existing async-waiter fix and opt-in VFX gate experiment. The previous guest plugin is backed up at `/private/var/tmp/NativeAdrenoMetal-before-present`. A new boot image is based on the complete current phone boot image, appending a thirteenth trust module from codesign's supplied identifier. Data is preserved. The guest received `shutdown -h now`; the subsequent kernel message-buffer capture failed because the script used an incompatible reference-kernel symbol map, so `vfs_unmountall(system) end` and `CPU halted` were not verified in this round. The daemon subsequently reported STOPPED with exit code 0 before boot replacement. Presentation correlation remains pending runtime validation.


The thirteenth-module boot is running; SSH and WindowServer are available, while `/dev/console` is still owned by root. Weather has not been launched for the presentation capture, avoiding lock-screen measurements. Developer mode is disabled and `kern.hv_vmm_present` remains 1. The correct message-buffer reader input is `MACOS_KERNEL=/home/qiuqiu/crosvm/macos/out/k27/kc-k27.bin`; a read with that symbol map succeeds on the new boot. It does not retroactively verify the prior shutdown markers. User unlock is pending; no rendering fix or CPU reduction is claimed.


### Foreground presentation failure and image-queue metadata follow-up

The first bounded capture records 1,600 drawable acquisitions and 1,600 presented-handler calls, all with presentedTime=0. The main 786×480 layer submits 405 frames over 14.452 seconds: its first three IOSurfaces occur once each, then surface 40 is reused for 402 acquisitions. Main-scene command buffers 1203/1207/1211 write their second pass to surface 40, confirming that the rendered main scene is the CAMetalLayer output. A presented-handler invocation is not proof of display success.

The first capture was subsequently found with UserNotificationCenter frontmost and is excluded from strict foreground CPU comparison. A second run explicitly activates Weather through NSRunningApplication, avoiding System Events automation prompts, and confirms com.apple.weather frontmost at both sampling endpoints. It reproduces all-zero presentedTime for all 1,600 callbacks; the main layer acquires 429 frames over 15.215 seconds, reusing surface 39 for 426 frames after three initial surfaces. A valid foreground CPU interval is 70.6% of one core. The prior confirmed foreground interval was 47.9%; neither establishes an improvement.

Two process-local controls, CA_DISABLE_FIFO_IMAGE_QUEUES=1 and CA_DISABLE_PRESENT_ON_FINISH=1, do not recover nonzero presentedTime. The FIFO-disabled run still reuses one main surface for 427 of 430 acquisitions. CA_LOG_IMAGE_QUEUE_FRAMES=1 produces no matching queue-frame messages in the collected unified-log interval; absence alone does not establish the failure branch. The next local-only diagnostic records queue registration, shared-state flags and six slot metadata records at bounded intervals. No image data is read. It is intended to distinguish failure to insert from slots waiting for consumption, not to modify QuartzCore behavior.

Evidence: [initial presentation trace](/home/qiuqiu/weather-crash-work/weather-present-trace.log), [confirmed foreground trace](/home/qiuqiu/weather-crash-work/weather-present-foreground.log), [FIFO control](/home/qiuqiu/weather-crash-work/weather-present-nofifo.log), [queue-log capture](/home/qiuqiu/weather-crash-work/weather-image-queue.log). The new diagnostic compiles and links successfully. The guest plugin is backed up at /private/var/tmp/NativeAdrenoMetal-before-queue. Normal shutdown is now verified with both vfs_unmountall(system) end and CPU halted in [the kernel shutdown capture](/home/qiuqiu/weather-crash-work/queue-shutdown-kernel.txt); daemon STOPPED and exit code 0 were confirmed before the boot replacement. The complete current boot was preserved and a fourteenth trust module appended using codesign-provided signing metadata, with Data preserved. No new production fix is claimed or committed.

The fourteenth-module boot reaches WindowServer and SSH. Console ownership remains root with loginwindow running; the bounded desktop-wait helper expired without launching Weather, so no lock-screen render or CPU measurement is substituted for the pending foreground capture. Developer mode remains disabled and kern.hv_vmm_present remains 1. User login is required for the new queue metadata run.

### Image queues stop after three frames: surface-use lifetime candidate

After user login, Weather PID 1658 is confirmed frontmost at both sampling endpoints. The bounded metadata capture records all display queues stopping at sequence 3. The six-slot main queue has three occupied slots (2, 4 and 5), each remaining in status `0x11111111`; three empty slots are reserved, so subsequent insertion cannot proceed. Queue registration and context are nonzero and visibility is 1. Main queue flags are `0xa481000000008000`. All presented times remain zero; a valid foreground CPU interval is 49.7% of one core. The diagnostic's old `used` field is slot offset 32, the 0.008333333-second display interval, not a display count.

QuartzCore's consumer at `0x18DDDA830` and `did_display` at `0x18DE26064` check both a GPU frame counter and, when queue flag `0x0400000000000000` is set, `IOSurfaceIsInUse` before retiring a slot. The integrated frontend increments IOSurface use counts for the lifetime of cached WindowServer textures. The board build already counts in-place video imports per command instead, but leaves ordinary drawable surfaces lifetime-counted. This is a source-level explanation consistent with the stuck slots, not yet a demonstrated runtime cause; GPU counter conditions remain relevant.

The candidate generalizes the existing command-scoped counting to all compositor IOSurfaces and in-place-video clients. Counts begin in `commit` on the caller thread, before deferred encoding/submission, and end at actual completion or failed submission through the existing `finish` path. Cached compositor texture creation no longer increments its surface count. The bounded local diagnostic additionally records slot fence values and IOSurface use counts without reading image data. The frontend-only build (`NO_STAGE=1`, `--no-deps`) and local metadata-object link passed. Runtime verification is pending; no rendering or performance fix is claimed.

Evidence: [queue metadata capture](/home/qiuqiu/weather-crash-work/weather-queue-state.log). Online component-documentation access failed (Tavily transport error, direct HTTP 403); the available local UniXNU build, bring-up, Adreno and sheng documentation was used with the repository implementation and macOS build entry point. No raw capture or diagnostic code is staged.


The candidate executable is signed and installed, with the prior plugin retained at `/private/var/tmp/NativeAdrenoMetal-before-surface-inflight`. Normal shutdown is verified by `vfs_unmountall(system) end` and `CPU halted` in [the shutdown capture](/home/qiuqiu/weather-crash-work/surface-inflight-shutdown-kernel.txt), followed by daemon STOPPED. The complete 402,653,184-byte existing boot image is retained and a fifteenth trust module appended from codesign metadata; Data is preserved. No checksum command, image capture or texture-pixel read was used. The local VFX gate diagnostic remains opt-in and is not part of the production candidate.

The fifteenth-module boot is running. SSH and WindowServer PID 167 are available; the installed executable is 31,797,584 bytes. The console is owned by `_windowserver`, so Weather has not been opened for foreground validation. Developer mode remains disabled and `kern.hv_vmm_present=1`. User login was requested for the candidate comparison.


### Command-scoped surface counts: queue retirement verified

After the next user login, the restored Weather instance was stopped and relaunched with the same opt-in VFX argument-encoder diagnostic and bounded presentation trace. One transient LaunchServices error -600 occurred after termination; a subsequent launch succeeds as PID 1556. Weather is confirmed frontmost at both CPU-sampling endpoints.

The 786×480 main layer acquires 420 frames over 16.955 seconds, cycling IOSurfaces 22, 23 and 24 exactly 140 times each. Its queue sequence reaches 369 at trace acquisition 1400 and 419 at acquisition 1600, rather than stopping at 3. Retired slots clear their type and the remaining slots continue to update; IOSurface in-use states now become false between commands. This verifies the cached-texture surface-use deadlock is resolved. It does not yet prove visible cloud motion: all 1,600 presented-handler timestamps remain zero.

Four valid foreground CPU intervals are 48.8%, 47.4%, 46.7% and 46.4% of one core. The first top sample (0%, cumulative baseline) is excluded. CPU remains substantial; no CPU improvement is established against the previous 49.7% interval. The user was asked whether the main sky's clouds visibly move. That answer is pending.

The verified queue-retirement change is committed as macOS integration `4f77b11`, containing only `scripts/build-metal-plugin.sh`. Raw logs, boot images, metadata diagnostics, the VFX gate experiment and unrelated NativeMetal work are not staged. Evidence: [candidate queue/presentation metadata](/home/qiuqiu/weather-crash-work/weather-surface-inflight.log), [foreground CPU](/home/qiuqiu/weather-crash-work/weather-surface-inflight-cpu.txt).

The user confirms the main sky clouds now move. Visible cloud animation is therefore verified with the command-scoped-count fix plus the existing opt-in VFX argument-encoder experiment. The foreground CPU issue and production replacement of the VFX experiment remain open. A short stack sample shows VFX spending much of its sampled wall time waiting in nextDrawable; those waiting stacks are not evidence of consumed CPU. The sample also records successful ImageQueueDidComposite delivery and the loaded candidate UUID `7101D171-F9F1-3C46-B3A9-767C49C0E220`. Evidence: [stack sample](/home/qiuqiu/weather-crash-work/weather-surface-inflight.sample).


### Remaining CPU: work-placement control and running-only profile

With visible cloud motion recovered, Weather is relaunched without presentation hooks enabled and with the existing telemetry reporter. Warm default-flow tables show zero shader compilation requests. Three stable 20-second intervals consume 9,934 / 8,827 / 10,064 ms CPU; roughly 1,884–1,919 commands and 39,656–40,386 draws complete per interval. This is ongoing rendering work, rather than the former image-queue insertion failure.

A process-local `NATIVE_METAL_FLOW=6` control disables the runtime lowering worker while retaining commit submission and cache priming. Telemetry confirms both lowering counts remain zero; commands continue to complete without failures and the draw counts are comparable. Two warm 20-second intervals consume 8,784 and 9,280 ms CPU; top intervals range from 41.5% to 52.6%. The small, variable difference does not establish a reliable performance fix, so no scheduling-policy change is committed and default flow is restored.

A five-second `spindump -onlyTarget -onlyRunning -noBinary` then captures actual running stacks of the default configuration. VFX runtime threads account for 1.681 and 0.721 CPU seconds and the lowering worker for 0.760 CPU seconds in this instrumented interval. Those times are not substituted for uninstrumented CPU measurements. The stack shows CPU work distributed across VFX/Swift, Metal frontend calls, render lowering, draw residency/binding-plan work and allocation; it does not identify a new single dominant failure. Cached per-encoder heap parts already exist in the runtime, so adding another speculative cache is not justified by this capture alone.

Evidence: [default-flow telemetry](/home/qiuqiu/weather-crash-work/weather-surface-flow7-timing.log), [default-flow CPU](/home/qiuqiu/weather-crash-work/weather-surface-flow7-cpu.txt), [worker-disabled telemetry](/home/qiuqiu/weather-crash-work/weather-surface-flow6-timing.log), [worker-disabled CPU](/home/qiuqiu/weather-crash-work/weather-surface-flow6-cpu.txt), [running-only stacks](/home/qiuqiu/weather-crash-work/weather-surface-running.spindump). There are no performance-code edits or commits from these controls. The bounded presentation reporter, periodic telemetry and flow override are disabled for the final Weather launch; only the explicitly documented VFX argument-encoder experiment remains enabled. Visible-animation repair is verified; further CPU optimization and a supported production replacement of the VFX experiment remain open.


### Identity-swizzle CPU candidate

A fresh foreground baseline, using only the VFX argument-encoder experiment and the existing timing reporter, has eight warm 20-second intervals: CPU 52.89%, 50.48%, 52.66%, 53.72%, 52.95%, 50.06%, 51.19% and 50.75% of one core. The corresponding work is approximately 1,862–1,931 draws/second and 87.7–91.0 command buffers/second, with zero submission failures. Both endpoints of the separate top capture identify Weather as frontmost. Evidence: [baseline telemetry](/home/qiuqiu/weather-crash-work/weather-texel-baseline.log), [baseline top capture](/home/qiuqiu/weather-crash-work/weather-texel-baseline-cpu.txt).

Running-only sampling includes repeated texture-class and border derivation below heap-table construction. The candidate makes the default texture swizzle an immediate identity in `reads_unswizzled`, and reuses `texel_format`'s already computed default borders in `with_border`. It adds no cache, name-keyed behavior, environment gate or sampling approximation. Nonidentity swizzles retain their prior path. The candidate is carried as board patch `0005-identity-texture-swizzle.patch` to preserve the pinned, already patched translator worktree. Existing texel-format release checks and the macOS bridge build are in progress; no CPU improvement or runtime success is claimed yet.


The existing release checks pass: `cargo test --release -p metal2vulkan --lib metal::texel_format::tests -- --nocapture` (12 passed) and the corresponding `bind::heap::tests` filter (17 passed). No test source was added. The patch's reverse-application check passes against the integrated translator, and only the patch plus its build entry are candidates for staging. Evidence: [texel checks](/home/qiuqiu/weather-crash-work/texel-identity-release-tests.log), [heap checks](/home/qiuqiu/weather-crash-work/texel-identity-heap-release-tests.log).

Additional VFX read-only decompilation at `0x1DA1F8DAC` confirms the same cached VM byte also suppresses creation of the external scene/entity resource encoders; `0x1DA1F9A8C` uses raw CPU-uniform storage in its false branch. This strengthens the prior finding that a missing Metal feature getter alone cannot restore the default argument-resource path. No global VM identity change, permanent debug authorization, framework patch or production gate workaround is made by this candidate.


The macOS arm64e release bridge and plugin link pass. The candidate executable is signed inside the guest and atomically installed, with the previous executable retained at `/private/var/tmp/NativeAdrenoMetal-before-identity-swizzle`. Its Mach-O UUID is `2178A6C8-CA15-3E8E-B54E-8EF47980229D`; the loaded UUID remains to be checked after restart. The full 402,653,184-byte existing boot image was backed up, and a sixteenth trust module appended from codesign-supplied metadata. Normal shutdown is verified at guest uptime 3637.207728 (`vfs_unmountall(system) end`) and 3637.207938 (`CPU halted`), followed by daemon STOPPED before boot replacement. Data is unchanged. Runtime validation and the performance comparison remain pending. Evidence: [release build](/home/qiuqiu/weather-crash-work/build-identity-swizzle-bridge.log), [link](/home/qiuqiu/weather-crash-work/link-identity-swizzle.log), [shutdown](/home/qiuqiu/weather-crash-work/identity-swizzle-shutdown-kernel.txt).


The sixteenth-module boot is RUNNING. SSH and WindowServer PID 169 are available; console ownership is root or `_windowserver`, so foreground Weather sampling has not started. Developer mode is disabled and `kern.hv_vmm_present=1`. The installed signed executable retains the candidate UUID and is 31,797,584 bytes; its signed copy is preserved locally. User login has been requested for the candidate comparison. The candidate code remains uncommitted until the runtime path is verified, and no performance improvement is claimed from build/tests alone.

### kern.hv_vmm_present 全局改 0 的评估（2026-11-15，结论：不可行）

在 guest 内遍历共享缓存每个镜像的 `__TEXT`，含 `kern.hv_vmm_present` 字符串的镜像约 65 个，主要有：
- 显示：SkyLight、QuartzCore、CoreVideo、RenderBox、IOSurfaceAccelerator、CompositorNonUI
- 音频：caulk
- 机器学习：CoreML、ANE、Espresso
- 账户和激活（反欺诈）：AuthKit、AppleAccount、MobileActivation、DeviceIdentity、ApplePushService
- 系统更新：SoftwareUpdate、OSInstaller
- libMobileGestalt，它的 `IsVirtualDevice` 又会转给更多调用方

QuartzCore 平时按 MobileGestalt 的 `IsVirtualDevice` 判断，只有 ChipID 是 0x8103 时才直接查这个 sysctl。它有 39 个函数按这个标志分支，涉及显示模式和缩放、DCP 通知、`_CARenderUpdateSetDisplays`、backdrop compute、着色器预热等。全局改成 0 会让合成器改走真机 DCP 路径，DroidVMDisplay 没有实现这些，所以否决。

VFX 只针对自己的可行性：
- VFX 的标志是懒初始化（swift_once），第一次在材质绑定时才求值，晚于插件加载。
- 但 `sysctlbyname` 的 GOT 是整个共享缓存共用的：16 个子缓存各有一个桩，都从同一个 auth GOT 槽 `0x1e20fa408` 取地址，这个页只读。
- 所以只针对 VFX 的做法是：插件加载时用 COW 改写这个槽（PAC 地址多样化签名），包装函数只在调用者返回地址落在 VFX 镜像（按路径从 dyld 镜像表查，不写死地址）、且查询名是 `kern.hv_vmm_present` 时返回 0，其他调用全部原样转发。

社区先例（网络检索，2026-11-15）：
- [VMHide](https://github.com/Carnations-Botanica/VMHide)：一个 Lilu 插件，把 `kern.hv_vmm_present` 的 sysctl OID 处理函数换成自己的，按进程过滤名单决定返回 0 还是 1，另有 strict 模式全局返回 0。
- [RestrictEvents](https://github.com/acidanthera/RestrictEvents)：同样按进程打补丁，例如 `revpatch=sbvmm`、`asset`。
- quickemu 社区用 OpenCore 内核补丁全局强制返回 0，用来修 Apple ID 登录，副作用是 guest agent 失效。

可选方案：
- 甲：插件里只针对 VFX 镜像（上节），与具体 App 无关，但要改写 auth GOT。
- 乙：按 VMHide 的思路，在我们自己的内核里按进程名单返回 0（如 Weather），实现简单，但需要维护名单，而且整个进程里的所有框架都会看到"非虚拟机"。

### 方案乙已上线（2026-11-15）

内核提交 f73fe08（macOS 仓库 cfde579，`patches/xnu-12377/vmm-hidden-processes.patch`）：`sysctl_vmm_present` 对 boot-arg `vmm-hidden=NAME[,NAME...]` 列出的进程返回 0（默认 `Weather`，置空则不隐藏任何进程），其他进程仍返回 1。

部署：
- 先用原内核按原开关重建内核缓存，与手机上的逐字节一致，确认构建条件对得上。开关为 `MACOS_DATA_PCI MACOS_DISPLAY MACOS_NET_PCI MACOS_GPU MACOS_VIDEO MACOS_AUDIO MACOS_PCIE MACOS_USB_PCI`，均为 1，`K27_NO_BOOT=1`。
- 只替换现有启动镜像里的 `Payloads/kernel.macho`，信任缓存（含插件模块）不动。
- 手机上原镜像备份为 `boot.img.before-vmmhidden`。关机已确认 `vfs_unmountall(system) end` 和 `CPU halted`。

验证：
- `sysctl` 读到 1，同一程序改名为 Weather 后读到 0。
- 从 Dock 正常打开天气（进程不带 NATIVE_METAL_* 环境变量），用户确认云层显示并且在移动。

固定地址的 VFX 诊断对象（vfx-vm-diagnostic.o）仍链接在已部署的插件里，但没有环境变量时不会生效；下次重建插件时不要再链接它。
