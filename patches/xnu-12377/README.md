# xnu-12377 for the k27 VM (macOS 27.2 kexts and userland)

On top of the pristine `xnu-12377.121.6` (sources/xnu-12377, commit ac9718f), applied in order with `git am`; the result is the
tree of branch `k27` (out/k27/xnu, a worktree of out/x12377/xnu-m; also fetched into sources/xnu-12377 as `k27`).
Export again after kernel commits: `git -C out/k27/xnu format-patch --no-signature -o patches/xnu-12377 ac9718f..k27`.

Build: `bash k27/build-kernel27.sh` (out/k27/kernel-k27.macho), then `k27/try.sh` builds the kernel collection and boots it.

Bring-up workarounds that a later commit took out again are not in the series (the 26.5 Sandbox calls and allow-all profile,
k27-sandbox-native, the /private/var/.data firmlink path rewrite, the one-entitlement copyClientEntitlementVnode): the history with
them is branch `k27-unlayered` (23a75df, same tree).
The 47-patch series contains only the single-container layout: the System volume is the root; launchd and APFS mount the other
volumes and stitch their firmlinks. The owner root check and root-only boot manifest are introduced directly in 0002. The former
SystemOS mount and two-volume manifest are absent from every intermediate tree, so no later patch is needed to remove them.
The former UUID patch and final single-volume conversion patch became empty and were dropped; later patches were renumbered.
CONFIG_FIRMLINKS remains enabled for APFS's native firmlinks.

Validation (2026-11-11): all 47 patches replayed with `git am` from ac9718f; the resulting tree is exactly the previously verified
k27 tree `c97cc109b2b49890091f3fb035777204c2fd1e4b`. No kernel behavior changed. Rebuild/replay records are in
`out/layout-cleanup-2026-11-11/`. This rewrites the local k27 patch branch, not the repository's published history.

Patch 0048 (`1168d2b`) adds mixed signed/unsigned Block descriptor support for macOS kexts.
The port compiler emits unsigned descriptors while AppleUserHIDDrivers passes signed ones;
authenticate them on access and re-sign them when a Block moves. Incremental kernel and KC builds passed.
Directed on-device validation (2026-11-11): DriverKit mouse and two trackpad services attached,
kernel_debugger_entry_count remained zero, and native PCIe block reads returned the expected bytes
with SPI 64 increasing once per read. The 47-patch replay record above predates this addition.

`IOServicePM-virtual-thunk-callbacks.patch` (`e59b8c5`) follows 0048. With upstream
Clang's arm64e member-pointer thunks, comparing virtual callback addresses cannot
distinguish IOService defaults from overrides. Preserve power informees on that
compiler configuration. Directed USB validation created all 16 xHCI ports; with
ArmDTPlatform's bus power hierarchy fix, the physical Logitech mouse enumerated.
