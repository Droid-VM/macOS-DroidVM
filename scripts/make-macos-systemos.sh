#!/usr/bin/env bash
# Build the SystemOS disk of a macOS root for the virtual machine board on a Linux host with sudo (run on .53).
#
#   make-macos-systemos.sh APFSPROGS_DIR APFS_KO CRYPTEX OS_IMAGE OUTPUT [SIZE_MIB]
#
# The owner chain union-mounts the SystemOS volume read-only over / and the Data volume read-write at /private/var
# (upstream offline-owner-systemos-mount.patch, iOS layout). A sealed macOS System volume has an empty /private: every
# writable path is a firmlink into the Data volume. This disk therefore carries, in one new unsealed APFS volume
# (UUID SYSTEMOS_UUID, the 21H461 one the upstream patch names):
#   - the Cryptex1,SystemOS content (CRYPTEX, the raw APFS member: arm64e dyld shared cache, ...), also reachable as
#     /System/Volumes/Preboot/Cryptexes/OS;
#   - the read-only firmlink targets of the macOS Data template (/System/Library/Templates/Data of OS_IMAGE): assets,
#     CoreTypes, Speech, cups, snmp; and its bulky read-only /Library parts under /System/Volumes/Data/Library, which
#     the Data seed links to;
#   - private/var (the Data mount point), private/etc and private/tmp, and symbolic links in place of the writable
#     firmlinks (/Library, /Users, /Applications, /Volumes, /cores, /opt, /usr/local, /System/Library/Caches) into
#     /private/var/.data, which make-macos-data-seed.sh fills.
# Sign it with make-virt-root.py like the iOS SystemOS member.
set -euo pipefail
APFSPROGS=$1
APFS_KO=$2
CRYPTEX=$3
OS_IMAGE=$4
OUT=$5
SIZE_MIB=${6:-7168}
VOLUME_UUID=${SYSTEMOS_UUID:-8846FE78-2910-4297-AF97-D59BB6F8FC16}
[ -e "$OUT" ] && { echo "$OUT exists" >&2; exit 1; }
truncate -s "${SIZE_MIB}M" "$OUT"
"$APFSPROGS/mkapfs/mkapfs" -L SystemOS -u "$VOLUME_UUID" "$OUT"

LOADED=0
if ! grep -q '^apfs ' /proc/modules; then
  sudo insmod "$APFS_KO"
  LOADED=1
fi
LOOP=$(sudo losetup --find --show "$OUT")
CX_LOOP=$(sudo losetup --find --show --read-only "$CRYPTEX")
OS_LOOP=$(sudo losetup --find --show --read-only --offset "${OS_OFFSET:-209732608}" "$OS_IMAGE")
MNT=$(mktemp -d)
CXM=$(mktemp -d)
OSM=$(mktemp -d)
cleanup() {
  for mount in "$MNT" "$CXM" "$OSM"; do
    mountpoint -q "$mount" && sudo umount "$mount"
    rmdir -- "$mount" 2>/dev/null || true
  done
  for loop in "${LOOP:-}" "${CX_LOOP:-}" "${OS_LOOP:-}"; do
    [ -n "$loop" ] && sudo losetup -d "$loop" 2>/dev/null || true
  done
  [ "$LOADED" = 1 ] && sudo rmmod apfs 2>/dev/null || true
}
trap cleanup EXIT
sudo mount -t apfs -o readwrite "$LOOP" "$MNT"
sudo mount -t apfs -o ro "$CX_LOOP" "$CXM"
sudo mount -t apfs -o ro "$OS_LOOP" "$OSM"
TEMPLATE=$OSM/System/Library/Templates/Data

# The cryptex files are APFS-compressed and land uncompressed here: leave out the x86_64 and Rosetta (aot) caches.
sudo rsync -aH --exclude='/System/Library/dyld/dyld_shared_cache_x86_64*' --exclude='/System/Library/dyld/aot_shared_cache*' \
  "$CXM/" "$MNT/"
sudo mkdir -p "$MNT/System/Volumes/Preboot/Cryptexes"
sudo ln -s / "$MNT/System/Volumes/Preboot/Cryptexes/OS"
for path in System/Library/Assets System/Library/AssetsV2 System/Library/PreinstalledAssets \
            System/Library/PreinstalledAssetsV2 System/Library/Speech \
            System/Library/CoreServices/CoreTypes.bundle/Contents/Library usr/libexec/cups usr/share/snmp; do
  if [ -e "$TEMPLATE/$path" ]; then
    sudo mkdir -p "$MNT/$(dirname "$path")"
    sudo rsync -aH "$TEMPLATE/$path" "$MNT/$(dirname "$path")/"
  fi
done
for path in Library/Apple "Library/Application Support/Apple" Library/Documentation Library/WebServer; do
  sudo mkdir -p "$MNT/System/Volumes/Data/$(dirname "$path")"
  sudo rsync -aH "$TEMPLATE/$path" "$MNT/System/Volumes/Data/$(dirname "$path")/"
done
for path in Library Users Applications Volumes cores opt usr/local System/Library/Caches; do
  sudo mkdir -p "$MNT/$(dirname "$path")"
  sudo ln -s "/private/var/.data/$path" "$MNT/$path"
done
# Bring-up shims (overlay/systemos-shims, the tree is copied over the volume): launchd's boot jobs fsck and mount-phase-1/2 do not
# work against the iPadOS Sandbox policy and the read-only container; /sbin/mount stays reachable as mount.real.
SHIMS=$(cd "$(dirname "$0")/.." && pwd)/overlay/systemos-shims
sudo mkdir -p "$MNT/sbin"
sudo install -m 755 "$OSM/sbin/mount" "$MNT/sbin/mount.real"
sudo cp -a "$SHIMS/." "$MNT/"
sudo mkdir -p "$MNT/private/var"
sudo ln -s var/.data/private/etc "$MNT/private/etc"
sudo ln -s var/tmp "$MNT/private/tmp"
sudo find "$MNT" -maxdepth 1 -exec ls -lad {} + | head -40
sudo du -sh "$MNT"
sync
cleanup
trap - EXIT
python3 -I "$(dirname "$0")/apfs-volumes.py" "$OUT" | tail -1
