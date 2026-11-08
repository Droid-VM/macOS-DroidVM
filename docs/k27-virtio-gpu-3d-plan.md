# k27 GPU 改走 virtio-gpu 3D（drm2kgsl）方案（2026-11-02）

## 为什么

- 现在：Metal → turnip（tu_knl_darwin）→ NativeAdreno user client（type 0x4147）→ DroidVMGpu kext → crosvm `--droidvm-gpu`（KGSL 代理设备）。
- 上游 Droid-VM/UniXNU-droidvm 已删掉 droidvm-gpu 的 guest 驱动（4284c6c、04d9f0d：“crosvm no longer has the droidvm-gpu device”），
  iPadOS 27 已用 virtio-gpu 3D 画出锁屏（23af1b2）。我们这条路上游无人维护，NativeAdreno main 也已走到 ABI v2、和 DroidVMGpu.cpp 的硬件层脱节。
- 目标：Metal → turnip（**仍是 tu_knl_darwin，加 virtgpu 分支**）→ 加速器 user client（type 0x4149）的 virtgpu 方法
  → virtio-gpu DRM native context（capset 6）→ 宿主 virglrenderer drm2kgsl → KGSL。

## 上游现成的东西（都在本地 fetch 过）

| 部件 | 位置 | 说明 |
|---|---|---|
| virtio-gpu 共享传输层 | UniXNU-droidvm wip/hackintosh `package/DroidVMVirtioGpu.{h,cpp}`（368 行） | 一个控制队列，显示与 3D 共用，多命令在途（post/poll/wait/abandon、全局 fence 环） |
| 3D 上下文 + user client 方法 | 同上 `package/DroidVMVirtioGpu3D.cpp`（981 行） | capset 6、每连接一个 DRM context、shmem 从 drm-host-pool 切、blob 用 guest 页、fence 等待、显示 hold；`vgpu-selftest=1` 开机自检 |
| 显示 | 同上 `DroidVMVirtioGpuDisplay.cpp` | iOS 的，不直接用；只借它“等 GPU 活干完再扫描”的规则（droidvm_virtgpu_finished） |
| 只剩发布的 DroidVMGpu | 同上 `package/DroidVMGpu.cpp`（1054→296 行） | NativeAdreno 只做发布与加速器注册，硬件类永不 attach |
| 用户态 ABI 头 | `DroidVMVirtgpuABI.h`（3D 方法号，0x7200 起） | turnip 与 NativeMetal 都包含 |
| turnip 后端 | Droid-VM/UniXNU wip/droidvm `patches/mesa/turnip-darwin-virtgpu.patch`（822 行） | 新文件 tu_knl_darwin_virtgpu.{cc,h} + tu_knl_darwin.cc 7 处钩子；`TU_DARWIN_VIRTGPU=1` 时把 NativeAdreno ABI 方法翻成 virtgpu；按 **ABI v1** 写（用到 MaxBoBytesShift），与我们的 805c7e4 同代 |
| Metal 前端 | Droid-VM/NativeMetal wip/hackintosh（比我们 45c8294 多 104 提交） | 0x4149 隧道、display hold |
| ADT | UniXNU-droidvm `scripts/make-droidvm-adt.py` | /arm-io/virtio-gpu 加 `drm-host-pool`（FDT 里的 drm2kgsl_host 池） |

宿主侧已就绪：手机 crosvm 的 macOS VM 已带 `--virtio-mmio-gpu`（gpu_api=drm2kgsl），stderr 有 drm2kgsl_renderer_probe、VBO 2^37、
Drm2KgslPool 64 MiB。**不需要改 crosvm。**

## 已验证的兼容性

- turnip-darwin-virtgpu.patch 在我们的 mesa pin（85fda3b + 8 个记录补丁 + mesa-macos）上：两个新文件、meson、tu_device 干净；
  tu_knl_darwin.cc 的 7 个 hunk 冲突（上游 darwin 后端补丁比我们新 587+/123−），需手工移植。
- 上游 turnip-host-import-images.patch 与我们 mesa-macos/0003 是同一问题的两种修法，二选一。

## 分阶段

