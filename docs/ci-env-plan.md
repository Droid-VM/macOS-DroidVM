# 构建环境脚本化 + 从 IPSW 到完整镜像的 CI（计划，2026-11-16）

目标：在一台干净的 x86_64 Linux（GitHub 托管 runner `ubuntu-24.04`，或本机的空目录）上，只靠本仓库 + 公开来源，
从下载 IPSW 一路做到 `boot.img` + 系统盘镜像，产物加密、压缩、分块上传。

现状：`product.py inputs/disk/full` 在开发机上能从空的 `artifacts/`、`out/k27` 跑通，但它依赖一批没入库、靠手工搭起来的东西
（`toolchains/`、`out/x12377/`、`sources/` 的本地状态、ios 仓库）。本文先盘点这些依赖，再分阶段把它们变成脚本。

## 1. 依赖盘点

方法：`strace -f -e openat,execve,newfstatat,access,readlink` 跟踪一次 `product.py full`（2026-11-16，产物与跟踪前逐字节相同）。
kernel、bridge 是增量构建（make 对每个依赖都做 stat，所以依赖仍在列表里；bridge 的 cargo 只读了 registry）。
最终以第 5 阶段在空目录里从头跑通为准。

### 1.1 宿主程序（apt）

| 用途 | 程序 |
|---|---|
| 编译 | `llvm-21`（clang、clang++、llvm-ar、llvm-nm、llvm-as、llvm-cxxfilt、dsymutil）、`make`、`bison`、`gcc-ar`/`ar` |
| Mesa（Turnip） | `meson`、`ninja`、`glslangValidator`、`dpkg-architecture`（meson 交叉探测）、python3 的 mako、pyyaml 等 |
| bridge | rustup nightly（`~/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu`），自定义 target 需要 `rust-src`；cargo 的 registry 要联网 |
| 启动盘 | `mtools`（mformat、mcopy） |
| 链接器 ld-classic、iig | `docker`（Darling 容器 `macos-appleclang`） |
| inputs | `ipsw`（blacktop/ipsw）；AEA 解密联网取密钥 |
| disk | `sudo`、linux-apfs-rw 内核模块（要对应 runner 内核的 headers）、apfsprogs |
| 其他 | `git`、`patch`、`tar`、`zstd`、`openssl`、`adb`（只在拉手机 DTB 时，CI 里改成入库的 DTB） |

### 1.2 `toolchains/`（5.3 GB，本机手工搭）

| 部分 | 体积 | 来源 | 脚本化办法 |
|---|---|---|---|
| `linux/toolchain/bin/aarch64-apple-darwin-{ld,ar,libtool,strip,nm,otool,lipo,…}` | 14 MB | cctools-port `e101a69` | ios 仓库 `UniXNU-gunyah/scripts/setup-linux.py build` |
| `linux/toolchain/bin/mig`、`migcom` | — | bootstrap_cmds `f337e60` | 同上 |
| `linux/cctools-work`（libmacho、libstuff） | 50 MB | 同上的构建目录 | 同上 |
| `linux/appleclang/apple-tools`（ld-classic、`libclang_rt.cc_kext`） | 1.3 GB | CLTools_Executables.pkg（swcdn.apple.com 公开地址，sha256 固定） | `setup-appleclang.py fetch/extract` |
| Darling 镜像 `e8b09bc1`、`darling-image/` | 332 MB | darling debs v0.1.20260608（GitHub）+ `Dockerfile.appleclang` | `setup-appleclang.py image/start/configure` |
| `linux/bin26/`（target-clang、xcrun、plutil、ditto、`linux-toolchain.json`） | — | ios 适配脚本生成；`native_compile=true`，内核由宿主 LLVM 21 编译，Darling 只做 ld-classic 和 iig | 生成脚本，路径参数化 |
| `linux/host-deps`（unifdef、pax、libbsd 静态库） | 5 MB | Ubuntu deb 解包 | `setup-linux.py` |
| `linux/python-deps`（openstep_parser） | 64 KB | PyPI wheel（sha256 固定） | `setup-linux.py` |
| `linux/apple-iig` | 249 MB | Xcode 16.4/16.2 的 xip（要 Apple ID 登录） | **CI 不需要**：k27 不改 `.iig`，用入库的生成物（见 1.3） |
| `sdks/MacOSX26.1.sdk` | 2.6 GB 解开 | joseluisq/macosx-sdks Release 26.1，sha256 `beee7212…784c`（已核对） | 下载校验解开 |
| `sdks/ios-sdks/iPhoneOS26.5.sdk` | 344 MB | xybp888/iOS-SDKs `ad607cb`，稀疏检出 | git 稀疏检出 |
| `linux/sdk`（iPhoneOS17.5） | 276 MB | 同一镜像 | k27 没读到，不要 |

