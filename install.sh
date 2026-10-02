#!/usr/bin/env bash
# dawnr's installer, for Linux (x86_64, arm64) and macOS. Nothing needs root; re-running resumes and skips what is
# already there. Into DAWNR_HOME (default ~/.local/share/dawnr) it downloads:
#   - llama.cpp's prebuilt server, a pinned build (github.com/ggml-org/llama.cpp releases),
#   - the base model, Qwen3.5-4B at 4 bits (Apache-2.0, huggingface.co/unsloth/Qwen3.5-4B-GGUF), which writes the
#     independent Python solution the gate checks the specification against,
#   - the dawnr student at 8 bits (this repository's release, or --student FILE),
#   - Dafny 4.11.0 (github.com/dafny-lang/dafny releases), the first of the seven provers;
# and writes a `dawnr` command into ~/.local/bin. The other six provers are optional (see t/README.md).
#
#   ./install.sh [--home DIR] [--student FILE_OR_URL] [--build cpu|vulkan|cuda] [--no-dafny]
set -euo pipefail

REPO=$(cd "$(dirname "$0")" && pwd)
DAWNR_HOME=${DAWNR_HOME:-$HOME/.local/share/dawnr}
BIN_DIR=${BIN_DIR:-$HOME/.local/bin}
LLAMA_TAG=b11342
DAFNY_VERSION=4.11.0
BASE_URL=https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf
STUDENT_URL=${DAWNR_STUDENT_URL:-https://github.com/trestoncuzzort/dawnr/releases/download/student-v1/dawnr-student-4b-q8_0.gguf}
BUILD=cpu
STUDENT=""
DAFNY=1

while [ $# -gt 0 ]; do
  case $1 in
    --home) DAWNR_HOME=$2; shift 2;;
    --student) STUDENT=$2; shift 2;;
    --build) BUILD=$2; shift 2;;
    --no-dafny) DAFNY=0; shift;;
    -h|--help) sed -n '2,13p' "$0"; exit 0;;
    *) echo "install.sh: unknown option $1" >&2; exit 2;;
  esac
done

say() { printf '\033[1m%s\033[0m\n' "$*"; }
fail() { printf 'install.sh: %s\n' "$*" >&2; exit 1; }
fetch() {  # url dest: resumable, fails on HTTP errors
  mkdir -p "$(dirname "$2")"
  if [ -s "$2" ] && [ ! -e "$2.part" ]; then echo "  have $(basename "$2")"; return 0; fi
  echo "  downloading $(basename "$2")"
  if [ -t 1 ]; then QUIET=--progress-bar; else QUIET=-sS; fi       # a meter only on a terminal
  curl -L --fail --retry 3 --continue-at - $QUIET -o "$2.part" "$1" || return 1
  mv "$2.part" "$2"
}

say "Checking this machine"
OS=$(uname -s); ARCH=$(uname -m)
case "$OS-$ARCH" in
  Linux-x86_64) case $BUILD in cpu) LLAMA_ASSET=llama-$LLAMA_TAG-bin-ubuntu-x64.tar.gz;;
                                vulkan) LLAMA_ASSET=llama-$LLAMA_TAG-bin-ubuntu-vulkan-x64.tar.gz;;
                                cuda) LLAMA_ASSET=llama-$LLAMA_TAG-bin-ubuntu-cuda-12.8-x64.tar.gz;;
                                *) fail "--build is cpu, vulkan or cuda";; esac
                DAFNY_ASSET=dafny-$DAFNY_VERSION-x64-ubuntu-22.04.zip;;
  Linux-aarch64|Linux-arm64) LLAMA_ASSET=llama-$LLAMA_TAG-bin-ubuntu-arm64.tar.gz; DAFNY_ASSET="";;
  Darwin-arm64) LLAMA_ASSET=llama-$LLAMA_TAG-bin-macos-arm64.tar.gz; DAFNY_ASSET=dafny-$DAFNY_VERSION-arm64-macos-13.zip;;
  Darwin-x86_64) LLAMA_ASSET=llama-$LLAMA_TAG-bin-macos-x64.tar.gz; DAFNY_ASSET=dafny-$DAFNY_VERSION-x64-macos-13.zip;;
  *) fail "no prebuilt server for $OS $ARCH";;
esac
command -v curl >/dev/null || fail "curl is needed"
command -v tar >/dev/null || fail "tar is needed"
PY=$(command -v python3 || true)
[ -n "$PY" ] || fail "python3 (3.10 or newer) is needed"
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || fail "python3 is $("$PY" -V); 3.10 or newer is needed"
if [ "$OS" = Linux ] && ! command -v bwrap >/dev/null; then
  echo "  note: bubblewrap (bwrap) is missing. dawnr runs model-written Python only inside it, so the independent"
  echo "        Python check will refuse every answer until it is installed (Debian/Ubuntu: sudo apt install bubblewrap)."
