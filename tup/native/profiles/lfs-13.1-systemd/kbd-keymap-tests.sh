#!/bin/bash
# Compile affected maps to binary output; --bkeymap never opens a console or
# loads a kernel keymap. --parse alone would still open the console in kbd 2.10.
# --unicode is the mode this system loads keymaps in: systemd-vconsole-setup
# passes -u to loadkeys on a UTF-8 console. Without a console to ask, loadkeys
# assumes the 8-bit mode, in which upstream's unpatched qwerty/lt.map cannot
# resolve its keysym "quotedblbase" and fails.
set -euo pipefail
export LOADKEYS_INCLUDE_PATH="$PWD/data/keymaps/include:$PWD/data/keymaps/i386/include"
maps=(
  dvorak/dvorak-l.map dvorak/dvorak-r.map fgGIod/tr_f-latin5.map
  qwerty/lt.l4.map qwerty/lt.map qwerty/no-latin1.map qwerty/ru1.map
  qwerty/ru2.map qwerty/ru-cp1251.map qwerty/ru-ms.map qwerty/ru_win.map
  qwerty/se-ir209.map qwerty/se-lat6.map qwerty/tr_q-latin5.map
  qwerty/ua.map qwerty/ua-utf.map qwerty/ua-utf-ws.map qwerty/ua-ws.map
)
[ ! -e native-kbd-keymaps.trs ]
number=0
for map in "${maps[@]}"; do
  number=$((number + 1))
  output=native-keymap-$number.bin
  [ ! -e "$output" ]
  ./src/loadkeys --unicode --bkeymap "data/keymaps/i386/$map" > "$output"
  [ "$(head -c 7 "$output")" = bkeymap ]
  [ "$(wc -c < "$output")" -gt 7 ]
  printf ':test-result: PASS\n:test-name: %s\n' "$map" >> native-kbd-keymaps.trs
done
[ "$number" = 18 ]