### P0 内核 3D 上下文打通（用户态不动，可与现路线并存）
1. 新 native kext（暂名 DroidVMVirtioGpu）= 上游 DroidVMVirtioGpu.cpp + 3D.cpp，按 overlay/kext 的方式编（build-native-kext.py）。
2. DroidVMDisplay 去掉自带的单用户轮询传输层，改调共享传输层的 command()/post()（同一设备只能有一个驱动占队列）。
3. ADT：run-macos-vm.py 给 /arm-io/virtio-gpu 加 drm-host-pool（取 FDT 池，参考上游 make-droidvm-adt.py:561）。
4. 验收：`vgpu-selftest=1` 走到 GET_PARAM(GPU_ID)=6850；桌面、拖动帧率不退化（显示改了传输层）。
- 待查：0x4149 user client 挂在谁身上。上游是“加速器的 user client，由 3D.cpp 服务”；我们的加速器由 NativeAdreno 发布（staged Publish），
  要在 newUserClient 里把 0x4149 路由到 3D 方法——可能落在 patches/droidvm-gpu/NativeAdreno 的新补丁里。

### P1 用户态切到 virtgpu
1. patches/mesa-macos/0004：移植 turnip-darwin-virtgpu（新文件原样，7 个钩子手工合）；DroidVMVirtgpuABI.h 放进 ABI 导出目录。
2. NativeMetal：把 Droid-VM wip/hackintosh 的 0x4149 隧道与 display hold 挑进我们的 macos 分支（UniXNU 子模块 bump）。
3. 开关：exec-env 给 Metal 进程加 `TU_DARWIN_VIRTGPU=1`（先只给 metal-probe，再 WindowServer，再全部）。
4. 验收：metal-probe 结果与现路线一致 → WindowServer 登录、桌面、Safari。

### P2 显示与 GPU 的先后
- 现在 DroidVMDisplay 的扫描不知道 virtio 3D 的活干完没有；移植上游 droidvm_virtgpu_finished / hold 规则，防止撕裂和读到半帧。

### P3 性能与内存对齐（止损点）
- 对比项：拖动帧率（现 kc292：111–121）、提交往返、首登内存、blob 分配耗时（上游注释：连续块扫描曾 0.2–3.7 s/blob，默认已改普通页）。
- **止损**：调优后拖动帧率低于现路线 15% 以上，或首登出现 blob 拒绝导致进程死，则停在 P2、保留 droidvm-gpu 路线并上报。

### P4 拆除旧路线
- VM 模板去掉 `--droidvm-gpu`（droidvm-app register + 重新 dump FDT）；DroidVMGpu 缩成只发布（上游 296 行版）；
  patches/droidvm-gpu 的 BO 池/无池/提交相关补丁、GPU_ARGS 里的 droidvm-gpu-* 参数、wire 1 说明一并删。
- 之后 NativeAdreno 可以跟上游走（硬件层不 attach，ABI 升级只影响 turnip 的 darwin 后端）。

## 风险
- 性能：两条路都是每次提交一次宿主往返；virtio 多了 virglrenderer ccmd 解析，少了我们的 KGSL 代理层。未测，P3 决定。
- 共享队列：显示命令与 3D 提交抢一个控制队列；上游已按“fenced 命令不占队列”设计，iPadOS 27 2048x2732 可用。
- NativeMetal 分叉：我们 macos 分支与 Droid-VM wip/hackintosh 差 104 提交，挑提交可能有冲突。
- 回退：P0–P2 期间 droidvm-gpu 设备和旧 kext 都还在，`TU_DARWIN_VIRTGPU` 不设就是旧路线。

## 进度
- 2026-11-02 P0 完成（9f59276）：传输层+3D 编进 DroidVMDisplay（槽数组挪堆上，patches/droidvm-display/0001，否则 DroidVMGpu 的 __DATA 放不下）；
  NativeAdreno 挑入 Droid-VM 的 virtgpu 提交（0003–0008，0x4149 与 0x7200 方法隧道）；kc-build 允许原生 kext 互相解析唯一符号；
  ADT 加 drm-host-pool。上机：vgpu-selftest 读到 GPU_ID 6850，显示走共享队列正常，登录界面正常。拖动帧率待用户确认。
