#!/usr/bin/env python3
"""Build AdrenoMetal's Shader Cache app (NativeMetal ShaderCache/, upstream's tools/build-shader-cache-app.py) for this guest, on Linux:
out/metal/shader-cache/Shader Cache.app, its two executables linker-signed (product.py trusts them in the boot disk's trust cache, as
the plugin's; the guest runs nothing outside it).

The app shows the system shader cache's progress, and its worker, started as root through an administrator authorization
(AuthorizationExecuteWithPrivileges), opens the plugin's device with NATIVE_METAL_PRIMER=1 and compiles every Metal library of the
OS into the system shader cache, which every other process reads as a layer after its own cache.

Upstream's macOS layout has the kernel make /private/var/tmp/NativeAdrenoMetal.cache for _windowserver and show it read-only at
/Library/GPUBundles/NativeAdrenoMetal.cache (SharedShaderCache.h); this guest's kernel does neither. Here the worker writes the reader's
directory itself: /Library/GPUBundles/NativeAdrenoMetal.cache, made by the worker, owner root, mode 0755 -- only the superuser writes
it, every sandbox that may use graphics reads /Library/GPUBundles, and the plugin (overlay/metal/NativeAdrenoMetalPlugin.mm) names it
as the layer. WindowServer does not fill it (it is not root), it keeps its own cache as before.

    build-shader-cache-app.py"""
import os
from pathlib import Path
import plistlib
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
NATIVE = Path(os.environ.get('NATIVE_METAL_SOURCE', ROOT / 'sources/UniXNU/drivers/NativeMetal'))
if not NATIVE.is_absolute():
    NATIVE = ROOT / NATIVE
OUT = ROOT / 'out/metal/shader-cache'
CACHE = '/Library/GPUBundles/NativeAdrenoMetal.cache'
APP_PATH = '/Applications/Shader Cache.app'
SDK = ROOT / 'toolchains/sdks/MacOSX26.1.sdk'

src = OUT / 'src'
if src.exists():
    shutil.rmtree(src)
(src / 'ShaderCache').mkdir(parents=True)


def copy(name, edits=()):
    text = (NATIVE / name).read_text()
    for old, new in edits:
        assert text.count(old) == 1, (name, old)
        text = text.replace(old, new)
    (src / name).write_text(text)


copy('SharedShaderCache.h', [('static const char kWriterPath[] = "/private/var/tmp/NativeAdrenoMetal.cache";',
                              f'static const char kWriterPath[] = "{CACHE}";   // this guest: the reader\'s directory itself')])
copy('PrimeShaders.h')
# The worker's own changes to priming (the plugin runs none here): patches/shader-cache, in order.
for patch in sorted((ROOT / 'patches/shader-cache').glob('*.patch')):
    subprocess.run(['patch', '-p1', '--quiet', '--no-backup-if-mismatch', '-d', str(src), '-i', str(patch)], check=True)
# The app's place is APP_PATH upstream too (AdrenoMetal 4676b87).
copy('ShaderCache/ShaderCacheState.h', [('@"/private/var/tmp/NativeAdrenoMetal.cache"', f'@"{CACHE}"'),
                                        (f'@"{APP_PATH}"', f'@"{APP_PATH}"')])
# No kernel makes the directory here: the worker does, as root, before it asks whether it may write it.
copy('ShaderCache/ShaderCacheWorker.mm', [('systemcache::writerDirectory().empty()',
                                           '(mkdir(systemcache::kWriterPath, 0755), systemcache::writerDirectory().empty())')])
copy('ShaderCache/ShaderCacheApp.mm')
# The worker holds an idle-sleep assertion while it compiles (IOKit's power management). Upstream's third program, ShaderCacheRegister,
# registers the app with Launch Services at each login, for its place under /Library/UniXNU; under /Applications it is found anyway.
copy('ShaderCache/ShaderCacheActivity.h')

app = OUT / 'Shader Cache.app'
if app.exists():
    shutil.rmtree(app)
code = app / 'Contents/MacOS'
code.mkdir(parents=True)
cxx = ['/usr/lib/llvm-21/bin/clang++', '-target', 'arm64e-apple-macos14.0', '-isysroot', str(SDK), '-std=c++17', '-fobjc-arc', '-O2',
       '-Wall', '-Wextra', '-Wno-deprecated-declarations', '-Wno-unused-function', '-Wno-unused-parameter', '-c', '-x', 'objective-c++']
for name, source, frameworks in [('ShaderCache', 'ShaderCacheApp.mm', ('AppKit', 'Security', 'Foundation')),
                                 ('ShaderCacheWorker', 'ShaderCacheWorker.mm', ('Foundation', 'Metal', 'IOKit'))]:
    obj = OUT / (name + '.o')
    subprocess.run([*cxx, str(src / 'ShaderCache' / source), '-o', str(obj)], check=True)
    subprocess.run(['python3', str(ROOT / 'scripts/apple-ld.py'), '-o', str(code / name), str(obj),
                    *[part for framework in frameworks for part in ('-framework', framework)], '-lobjc', '-lc++', '-lSystem'],
                   check=True)
(app / 'Contents/Info.plist').write_bytes(plistlib.dumps(dict(
    CFBundleIdentifier='org.unixnu.ShaderCache', CFBundleName='Shader Cache', CFBundleDisplayName='Shader Cache',
    CFBundleExecutable='ShaderCache', CFBundlePackageType='APPL', CFBundleVersion='1', CFBundleShortVersionString='1.0',
    LSMinimumSystemVersion='14.0', NSHighResolutionCapable=True, NSPrincipalClass='NSApplication')))
print(app)
