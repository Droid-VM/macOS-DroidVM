# macOS 独立光标接入 crosvm

DroidVMDisplay 原先跳过独立光标表面，需用 WindowServer 的 CAUseSWCursor 偏好将光标合成进桌面。
本次接通原有 virtio-gpu cursor queue，让光标作为 Android 的独立 Surface 呈现。
桌面的 Metal/GPU 加速保留。独立 Surface 最终由 GPU 还是显示硬件合成，由 Android 决定。

## 实现

- crosvm `a62d621d9`：cursor Surface 按 resource 的实际宽高创建。原来固定 64×64，
  后端可接收 macOS 的 128×128 BGRA 资源。Linux 的 64×64 资源继续使用其原始尺寸。
  但当前 Android App 的 View 仍按 64×64 布局；单独扩大 buffer 仍会导致光标图像缩小。
- DroidVMDisplay 发布 `CursorPlane=1`，处理 swap layer 1。空表面隐藏光标；桌面扫描输出独立处理。
- 图像经普通 BGRA 2D resource 上传，位置和显隐经 cursor queue 的 UPDATE_CURSOR / MOVE_CURSOR 提交。
  队列完成后才复用命令缓冲，避免后续移动覆盖尚未消费的请求，以及跨队列释放资源的先后错误。
- 保留当前 IOSurface 和 unlock seed。图像未变时只提交 MOVE_CURSOR；换形状或内容变化时重新上传图像。
- swap 的光标位置位于物理显示模式坐标系，宿主使用桌面扫描缓冲区坐标。
  当前桌面 1344×756、显示模式 1920×1080，位置按对应宽高比例换算；光标图像本身已在源表面尺度。
  不做这一步会显示指针但点击偏移。
- 为兼容 App 的 64×64 光标 View，扫描源图像 alpha，裁掉左侧和顶部透明留白，
  将有效图案放进标准 64×64 resource。源图案的像素尺度保留；在上述位置换算后加上裁剪偏移。
  只扩大 host buffer 而不做这一步时，128×128 图像被缩到 64×64，
  指针在右下角无法到达真实点击点。当前路径容纳的有效图案范围为 64×64；
  更大的辅助功能放大光标需要 App 支持可变光标 View。
- set_parameter(-1) 的四个 uint64_t 字段为时间戳、x、y、可见状态，亦接到光标位置/显隐路径。
  本次观察到的 WindowServer 主要通过 cursor swap 更新位置。

## 当前部署和验证

编译使用 build_crosvm.sh；guest 显示驱动和 KC 构建通过。通过 mcopy 更新 boot 镜像，
正常卸载 APFS 后部署。未改写 Data seed；无文件摘要计算、烟测、新增测试代码或 framebuffer 采集。

当前 guest 已撤掉 CAUseSWCursor 偏好，保持物理 Logitech G102 直通。
首版用户确认指针可见，但点击偏移；随后已部署上述扫描坐标换算修正。
最终用户确认：“边缘和点击都正常”。

guest 实现提交：`dee357f`；crosvm 提交：`a62d621d9`。
最终 SurfaceFlinger 元数据显示独立光标 buffer 为 64×64，桌面 buffer 为 1344×756；
此前光标 128×128 buffer 的显示缩放为 0.8516，桌面为约 1.6935，印证了 App 对光标图像的半尺寸缩放。
最终 guest 的 kernel_debugger_entry_count=0，8 个 CPU 均就绪。
坐标修正后的中间版已记录 4300 次 MOVE_CURSOR 路径调用；图像按 surface/seed 变化重新上传。

原始证据位于 [cursor-plane-2026-11-12](../research/cursor-plane-2026-11-12/)，
包括构建输出、IORegistry、启动日志和每 CPU SPI 计数；当前 kernel_debugger_entry_count=0，8 个 CPU 均就绪。

## 设置

独立光标无需软件光标偏好。此前启用过软件光标的已有安装，删除该键后重启图形会话：

```sh
sudo defaults delete /Library/Preferences/com.apple.WindowServer CAUseSWCursor
sudo launchctl kill SIGKILL system/com.apple.WindowServer
```

这会重载桌面并关闭桌面应用。恢复软件光标的方法见
[软件光标记录](macos-software-cursor-2026-11-12.md)。
