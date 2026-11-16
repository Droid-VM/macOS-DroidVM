#!/bin/sh
set -eu
cd "$(dirname "$0")"
gcc rtsig.c -o build/rtsig
build/rtsig build/rtsig.h
set -- -std=gnu11 -g -O0 -D_GNU_SOURCE -DMLDR_BUILD -D__LITTLE_ENDIAN__ \
    '-DINSTALL_PREFIX="/usr"' -pthread \
    -Isrc/startup/mldr/include -Ibuild -Ibuild/include -Iserver/include
gcc "$@" -include src/startup/mldr/resources/dserver-rpc-defs.h \
    -c build/src/rpc.c -o build/rpc.o
gcc "$@" src/startup/mldr/mldr.c src/startup/mldr/commpage.c \
    src/startup/mldr/elfcalls/elfcalls.c src/startup/mldr/elfcalls/threads.c \
    build/rpc.o -lrt -ldl -lm -o build/mldr
