# macOS DroidVMDisplay 软件光标

当前已切换至 [独立光标实现](macos-independent-cursor-2026-11-12.md)，
并删除 guest 的 CAUseSWCursor 偏好；以下保留为软件光标回退记录。

2026-11-12，物理 Logitech G102 USB/HID 输入正常，用户仍看不到指针。
CoreGraphics 的 CGCursorIsVisible=true，坐标位于显示范围内；输入报告及系统事件队列均持续增长。
DroidVMDisplay 收到单独的 128×128 BGRA 光标表面，但只扫描输出桌面大小的表面。
省略 CursorPlane 属性并不会让 macOS 27 自动将光标合成进桌面。

QuartzCore 的 CAUseSWCursor 通过 CFPreferencesGetAppBooleanValue 读取当前应用的偏好设置，
不是环境变量。当前应用是 WindowServer；设置系统级偏好后重载它：

```sh
sudo defaults write /Library/Preferences/com.apple.WindowServer CAUseSWCursor -bool true
sudo launchctl kill SIGKILL system/com.apple.WindowServer
```

第二条命令重载图形会话，会关闭当前桌面应用。此次调试中尝试的 launchctl 环境变量已移除。
偏好设置保存在 Data 卷，跨 VM 重启保留，无需改写 Data seed 或重建 KC。
仅设置 CAUseSWCursor，保留该偏好文件的其他键。新安装亦需应用上述 defaults 命令；
配置内容在 [com.apple.WindowServer.plist](../overlay/display/com.apple.WindowServer.plist)。

用户确认“能看到，移动正常”。设置后采集到桌面大小的 RGhA swap，未再观察到此前交替出现的
128×128 光标 swap。未采集截图或读取 framebuffer，未新增测试代码。
原始诊断数据：macos/research/usb-passthrough-2026-11-12/pointer-preference-boot.log。

恢复默认行为：

```sh
sudo defaults delete /Library/Preferences/com.apple.WindowServer CAUseSWCursor
sudo launchctl kill SIGKILL system/com.apple.WindowServer
```

这项配置让当前不提供独立光标平面的显示驱动可用；尚未实现 virtio-gpu 硬件光标。
