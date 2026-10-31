# xnu-12377 for the k27 VM (macOS 27.0.1 kexts and userland)

On top of the pristine `xnu-12377.121.6` (sources/xnu-12377, commit ac9718f), applied in order with `git am`; the result is the
tree of branch `k27` (out/k27/xnu, a worktree of out/x12377/xnu-m; also fetched into sources/xnu-12377 as `k27`).
Export again after kernel commits: `git -C out/k27/xnu format-patch --no-signature -o patches/xnu-12377 ac9718f..k27`.

Build: `bash k27/build-kernel27.sh` (out/k27/kernel-k27.macho), then `k27/try.sh` builds the kernel collection and boots it.

Bring-up workarounds that a later commit took out again are not in the series (the 26.5 Sandbox calls and allow-all profile,
k27-sandbox-native, the /private/var/.data firmlink path rewrite, the one-entitlement copyClientEntitlementVnode): the history with
them is branch `k27-unlayered` (23a75df, same tree).