- 2026-11-02 P1 进行中：patches/mesa-macos/0004（上游 turnip-darwin-virtgpu 移植，服务名取 TU_DARWIN_SERVICE，默认 IOAcceleratorES）编过。
  部署不换种子：stage-gpu-plugin.py --base 现种子 --store 拉回的 data-store.img（scripts/data_store.py：覆盖层折入→改→页差写回覆盖层），
  droidvm-app.py store-patch 原地 dd 写入手机 store（被替换的块先存 data-store.undo.*）。用户 Data 1.6 GiB 超出打包种子 256 MiB 上限，折回种子不可行。
  MACOS_EXEC_ENV='metal-probe:TU_DARWIN_VIRTGPU=1' 只让 metal-probe 走 virtgpu。
- 2026-11-02 P1 上机（28a93b8、1914f41）：metal-probe 单独走 virtgpu 先失败于 ResourceCreateBlob InvalidResourceId（DroidVMDisplay 自带资源号计数撞 3D 的 1 号），
  改用传输层 resourceId() 后通过；随后 vgpu-3d=1（上游板级默认，turnip 不设 TU_DARWIN_VIRTGPU 时开 0x4149 问 DEFAULT_3D）全部 Metal 进程只开 0x4149，
  WindowServer 经 drm2kgsl 出帧、登录界面在、无 panic。当前手机启动盘带 vgpu-3d=1 与 stderr-log=1（诊断，下次重建去掉 stderr-log）。待用户看画面/拖动。
- 2026-11-02 P2（提交见 git log）：用户报壁纸抽动。DroidVMDisplay 在 swap_submit 记 droidvm_virtgpu_submitted()，拷贝线程扫描前等 droidvm_virtgpu_finished()（100 us 步长、200 ms 上限）。
  实测约 1/5 的帧需要等，均值 3–6 ms、0 次放弃。未移植上游的 display hold（NativeMetal 编码线程晚提交时用）；若仍见半帧再加。
  开机偶发卡在第一个磁盘请求（Waiting on IOMedia），与本改动无关，重启即过。
- 2026-11-02 P2 后锁屏动态壁纸仍抽动（用户两次录屏）：已排除宿主拷贝、前端 YCbCr 缓存、WindowServer IOSurface 使用计数（试过无效、已回滚）。
  详见 k27/TODO.md「GPU 迁 virtio-gpu 3D」一节的待查方向。P3 未开始。
- 2026-11-02 对照：旧路线（无 vgpu-3d=1）登录后锁屏同样抽动 → 不是迁移的问题，从本方案剥离（k27/TODO.md 独立跟踪）。P1/P2 结论不变，下一步 P3。
- 2026-11-02 P3 拖动 A/B（同日、同频率上限）：新路线 80–109 帧/s（峰值 115），旧路线 84–88（峰值 101），止损未触发；首登内存与 blob 耗时未测。

2026-11-02 P4 完成（b0558b7）：VM 无 --droidvm-gpu，DroidVMGpu 只发布（上游 4284c6c 式），starter 挂 IOResources，GPU_ARGS 只剩 vgpu-3d=1 与 CA 节奏参数；上机桌面正常、所有打开都是 0x4149。NativeAdreno 的 KGSL 代理补丁随后也删了（b502540，只剩 6 个 virtio-gpu 3D 提交）。

2026-11-02 与上游 Droid-VM 核对：内核侧（NativeAdreno virtgpu、DroidVMVirtioGpu*）已与上游一致；用户态未同步——Turnip（mesa pin cecc0e9 及
deadline-queue/queue-priority/bo-cache-budget 等约 10 个补丁）、NativeMetal（109 个提交）；宿主 virglrenderer 缺 10-31 后的 deadline queue 功耗约束。
顺序：Turnip（只改 guest）→ 宿主 virglrenderer（需同意）→ NativeMetal 分批（以 Droid-VM/NativeMetal wip/hackintosh 为主，UniXNU main 与之分叉、不直接跟）→ 硬件编解码（VideoToolbox 半虚拟化移植）。详见 k27/TODO.md。