### 1.3 `out/x12377/`（1.4 GB，内核与 kext 的构建环境，本机手工搭）

| 部分 | 来源 | 脚本化办法 |
|---|---|---|
| `env.sh`、`build-kernel.sh`、`build-firehose.sh` | 手写，原只在 out/ 里 | 已移进 `k27/x12377/`（`build-full.sh`、`kc-segaddrs.sh` k27 不用） |
| `xnu-m`（含 `k27` 分支）、`out/k27/xnu`（它的工作树） | xnu-12377.121.6 `ac9718f` + `patches/xnu-12377`（52 个，覆盖到 `ad47716`） | `git am`，回放后比对树哈希 |
| `build/xnu/e-obj` 的 iig 生成物（`.h`、`.iig.cpp`） | 曾在 Darling 里用 Xcode 的 iig 生成 | 生成物入库（APSL 源码的派生），build-kernel27.sh 从仓库取 |
| `fakeroot`（libfirehose_kernel.a、Availability*、os/ 头） | `refer-libdispatch`、`refer-libplatform`、`refer-AvailabilityVersions`（apple-oss-distributions） | ios 仓库 `build-firehose-linux.py` + 固定 tag |
| `kdk`（CoreEntitlements、TrustCache 等头，388 KB） | KDK 26.5.2 25F84（dortania/KdkSupportPkg 公开镜像） | 下载、校验、`kdk-headers.py` 提取 |
| `un/`（none24smu/UniXNU `ios26` 的一份拷贝，`drivers` 链到 `out/linux/UniXNU/drivers`） | k27 只从中取 `drivers/ArmCpu/ArmCpu.cpp`（UniXNU/ArmCpu `1951cc8`）和 `drivers/ArmDTPlatform/ArmDTPlatform.cpp`（UniXNU/ArmDTPlatform `0d54470`），归档由 `k27/build-platform-*.sh` 生成 | 只克隆这两个仓库的固定提交，不要整棵 `un` |
| `inc-hid`、`inc-gfx` | 指向 MacOSX26.1 SDK `Kernel.framework/Headers` 下 HIDDriverKit、IOKit/{hid,hidsystem,graphics} 和 `TargetConditionals.h` 的软链接（`inc-gfx` 已由 `build-droidvm-gpu.py` 自动建） | 脚本建链接 |
| `src-gpu`、`native-kexts`、`storage-abi` | 脚本生成（`build-droidvm-gpu.py` 等） | 已脚本化 |

### 1.4 `sources/`（`configs/sources.lock.json` 已过时）

实际用到的：`UniXNU`（`.cache/mesa-work` 等）、`UniXNU/drivers/NativeMetal`（`805ea2b`，已推 Droid-VM/NativeMetal `macOS`）、
`UniXNU/drivers/NativeAdreno`、`UniXNU/.cache/gpu-reference/metal2vulkan-555b13d`（steelbrain/metal2vulkan `555b13d`）、
`UniXNU-turnip`（Droid-VM/UniXNU `0f7b62a`）及其 `.cache/mesa-work`（Droid-VM/mesa `cecc0e9` + 33 个记录补丁）、
`UniXNU-droidvm`（`bf7fc44`）、`xnu-12377`、`edk2`（DarwinBoot）。锁文件要改成能描述"提交 + 补丁序列 + 工作树"的格式。

### 1.5 其他

