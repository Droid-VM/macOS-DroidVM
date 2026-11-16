# k27 联动内存与 GPU 池块上限（2026-11-16）

## 现象

5 GiB guest 开机十几分钟后联动（wired）内存 2.2–2.5 GiB。`zprint -t` 里记在 DroidVMDisplay（kmod 59）名下的 1.4–1.65 GiB
是 GPU 缓冲区：没有独立显存，BO 一分配就整块常驻。其余固定开销：页表约 290 MB、内核 zone 约 300–330 MB、启动期 241 MB。

按进程看 `footprint` 的 `IOKit (graphics)`：WindowServer 623 MB、iconservicesagent 267 MB、活动监视器 320 MB。`vmmap` 显示
占用集中在少数大块：WindowServer 有 4 个 80 MB，iconservicesagent 有 2 个 64 MB 和 1 个 68 MB。

## 原因

metal2vulkan 555b13d 的 `crates/metal2vulkan-runtime/src/memory.rs`：

- 池块从 `FIRST_BLOCK_BYTES`（4 MiB）起随池翻倍，上限 `BLOCK_BYTES` = 64 MiB，图像块再加 1/16。
- NativeMetal 45c8294 的桥接补丁 0021（上限 16 MiB，当时 WindowServer 620 → 310 MiB）在换到 555b13d 时被删，合并补丁
  0040 没带上。
- 空块闲置 10 s 才释放，清扫只发生在该进程后续的创建调用里（`sweep_stale`）；画完就闲下来的进程不会归还。

对照：`kill -9` 用户的 iconservicesagent 后，新进程画同类图标只占 121 MB（块 4–24 MiB）。

## 修改

`patches/metal2vulkan-macos/0006-sixteen-mib-memory-blocks.patch`：`BLOCK_BYTES` 改为 16 MiB，已加进
`scripts/build-metal-bridge-macos.py` 的补丁清单。空块定时清扫没有做。

## 结果

同一台 VM，开机 12–13 分钟，活动监视器关闭：

| 项目 | 改前 | 改后 |
| --- | --- | --- |
| 联动内存 | 2206 MB | 1555 MB |
| GPU 缓冲区（kmod 59） | 1376 MB（峰值 2369） | 753 MB（峰值 765） |
| WindowServer | 623 MB | 267 MB |
| iconservicesagent | 267 MB | 60 MB |

改后最大块为 24 MB（WindowServer：4 个 20 MB、3 个 16 MB、24 和 12 MB 各一个）。没有新的崩溃报告，日志里没有
OutOfMemory 或 MTLTexture 分配失败。两次的桌面操作不完全相同；帧率和天气云层没有复测。

## 部署记录

- 插件从已提交的 NativeMetal（2798366）重编，`NO_STAGE=1 bash scripts/build-metal-plugin.sh --no-deps`；之前链接的 VFX
  诊断对象不再带上。
- 在 guest 里 `codesign -f -s - -i org.droidvm.NativeAdrenoMetal`，替换
  `/Library/GPUBundles/NativeAdrenoMetal.bundle/Contents/MacOS/NativeAdrenoMetal`，旧文件在
  `/private/var/tmp/NativeAdrenoMetal-before-16mib`。
- 停机后拉取手机启动盘，用 `research/gpu-memory-2026-11-16/add-trust-module.py` 给信任缓存追加一个模块（17 → 18），
  推回；旧盘是手机上的 `boot.img.before-16mib`。没有动 Data 种子。

## 诊断方法

- `sudo zprint -t` 看 kmod 标签；`sudo footprint -a` 的 `IOKit (graphics)`；`sudo vmmap PID | grep ^IOKit` 看块大小。
- `METAL2VULKAN_LOG_MEMORY=1` 的输出走设备消息 sink 的 Info 级，在这套插件里到不了 stderr 或系统日志。
- `research/apple-account-2026-11-15/kernel-static-live.py` 可在运行中读写内核静态量（exec-env、stderr-log、vmm-hidden）。

## WindowServer 的显存构成（遥测，11-16 03:15）

取法：运行中把内核 exec-env 改成 `WindowServer:NATIVE_METAL_TIMING=1`，`launchctl debug system/com.apple.WindowServer --stderr
/private/var/tmp/ws.err`（会一直等到服务下次启动），再 `kill -9` WindowServer；之后每 20 s 一份表。自动登录只在开机后第一次
loginwindow 启动时生效，重启 WindowServer 后要手动登录。

`footprint` 369 MB 时的 `MEM`/`MK`/`ML` 行（MiB）：

| 部分 | 大小 | 说明 |
| --- | --- | --- |
| 池块里实际放了东西 | 67 | 15 个池块共 128，其中 61 是块内空余 |
| 保留的空池块 | 64 | 内存压力警告时归还（实测 64 → 0） |
| 独立块 | 22 | 11 MiB 一个，1600×900 半浮点整幅 |
| memoryless 附件被 Turnip 实际分配 | 36 + 保留 16 | 在 sysmem 渲染的 pass |
| Turnip 的已释放 BO 缓存 | 98（峰值 110） | 预算 96 + 小块 16；压力警告后 `tuc flush` 仍为 0 |

也就是真正在用的约 125 MiB，其余约 240 MiB 是块内空余和各级缓存。

`sudo memory_pressure -S -l warn` 的对照：WindowServer 收到警告（`PE warn 1 freed 6`），运行时空块和保留的 lazy 块清零，
WindowServer 369 → 316 MB，全系统 GPU 标签 943 → 869 MB；Turnip 的缓存没有清（109 MiB，`tuc flush 0`）。

## 其他发现

- 插件（`overlay/metal/NativeAdrenoMetalPlugin.mm`）仍在设 `METAL2VULKAN_BLOCK_MIB=16`，但 555b13d 的运行时已不读这个变量，
  所以合并后一直无效；0006 改的是常量。注释里记着上游 iPadOS 板在 16 MiB 下渲染服务挂过（NativeMetal 8f735a2），macOS 上没出现过。
- 其他进程的 Turnip 缓存预算是 16 + 8 MiB，只有 WindowServer 用默认 96 + 16。
- 早先看到的 20 MiB 区域不是独立纹理，属于 Turnip 自己的缓存和附件。

## 可做而未做

- Turnip 的 BO 缓存在内存压力时不清：查压力事件源在 virtio 后端下是否建立，或给 WindowServer 设较小的 `TU_DARWIN_BO_CACHE_MB`
  （代价是新建 BO 要走宿主往返，过渡动画时 10–35 ms 一次）。
- 运行时空块定时清扫。
