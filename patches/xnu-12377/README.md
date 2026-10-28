# xnu-12377 port patches (on top of out/x12377/xnu-m commit eb7f972)

Applied in order (`git am`). 0001-0006 are the real fixes of the launchd bring-up, 0007 the kernel side of DroidVMGpu, 0008 the shared region pager's 16 KiB slide page deadlock (WindowServer's exec), 0009 is the diagnostics (boot-arg gated: `stderr-log=1`,
`sc-trace=NAME[,NAME]`, `sc-trace-all=1`, `iokit-log=NAME[,NAME]`, `crash-log=1`, `sample-pid`, `sample-name`), which can be left out of a production kernel. 0011 makes the board AMP (two clusters, sched_amp); the ADT's cpus need cluster-type, which scripts/run-macos-vm.py adds (MACOS_AMP=0 for an older kernel). 0012 adds the boot argument `exec-env=NAME:VAR=VALUE[,VAR=VALUE...]`, the environment of one executable at exec (e.g. `exec-env=WindowServer:MallocZeroOnFree=0`). 0013 makes the mount union-mounted over the root volume (union-hide-lower=1) report MNT_ROOTFS in statfs, without which fseventsd never starts and the login window comes minutes late.

Build: `XNU_KC=1 XNU_KEXT_CRYPTO=1 bash out/x12377/build-full.sh` (KC layout: out/x12377/kc-segaddrs.sh, scripts/kc-build.py).