- `artifacts/boot-inputs/UniXNU.efi`：取自某次 Droid-VM CI 启动盘（产物会过期）。要固定一个能长期下载的来源，或用 edk2 从源码编。
- `artifacts/boot-inputs/DarwinBoot.efi`：`scripts/build-darwinboot.py` 已能生成（edk2 `b7a715f`）。
- `out/app/generated.dtb`：手机上 crosvm 为这台 VM 生成的 FDT。CI 用入库的参考 DTB（`MACOS_FDT` 指定），VM 配置变了要更新。
- `scripts/droidvm-app.py` 导入 `~/crosvm/ios/tools/droidvm-app.py`：跨仓库依赖。只有启动盘和 ADT 相关的部分要搬进本仓库，或者把 ios 仓库作为固定提交的源。
- `ios/UniXNU-gunyah/scripts/setup-*.py`：工具链脚本在 ios 仓库，而 ios 仓库是私有的（公开 CI 拉不到）。沿用 `compat/xnu-linux/`
  已有的做法，把 `setup-linux.py`、`setup-appleclang.py`、`darling_mldr.py`、`Dockerfile.appleclang`、`build-darling-mldr.sh`、
  `darling-patches/` 从 ios `9843a07` 原样复制进来。
- `scripts/start-linux-runtime.py` 写死了本机 Darling 镜像 ID `e8b09bc1` 和 mldr 的哈希，换机器重建就对不上；改为读工具链配置。
- 宿主：开发机是 Ubuntu 26.04（自带 LLVM 21、Python 3.14）；GitHub 的 ubuntu-24.04 要从 apt.llvm.org 装 LLVM 21。
- rust：nightly 2026-09-05（rustc 1.100.0-nightly `0ed41eb41`），带 `rust-src`。

## 2. 分阶段

| 阶段 | 内容 | 验收 |
|---|---|---|
| P1 锁文件 | `configs/env.lock.json`：每个源码（URL、提交、补丁序列、工作树位置）、每个下载件（URL、sha256）、apt 包、rust nightly 日期、LLVM 版本 | 用它核对开发机现状全部一致 |
| P2 工具链 | `scripts/setup-env.py toolchain`：复用 ios 的 setup-linux/setup-appleclang，生成 `toolchains/` 和 Darling 镜像；SDK 下载校验 | 在空目录生成后，按 1.2 的清单逐文件对比哈希 |
| P3 内核环境 | `setup-env.py x12377`：脚本入库、xnu `git am` 回放、iig 生成物入库、fakeroot、KDK、un、inc | 空目录里 `product.py kernel` 的内核与现有内核符号地址一致（内核版本串带时间，不逐字节） |
| P4 其余 | `setup-env.py sources`（含 Turnip mesa-work 补丁、metal2vulkan 工作树）、UniXNU.efi 来源、参考 DTB、去掉 ios 依赖 | 空目录里 `product.py full` 产物（KC、插件、Turnip）与现有哈希相同 |
| P5 干净复现 | 新目录：`setup-env.py all` → `product.py inputs` → `disk` → `full` | 端到端跑通，记录时间和磁盘峰值 |
| P6 CI | `.github/workflows/image.yml` | 见第 3 节 |

## 3. CI 设计（P6）

- runner：`ubuntu-24.04`（4 核、16 GB 内存）。先删掉预装的 Android/.NET/GHC 等腾出空间，工作目录放在空间大的分区上。
- IPSW 输入（解出约 16 GB）：`actions/cache` 单仓总上限 10 GB 装不下，改用 Release 资产当缓存：键是两份 IPSW 清单的 sha256；
  zstd 压缩，用 `ARTIFACT_KEY` 做 AES-256 加密，切成不超过 1.9 GB 的块。命中就下载解密，否则跑 `product.py inputs` 再上传。
- 工具链：下载件（CLTools、Darling debs、SDK）用 `actions/cache` 按锁文件哈希缓存；构建出的 `toolchains/` 也按锁文件缓存。
- 编译缓存：内核、kext、Mesa、插件的 C/C++ 编译走 `ccache`（`actions/cache`），各构建脚本支持编译器前缀；bridge 缓存 cargo 的
  registry 和 target 目录，键是补丁和 NativeMetal bridge 源码的哈希。
- 产物：`boot.img`、系统盘镜像（48 GB 稀疏，用 `zstd --sparse` 流式压缩）、`manifest.json`、各中间件哈希。
  加密后用 `split -b 1900m` 流式切块（不落第二份完整副本），上传为 workflow artifact；可选发布成 Release。附解密/合并脚本。
- 含苹果二进制（系统、内核缓存、SDK）的东西一律加密；只有日志和哈希清单明文。

## 4. 进度

