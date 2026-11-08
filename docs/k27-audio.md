# k27 音频（virtio-snd）现状（2026-11-06）

## 一句话现状

有声、不卡、音画同步（11-05 晚用户确认"正常了"）。根因有两层：guest 侧 CoreAudio 写死 24 MHz 时钟（主因），宿主侧 snd helper 线程被 vCPU 抢占（次因）。
前者已由内核补丁 0042 + 默认启动参数正式修复；后者目前只靠手机上的 `sndrt.sh` 临时兜底。

## 症状 → 根因

| 症状 | 根因 | 修法 |
|---|---|---|
| 隔一秒左右卡一下，声音越来越落后于画面（嘴型对不上） | macOS 27 CoreAudio 假定宿主时钟 24 MHz：`AudioGetHostClockFrequency` 直接 return 24000000.0（常量 0x1841ecd70 约 25 处读），13 个函数内联 125/3 换算；本板计数器 19.2 MHz → HAL 每 80 ms 才写 3072 帧（应 64 ms），每秒落后一跳，CoreMedia 报 `FADC … Flagging discontinuity` | 移植 Droid-VM 上游 UniXNU-droidvm `5edbbfc`（ipados27/patches/xnu-12377/droidvm-timebase-24mhz.patch）：内核把计数器读数 ×5/4、decrementer 反换算（向上取整）、mach_timebase_info 报 125/3、用户态走 mach_absolute_time trap（USER_TIMEBASE_NONE）。启动参数 `droidvm-timebase-hz=24000000` |
| 偶发整段空（宿主 "playback stream is running with nothing queued"），guest 丢周期 | crosvm 声卡 helper 的 `exe`、`AudioTrack` 线程是 SCHED_OTHER，被 1:1 绑核的 vCPU 线程抢占（窗口内等 120–184 ms）→ 16 个 tx 槽全压在宿主 | 临时：`/data/local/tmp/sndrt.sh` 循环 `chrt -f -p TID 2`。正式修复待做（helper 是 app uid，不能自设 RT，要 droidvmd/root 侧做） |
| 延迟高（约 170 ms 以上） | AAudio 阻塞写的流被拒 FAST（"FAST denied by client … TRANSFER_SYNC"），落到 deep buffer（168 ms） | crosvm 改为数据回调 + LOW_LATENCY → fast mixer（约 31 ms） |

注意：内核 `mach_timebase_info` 本身一直是对的，问题在用户态框架写死频率；Swift `Task.sleep` 等同类偏差一并修好。
Apple 在 macOS 15 发布说明里写明 M3+ 用 1 GHz 计数器但 VZ 虚拟机仍给 24 MHz，即用户态默认 24 MHz。

## 修后实测（11-05 晚）

HAL 每 61–65 ms 写 3072 帧；HAL 写入领先 +2.5k–6.7k 帧；discontinuity 0；宿主 10 s 收 480000 帧、丢 0、补静音 0。

## 代码状态

| 位置 | 内容 | 状态 |
|---|---|---|
| `out/k27/xnu` k27 分支 `fd327f8` = `patches/xnu-12377/0042-k27-a-24-MHz-timebase-…patch` | 24 MHz 时基（machine_routines.c、pe_identify_machine.c） | 内核分支已提交；补丁已提交（macos bcf8237） |
| `patches/xnu-12377/0041` | coreaudiod 实时计算量超限截到上限（thread_policy.c） | 补丁已提交（macos bcf8237），但内核 k27 分支里仍是工作树 diff、**未提交**（另一会话的改动，别动）。时基改 24 MHz 后 1200000 tick 正好 50 ms，可能已不需要，未验证 |
| `scripts/droidvm-app.py` REQUIRED_ARGS | 默认带 `droidvm-timebase-hz=24000000`（可用 MACOS_DROP_ARGS 去掉做 A/B） | 已提交（macos bcf8237） |
| `patches/droidvm-audio/0001–0003` | 0001 native kext 不自己做模块加载；0002 开播垫 8 周期（40 ms）；0003 报的输出延迟再加 1536 帧（宿主侧） | 已提交（macos bcf8237）；0099 临时诊断已删 |
| `external/crosvm/android_audio/src/lib.rs` | AAudio 低延迟 + 数据回调；8 周期环（OutputRing）；欠载补静音记债、后到的数据按债丢回；环满时 `ex.delay` 让出执行器（阻塞会饿死 desc 接收任务=全静音）；丢帧时 warn | 已提交（crosvm d7fdd3079，wip/macos-virtio-gpu），已部署（手机备份 `crosvm.bak-1105`） |
| `external/crosvm/devices/src/virtio/snd/common_backend/async_funcs.rs` | 断粮后把已排队的积压周期按欠的数量直接完成（不播），避免永久落后 | 已提交（crosvm d7fdd3079），已部署 |

临时诊断（guest 0099、crosvm `DIAG snd` 与 10 秒统计行、手机 `vcpusched.sh` 采样）11-06 已全部撤掉。

## 导出内核补丁的坑

