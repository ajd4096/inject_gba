#!/bin/sh
ZELDA=vc-minish/content/alldata.bin
MARIO=vc-mario/content/alldata.bin

./inject_gba.py -z "$ZELDA" -e
./inject_gba.py -m "$MARIO" -e
find . -name \*.gba

find . -name \*.gba -print0 | xargs -0 ./inject_gba.py -z "$ZELDA"
find . -name \*.adb

find . -name \*.gba -print0 | xargs -0 ./inject_gba.py -m "$MARIO"
find . -name \*.adb
