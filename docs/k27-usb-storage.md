# macOS 27 USB 大容量存储

2026-11-12 已在 SM3281（0930:6545，USB 2.0 / 480 Mbps）上验证：
126.4 GB 磁盘及两个 MBR 分区可见；主分区 `sm328x` 为 exFAT，
重新接入后自动挂载到 `/Volumes/sm328x`，剩余约 11.6 GB。
`Windows_NTFS` 是 MBR 分区类型提示，实际文件系统由 FSKit 探测为 exFAT。

需要三个层次同时齐全：

- `k27/try.sh` 的 USB 配置显式保留 `IOUSBMassStorageDriver` 和
  `IOSCSIBlockCommandsDevice`，依赖闭包带入 SCSI family。
- XNU 的固定 owner cache 启动不等待后续驱动替换阶段再发布外部 IOMedia。
  原先 USB 磁盘已有 BSD 节点，但 state 为 `0x8000001e`，被用户态匹配过滤，
  因而 `diskutil` 和磁盘仲裁服务看不到它。
  源码提交为 XNU `b3367e3`，补丁保存在
  [IOService-owner-cache-media-visibility.patch](../patches/xnu-12377/IOService-owner-cache-media-visibility.patch)。
- 保留 `com.apple.filesystems.lifs`，并启用 `com.apple.filesystems.fskitd`。
  macOS 27 默认通过 FSKit 探测 exFAT/FAT；没有 lifs 时 fskitd 启动即退出。

现有 Data 卷中已持久启用 FSKit 服务。制作新种子时不要再使用旧配方中的
`--disable-job com.apple.filesystems.fskitd`。已有禁用记录可用以下命令恢复：

```sh
sudo launchctl enable system/com.apple.filesystems.fskitd
sudo launchctl bootstrap system /System/Library/LaunchDaemons/com.apple.filesystems.fskitd.plist
```

第二条仅用于服务尚未加载的情形。正常启动时由系统按需运行 fskitd 和 exFAT/FAT 扩展。

本次只构建内核/KC，正常关机后更新启动镜像，未重建 Data 种子。
原有独立光标链路保留。USB 重接验证先通过 `diskutil unmountDisk disk3`
卸载，再解除分配和重新接入；没有在 U 盘创建测试文件或格式化分区。
挂载结果见 [auto-mount.log](../research/usb-storage-2026-11-12/auto-mount.log)。

如果 U 盘在固件阶段已分配给 VM，UEFI 可能优先尝试其中的启动程序。
本次更新时暂时取消该设备的 host USB authorization，进入 macOS 后恢复并重新分配。
最终 authorization 已恢复为 1，设备保持分配并挂载。