fi
echo "  $OS $ARCH, $("$PY" -V), llama.cpp build $LLAMA_TAG ($BUILD)"

say "The model server (llama.cpp)"
fetch "https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA_TAG/$LLAMA_ASSET" "$DAWNR_HOME/downloads/$LLAMA_ASSET" \
  || fail "could not download llama.cpp's $LLAMA_ASSET"
if [ ! -x "$DAWNR_HOME/llama.cpp/llama-server" ]; then
  rm -rf "$DAWNR_HOME/llama.cpp.tmp"; mkdir -p "$DAWNR_HOME/llama.cpp.tmp"
  tar -xzf "$DAWNR_HOME/downloads/$LLAMA_ASSET" -C "$DAWNR_HOME/llama.cpp.tmp"
  SERVER=$(find "$DAWNR_HOME/llama.cpp.tmp" -name llama-server -type f | head -1)
  [ -n "$SERVER" ] || fail "no llama-server in $LLAMA_ASSET"
  rm -rf "$DAWNR_HOME/llama.cpp"; mv "$(dirname "$SERVER")" "$DAWNR_HOME/llama.cpp"; rm -rf "$DAWNR_HOME/llama.cpp.tmp"
fi
"$DAWNR_HOME/llama.cpp/llama-server" --version >/dev/null 2>&1 || fail "llama-server does not run on this machine"
echo "  llama-server ready"

say "The models"
fetch "$BASE_URL" "$DAWNR_HOME/models/Qwen3.5-4B-Q4_K_M.gguf" || fail "could not download the base model"
if [ -n "$STUDENT" ] && [ -f "$STUDENT" ]; then
  ln -sf "$(cd "$(dirname "$STUDENT")" && pwd)/$(basename "$STUDENT")" "$DAWNR_HOME/models/dawnr-student.gguf"
  echo "  student: $STUDENT"
else
  URL=${STUDENT:-$STUDENT_URL}
  fetch "$URL" "$DAWNR_HOME/models/dawnr-student.gguf" \
    || fail "the student model is not downloadable from $URL yet; build or obtain it and pass --student FILE"
fi

if [ "$DAFNY" = 1 ]; then
  say "The first prover (Dafny $DAFNY_VERSION)"
  if [ -z "$DAFNY_ASSET" ]; then
    echo "  no Dafny release for $OS $ARCH; install it yourself (t/README.md)"
  elif [ -x "$DAWNR_HOME/provers/dafny/dafny" ]; then
    echo "  have Dafny"
  else
    command -v unzip >/dev/null || fail "unzip is needed for Dafny"
    fetch "https://github.com/dafny-lang/dafny/releases/download/v$DAFNY_VERSION/$DAFNY_ASSET" "$DAWNR_HOME/downloads/$DAFNY_ASSET" \
      || fail "could not download Dafny"
    mkdir -p "$DAWNR_HOME/provers"; rm -rf "$DAWNR_HOME/provers/dafny"
    unzip -q "$DAWNR_HOME/downloads/$DAFNY_ASSET" -d "$DAWNR_HOME/provers"
  fi
  [ -x "$DAWNR_HOME/provers/dafny/dafny" ] && echo "  $("$DAWNR_HOME/provers/dafny/dafny" --version 2>/dev/null | head -1)"
fi

say "The dawnr command"
mkdir -p "$BIN_DIR" "$DAWNR_HOME"
cat > "$DAWNR_HOME/env" <<ENV
DAWNR_REPO=$REPO
DAWNR_HOME=$DAWNR_HOME
DAWNR_PYTHON=$PY
LLAMA_SERVER=$DAWNR_HOME/llama.cpp/llama-server
STUDENT_GGUF=$DAWNR_HOME/models/dawnr-student.gguf
BASE_GGUF=$DAWNR_HOME/models/Qwen3.5-4B-Q4_K_M.gguf
ENV
[ -x "$DAWNR_HOME/provers/dafny/dafny" ] && echo "T_DAFNY=$DAWNR_HOME/provers/dafny/dafny" >> "$DAWNR_HOME/env"
ln -sf "$REPO/bin/dawnr" "$BIN_DIR/dawnr"
echo "  $BIN_DIR/dawnr"
case ":$PATH:" in *":$BIN_DIR:"*) ;; *) echo "  add $BIN_DIR to your PATH to type 'dawnr' anywhere";; esac
say "Done. Try:  dawnr doctor   then   dawnr ask \"Write a function that doubles a number.\" --test \"assert double(3) == 6\""