- 2026-11-16：完成盘点（本文第 1 节）；ios 的工具链脚本已复制进 `compat/xnu-linux`。
- 2026-11-16：P1 锁文件 `configs/env.lock.json`（宿主包、rust、SDK、工具链部分；源码和内核环境部分随 P3/P4 补上）。
- 2026-11-16：P2 完成。`scripts/setup-env.py toolchain` 在空目录（新克隆的仓库）里一次做出 `toolchains/`：SDK 下载校验、
  cctools-port/MIG 从源码编、CLTools 解包、Darling 镜像构建与容器启动、AppleClang 通过内核类型分配探测、ld-classic、`bin26`。
  与开发机现有工具链逐个比对：ar、libtool、strip、mig、ld-classic、AppleClang、两个 SDK 都逐字节相同；`aarch64-apple-darwin-ld`
  只差 ld64 编进去的构建时间（30 字节）。`apple-iig` 不再生成（k27 不需要）。开发机原来缺 `unifdef`、`pax`、`libbsd-dev`、
  `pkg-config`、`libtool`（以前用解包的 `host-deps`），已按锁文件补装。耗时约 4 分钟（下载走代理，Docker 基础镜像有本地缓存）。
- 2026-11-16：P3 完成。`scripts/setup-env.py x12377` 在空目录里一次做出内核构建环境：
  - 内核树：xnu `ac9718f` 直接浅克隆为 `out/x12377/xnu-m`，`out/k27/xnu` 是它的工作树（`k27` 分支），`git am` 回放
    `patches/xnu-12377`（锁文件 `x12377.series`），树哈希与锁文件一致（`6327053`）。
  - `gunyah-linux.mk`：由树里提交的那份改写为本工作区路径、本机内存和 CPU 数，放在 `out/x12377/`（开发机也改为用它）。
    原先 `host-deps` 里的 pax、unifdef、tcsh、libbsd、libmd 一律改用系统包。
  - fakeroot 的构建顺序：
    1. AvailabilityVersions `make install`；
    2. 拷 libplatform 头；
    3. 对 libdispatch `os/` 头跑 unifdef；
    4. k27 树 `installhdrs`，其 iig 生成物从 `k27/iig` 预置；
    5. `k27/x12377/build-firehose.sh`。
  - KDK：25F84 dmg 的 sha256 已固定（`faef4393…`），在工作区临时目录里解包（/tmp 放不下 1 GB 的 pkg），用 `kdk-headers.py` 提取，结果与开发机逐字节相同。
  - 其余：ArmCpu、ArmDTPlatform 取公开仓库的固定提交；`inc-hid` 由脚本建链接。
  - 新发现的隐藏依赖：
    - 开发机的 iPhoneOS26.5 SDK 被就地加了 `usr/local/libexec/availability.pl`，并换了 `usr/include/AvailabilityVersions.h`
      （xnu 的 `make_symbol_aliasing.sh` 从 SDKROOT 读它们）。两者都和 AvailabilityVersions 的安装产物相同，现由 setup 拷入。
    - xnu 的 doconf 要 `tcsh`（以前在 `host-deps` 里），已加入 apt 列表。
    - `build-kernel27.sh` 的 ArmDTPlatform/ArmCpu 要借内核自己对象的编译记录（`*.cpo.json`），新对象目录里还没有：现在先不链这两个归档、
      让内核先编一遍出记录，再编它们并链接。开发机已有对象，不受影响。
  - fakeroot 与开发机仍有 33 处差异：开发机那份是 10-23 从旧 xnu-work 树导出的，os/ 头也来自另一版 libdispatch。新的
    一份用的是锁定的源码，内核主要用树内头文件。
  - 验收：
    - 空目录 `product.py kernel` 52 秒出内核，符号表 67671 条，代码段地址全同；后面的段只差 480 字节，即 240 个嵌入的构建路径
      各长 2 字节（`ci-clean` 对 `crosvm`）。路径归一后字符串只差版本串里的构建时间。
    - 开发机按新脚本增量编译，符号表无变化。
    - Darling 镜像在空目录从源码重建得到同一个镜像 ID `e8b09bc1`；`start-linux-runtime.py` 改为按锁文件里的镜像标签解析，不再写死镜像 ID。
