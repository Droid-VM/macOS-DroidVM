# xnu-12377 port patches (on top of out/x12377/xnu-m commit eb7f972)

Applied in order (`git am`). 0001-0006 are the real fixes of the launchd bring-up, 0007 is the diagnostics (boot-arg gated: `stderr-log=1`,
`sc-trace=NAME[,NAME]`, `crash-log=1`, `sample-pid`), which can be left out of a production kernel.

Build: `XNU_KC=1 XNU_KEXT_CRYPTO=1 bash out/x12377/build-full.sh` (KC layout: out/x12377/kc-segaddrs.sh, scripts/kc-build.py).
