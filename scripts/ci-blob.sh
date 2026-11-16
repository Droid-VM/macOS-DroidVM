#!/usr/bin/env bash
# Encrypted, split archives of the CI (.github/workflows/image.yml): the IPSW inputs it keeps as release assets and the images it
# produces. Anything holding Apple's files is only ever stored this way (the repository's ARTIFACT_KEY, as the other workflows).
#
#   ci-blob.sh pack PREFIX DIR NAME...     tar (holes kept) of DIR's NAMEs | zstd | openssl AES-256-CBC (PBKDF2) | split into
#                                          PREFIX.000, PREFIX.001, ... of CI_BLOB_CHUNK (default 1900m: a release asset is at most
#                                          2 GiB); PREFIX.sha256 lists the parts
#   ci-blob.sh unpack DEST PART...         the parts in order (a glob sorts them) | decrypt | unzstd | untar into DEST
#   ci-blob.sh fetch RELEASE PREFIX DEST   a release's parts (PREFIX.sha256 lists them) downloaded one after another straight
#                                          into unpack: no copy on disk, the download and the unpacking overlap; a damaged
#                                          part fails zstd's frame checksum
#
# The key is $ARTIFACT_KEY. To unpack a downloaded image by hand:
#   ARTIFACT_KEY=... scripts/ci-blob.sh unpack out/ci-image image.tar.zst.enc.[0-9][0-9][0-9]
set -euo pipefail
: "${ARTIFACT_KEY:?ARTIFACT_KEY is not set}"
case "${1:-}" in
  pack)
    prefix=$2 dir=$3; shift 3
    mkdir -p "$(dirname "$prefix")"
    tar --sparse -C "$dir" -cf - "$@" | zstd -T0 -6 -q -c \
      | openssl enc -aes-256-cbc -pbkdf2 -salt -pass env:ARTIFACT_KEY \
      | split -b "${CI_BLOB_CHUNK:-1900m}" -d -a 3 - "$prefix."
    (cd "$(dirname "$prefix")" && sha256sum "$(basename "$prefix")".[0-9][0-9][0-9]) > "$prefix.sha256"
    ls -la "$prefix".*
    ;;
  unpack)
    dest=$2; shift 2
    mkdir -p "$dest"
    cat "$@" | openssl enc -d -aes-256-cbc -pbkdf2 -pass env:ARTIFACT_KEY | zstd -d -q -c | tar --sparse -C "$dest" -xf -
    ;;
  fetch)
    release=$2 prefix=$3 dest=$4
    mkdir -p "$dest"
    gh release download "$release" --pattern "$prefix.sha256" --output - | while read -r _ name; do
      gh release download "$release" --pattern "$name" --output - </dev/null
    done | openssl enc -d -aes-256-cbc -pbkdf2 -pass env:ARTIFACT_KEY | zstd -d -q -c | tar --sparse -C "$dest" -xf -
    ;;
  *)
    sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