- 2026-11-16：P4 完成。`scripts/setup-env.py sources`：
  - 源码全部按锁文件取公开仓库的固定提交：
    - UniXNU `b2242fe`，只检出用到的子模块：NativeMetal `805ea2b`（Droid-VM/NativeMetal）、NativeAdreno `805c7e4`、
      DarwinBoot `85332b3`（Droid-VM/DarwinBoot）、NativeAES、NativeRamBlock、VerifiedRoot、AdrenoPM4、ArmSmmu4K；
    - metal2vulkan `555b13d`；
    - Turnip 用的 UniXNU `0f7b62a`（稀疏检出 scripts、patches），加 Droid-VM/mesa `cecc0e9` 并按它记录的 33 个补丁 `git apply`；
    - UniXNU-droidvm `dadbba7`，另抓 kext 脚本 `git show` 用到的四个提交；
    - edk2 `b7a715f`，只初始化 4 个子模块；
    - linux-apfs-rw `0318712` 加 `patches/linux-apfs-rw`（`git am`）；apfsprogs `1bd1c1c` 加 `patches/apfsprogs`。
  - 工具：mkapfs/apfsck、apfs.ko（运行内核是 clang 编的时要 `LLVM=1`）、ipsw 3.1.749 发布版（sha256 已固定，
    `product.py` 默认用 `toolchains/ipsw/ipsw`）。
  - 启动件：
    - `UniXNU.efi` 由 UniXNU 自己的 `package/build.sh`（DEBUG、CLANGPDB）从源码编：用锁定的 edk2 和 LLVM 21，不用它默认的
      Mu_Basecore。与原先 Droid-VM CI 发布的那份（93696 字节）字节不同（93184），但可读字符串完全一致；手机上只换启动盘里
      的这一个文件实测：读配置、出菜单、拉起 DarwinBoot、交接内核、系统起到 sshd，之后已换回原盘；
    - `DarwinBoot.efi` 由 edk2 从源码编，开发机重编逐字节相同；
    - `GunyahBootPkg`（原来只在被忽略的 `sources/` 里）移进 `overlay/edk2/`。
  - 参考 DTB 入库为 `configs/k27-generated.dtb`；`droidvm-app.py` 的 `build_boot` 认 `MACOS_FDT`；没有 ios 仓库时，
    只有和手机打交道的功能报错。
  - 旧的 `prepare-sources.py`/`sources.lock.json` 仍供 14.6.1 时期的脚本使用，保留不动。
  - 修掉的可复现性问题：
    - `build-droidvm-gpu.py` 默认借 `e-obj`（旧 xnu-m 构建的编译记录），改为 `k27-obj`，与其他 kext 一致；九个目标文件除调试信息外完全相同。
    - Turnip 的 source id（即 pipelineCacheUUID）原来随工作区变化：`git diff` 的缩写 blob 名长度随对象数变，选项里又有
      绝对路径。现改为 `--full-index`，路径写成 `$ROOT`，因此开发机的 UUID 变了一次（客户机的 Turnip 管线缓存会失效一次）。
      改后空目录与开发机的 Turnip dylib 逐字节相同。
    - bridge：生成的 Cargo.toml 以绝对路径引用源码，crate 哈希随路径变化，加上 fat LTO，整个库都不同；同时空目录解析出了更新的
      crate。现改为工作区内软链接（`[workspace] exclude`，翻译器的 crate 仍用自己的工作区）加 `trim-paths`，依赖固定为
      `configs/metal-bridge.Cargo.lock`（`--locked`）。另外 `llvm-as` 改用相对输入名，原来嵌进库的 AIR 里带着 `.ll` 的绝对路径。
    - 插件：ld-classic 的调试映射（OSO）记录了目标文件的绝对路径，`apple-ld.py` 改为一律传 `-oso_prefix <工作区>/`。
  - 空目录 `product.py full`（无手机、无 ios 仓库，IPSW 输入从开发机借用 4 个小文件）跑通。与开发机比对：
    - 逐字节相同：Turnip、bridge、插件、Shader Cache 两个可执行文件，以及启动盘里的信任缓存；
    - 只差嵌入的构建路径（内核还差版本串里的构建时间和用户名）：内核、KC、DarwinBoot.efi、UniXNU.efi（PDB 路径），因此 boot.img 也不同。
  - CI 上 Turnip 的身份仍会和开发机不同：它包含 `clang --version`，apt.llvm.org 与 Ubuntu 自带的 LLVM 21 版本串不一样。