REPO-LAYOUT 写的导出方式是 `git format-patch ac9718f..k27`。但 0041 来自未提交的工作树 diff，若按区间重新导出，`fd327f8` 会变成 0041 并覆盖截断补丁。
在 0041 提交进 k27 分支之前，只单独导出：`git -C out/k27/xnu format-patch --no-signature -1 <提交> --start-number N -o patches/xnu-12377`。

## 参考与逆向结论

- Apple AppleVirtIOSound（只走 PCI，用不上）：HAL 插件周期 = roundup(rate×bpf/12, 页) = 4096 帧、12 周期、冲刷定时 41.67 ms、safety offset 100、时间戳周期 260 ms、latency 0、不看 latency_bytes；kext 只是透传（AppleVirtIOSoundUserClient）。产物在 `out/tmp/avs/`。
- QEMU virtio-snd 2026-02 有 `latency_bytes` 补丁。
- CoreAudio 27 逆向：`out/tmp/ca27/CoreAudio` + `dsc.a2s`（`ipsw dyld extract … -c <可写 a2s> --slide -o dir`，只读挂载上直接跑会失败）。

## 诊断手段

- guest：驱动的 EngineStatus.writeEnd 看 HAL 写入节奏；log-stream 里的 FADC discontinuity。
- 宿主：crosvm stderr 的 "late periods dropped"、"endpoint took nothing"；`/proc/PID/task/TID/schedstat` 采 vCPU/helper 线程等待。
- 换 guest 补丁后：`bash k27/build-native-audio.sh` → `K27_NO_BOOT=1 MACOS_DISPLAY=1 MACOS_GPU=1 MACOS_VIDEO=1 MACOS_AUDIO=1 bash k27/try.sh 0` → 重建启动盘（先核对种子身份 1aa0a464ac13866f）。

## 登录前 audiomxd 死循环（11-06 定性，用户决定先跳过）

- 现象：停在登录界面不登录时 guest 约 2.4 核忙（宿主逐 CPU 采当前线程：log 11%、audiomxd 9%、diagnosticd 7%，按 8 核计）。
- 根因（逆向 DSC 27.0.1 的 MediaExperience + BluetoothServices）：`MXAudioAccessoryServices initializeAudioAccessoryConnection` 新建
  `BTAudioRoutingRequest` → `updateAudioState:withState:2` → `_ensureXPCStarted`：系统上下文且无前台用户 → `_handleServerDied` +
  报 "No user logged in" → 发 `AudioAccessorydDiedNotification` → MX `handleServerDeath` → finalize + initialize → 回到开头。无退避，每秒上千次；
  configd 每轮被查控制台用户也跟着高。`+[BTAudioRoutingRequest isSupported]` 恒真，无配置开关。登录后自停。与 24 MHz 时基无关（之前就有）。
- 真机同样有：Apple 社区 https://discussions.apple.com/thread/256381912（2026-10-23，Mac mini + macOS 27.0.1 26A434，audiomxd 75–79%、
  configd 41–42%，同样的日志，无回复、6 个"我也遇到"，唯一绕过=保持登录/自动登录）；Jamf 社区 Sequoia 15.2 机房登录窗口 audiomxd 100%（关蓝牙后消失）。
- 已做：去掉 Data 的 org.droidvm.log-stream（它的谓词转发 audiomxd/coreaudiod 错误，占约 1.4 核）。之后登录前 audiomxd≈6% + configd≈5%，总忙约 1 核。
- 未做（可选）：① 自动登录（autoLoginUser + /etc/kcpassword，不改二进制，代价无登录界面）；② exec-env 给 audiomxd 注入 dylib 让
  isSupported 返回假（根治，本板无蓝牙；需先验证 audiomxd 接受 DYLD 注入）；③ 登录前禁用 audiomxd、登录后 enable+kickstart（绕）。
- 诊断：`research/debug-2026-11-06/cpusample.py [次数]`（基于 research/debug-2026-10-31/k27-threadwalk.py 偏移；状态 0x84 的 kernel_task 线程是空闲线程）。

## 待办

- [ ] 宿主 snd helper 线程实时调度的正式修复（AAudio 回调线程本身已是实时的，但给环填数据的 `exe` 线程不是；方向是 droidvmd 以 root 给 helper 设 SCHED_FIFO，具体做法未定）；在此之前不要停 `sndrt.sh`，手机重启后要重新拉起。
- [ ] 验证 0041（实时计算量截断）在 24 MHz 时基下是否还需要。
- [ ] 麦克风：宿主 PCM_PREPARE stream 1 失败（AAudio Failed to open stream），推测 App 无录音权限，未验证。
- [x] 提交：crosvm d7fdd3079；macos bcf8237（DroidVMAudio、droidvm-audio 0001–0003、xnu 0041/0042、MACOS_SND、--enable-job、droidvm-video 0012），11-06。
- [ ] （跳过中）登录前 audiomxd 死循环，见上节。
- [ ] 收尾：卸载 `/tmp/sysos27`（loop 设备记在 `/tmp/sysos.loop`）；`macos/research/vt-probe/collect.sh` 可按需从 `.bak` 恢复。