- 2026-11-16：P5（本地从零全流程）跳过：开发机只剩 20 GB，全流程要约 45 GB（IPSW 输入 16 GB、新装盘约 15 GB）。改由 P6 的
  CI 首次运行来验证。
- 2026-11-16：P6 `.github/workflows/image.yml`（手动触发）：
  - 宿主准备：用 apt.llvm.org 装 LLVM 21，按锁文件装 apt 包（`docker.io` 除外，runner 已有 Docker）和运行内核的 headers；
    Python 3.14，meson/mako/pyyaml/packaging 按锁文件 `host.python` 固定版本（Ubuntu 24.04 的 meson 1.3 太老）；
    rust 用锁定的 nightly（`MACOS_RUST_TOOLCHAIN`）。
  - 依次运行 `setup-env.py toolchain`、`x12377`、`sources`。
  - IPSW 输入：加密分块的 Release 资产 `inputs-27.2-KEY`（KEY 由产品配置的 inputs 和两个 IPSW 描述文件算出）；命中就下载解密，
    否则跑 `product.py inputs` 再打包上传。
  - 产品：`product.py disk artifacts/27.2/disk`（新装盘，boot 自动用它的根 UUID）→ `full` → `stage`（新增：把插件、
    Shader Cache、用户 `droid:droid`（`MACOS_USER` secret 可改）和 `disk.stage` 的设置写进 Data）。
  - 输出：boot.img、data-store.img、scratch-data.img、disk.json、manifest 等，经 `scripts/ci-blob.sh` 打成
    tar（保留空洞）→ zstd → AES-256 → 1900 MB 分块，作为 run 的 artifact（可选同时发 Release）；日志、哈希、清单为明文。
  - 缓存（actions/cache）：`toolchains/`、ccache、bridge 的 cargo target。
  - ccache：
    - 内核：编译适配器 `darwin-tool.py` 在设了 `MACOS_CCACHE` 时走 ccache。ccache 不缓存带 `-MJ` 的编译，所以先用
      `-fdriver-only` 只跑 driver 写出同样的编译记录（去掉该选项本身），再把不带 `-MJ` 的编译交给 ccache。
    - Turnip：meson 交叉文件里给编译器加 ccache 前缀。
    - 不能设 `CCACHE_BASEDIR`：它会把路径改写成相对路径，内核的 `__FILE__` 字符串随之改变，生成的代码也变了。
    - 实测（20 核）：内核冷编 68 s、热编 20 s，命中 1182/1183；Turnip 66→38 s。与不走 ccache 的产物相比，内核符号表相同、
      编译记录逐字节相同，Turnip 逐字节相同。
- 2026-11-16：P6 拆成六个并行 job（`.github/workflows/image.yml` 顶部有依赖图）：
  - `inputs`：Release `inputs-27.2-KEY` 缺资产（或勾选 refresh）时才跑 `product.py inputs`。输入分两包：small（`out/kc/kc27.bin`
    和 `artifacts/27.2` 中除 `os.raw`、`dec/`、`app-cryptex/`、`disk/` 外的全部，内核 job 只要这些）、large（那三项）。
  - `bridge`、`turnip` 不依赖输入，一开始就并行跑；`kernel`（内核、kext、KC）只等 inputs，下载 small 包；
    `plugin` 等 bridge 和 turnip（`product.py gpu` 不带 deps，直接用前两个 job 的产物）。
  - `image` 等 inputs、kernel、plugin：下载 small+large 两包 → `product.py disk` → 解包 KC 和插件 → `boot` → `stage` → 打包。
    disk/boot/stage 不需要工具链。
  - job 之间传递：KC 加密（`kc.tar.zst.enc.*`），bridge/Turnip/插件 bundle 明文（我们自己的代码）；保留 1 天。
  - 为此新增：`setup-env.py sources --part kernel|turnip|bridge|plugin|inputs|image|all`（每个 job 只取自己要的源码、
    磁盘工具、IPSW 工具、引导程序）、`setup-env.py sdks`（只装 SDK，bridge 用）、`build-droidvm-gpu.py --export-only`
    （只导出补丁后的 DroidVMGpu 源码，Turnip 要它的头文件）、composite action `.github/actions/host`（宿主准备，
    导出 `MACOS_FDT`、`INPUTS_KEY`）。ccache 按 job 分键（`ccache-kernel-`、`ccache-turnip-`）。
