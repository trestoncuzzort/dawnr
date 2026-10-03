#!/usr/bin/env bash
# dawnr's installer, for Linux (x86_64, arm64; Windows through WSL2) and macOS. The installer needs no root (a fresh
# Ubuntu needs `sudo apt install libgomp1 unzip` once, which it asks for); re-running resumes and skips what is
# already there. Into DAWNR_HOME (default ~/.local/share/dawnr) it downloads:
#   - llama.cpp's prebuilt server, a pinned build (github.com/ggml-org/llama.cpp releases),
#   - the base model, Qwen3.5-4B at 4 bits (Apache-2.0, huggingface.co/unsloth/Qwen3.5-4B-GGUF), which writes the
#     independent Python solution the gate checks the specification against,
#   - the dawnr student at 8 bits (this repository's release, or --student FILE),
#   - Dafny 4.11.0 (github.com/dafny-lang/dafny releases), the first of the seven provers;
# and writes a `dawnr` command into ~/.local/bin. The other six provers are optional (see t/README.md).
#
#   ./install.sh [--home DIR] [--student FILE_OR_RELEASE_URL] [--build auto|cpu|vulkan|cuda] [--no-dafny]
# --build auto (the default) takes CUDA when an NVIDIA GPU answers nvidia-smi (WSL2 included), else the CPU build.
# Every download is checked against the SHA-256 its publisher lists.
set -euo pipefail

REPO=$(cd "$(dirname "$0")" && pwd)
DAWNR_HOME=${DAWNR_HOME:-$HOME/.local/share/dawnr}
BIN_DIR=${BIN_DIR:-$HOME/.local/bin}
LLAMA_TAG=b11342
DAFNY_VERSION=4.11.0
BASE_URL=https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf
STUDENT_RELEASE=${DAWNR_STUDENT_RELEASE:-https://github.com/trestoncuzzort/dawnr/releases/download/student-v1}
BUILD=auto
STUDENT=""
DAFNY=1

while [ $# -gt 0 ]; do
  case $1 in
    --home) DAWNR_HOME=$2; shift 2;;
    --student) STUDENT=$2; shift 2;;
    --build) BUILD=$2; shift 2;;
    --no-dafny) DAFNY=0; shift;;
    -h|--help) sed -n '2,/^set -euo/p' "$0" | grep '^#'; exit 0;;
    *) echo "install.sh: unknown option $1" >&2; exit 2;;
  esac
done

say() { printf '\033[1m%s\033[0m\n' "$*"; }
fail() { printf 'install.sh: %s\n' "$*" >&2; exit 1; }
sha256() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -c1-64; else shasum -a 256 "$1" | cut -c1-64; fi; }
fetch() {  # url dest [sha256]: resumable, fails on HTTP errors, and on a checksum that differs from the published one
  mkdir -p "$(dirname "$2")"
  if [ -s "$2" ] && [ ! -e "$2.part" ]; then
    if [ -z "${3:-}" ] || [ "$(sha256 "$2")" = "$3" ]; then echo "  have $(basename "$2")"; return 0; fi
    echo "  $(basename "$2") does not match its checksum; downloading it again"; rm -f "$2"
  fi
  echo "  downloading $(basename "$2")"
  if [ -t 1 ]; then QUIET=--progress-bar; else QUIET=-sS; fi       # a meter only on a terminal
  curl -L --fail --retry 3 --continue-at - $QUIET -o "$2.part" "$1" || return 1
  if [ -n "${3:-}" ] && [ "$(sha256 "$2.part")" != "$3" ]; then
    rm -f "$2.part"; echo "  $(basename "$2"): checksum mismatch, removed" >&2; return 1
  fi
  mv "$2.part" "$2"
}
# Published SHA-256s of the pinned downloads (GitHub's release digests; Hugging Face's LFS hash), read 2026-10-02.
sum_of() {
  case $1 in
    llama-b11342-bin-ubuntu-x64.tar.gz) echo 7c8f7eb14cfb4a8dceb1f6cc6220ea387a1940f0c95cab76ca63ac35d2934fd4;;
    llama-b11342-bin-ubuntu-vulkan-x64.tar.gz) echo e88910ac1a46955f8d088a2b518245c32d620a02c954906e0a05884dca48e5be;;
    llama-b11342-bin-ubuntu-cuda-12.8-x64.tar.gz) echo e8e5b32e1abf829c08e24c7c99aa4f66dc046100682260b1625a272d1f80e8d1;;
    cudart-llama-b11342-bin-ubuntu-cuda-12.8-x64.tar.gz) echo b3e2535f674f8df5ed28cd66e8dbcb6f64b2f675f2a8bb2bbfce4bd9c8bdaa22;;
    llama-b11342-bin-ubuntu-arm64.tar.gz) echo 6f5f88d9e105230c32b13ad9d8bba9611ab29ee27532717ba6bb5bb4120f3c85;;
    llama-b11342-bin-macos-arm64.tar.gz) echo 1050318ed5fb941a1b4c1c603f6c3c7fd3f065b56af3b8cfab39aee70f3ad076;;
    llama-b11342-bin-macos-x64.tar.gz) echo f5603510bcf2374d02ee1bd5ab1d307b60dec9f9c03fa67dd88a6c049089e49a;;
    dafny-4.11.0-x64-ubuntu-22.04.zip) echo a46a9ff7cdd720f7955854c78e95df13f4cfe6b80691b05f8654fe19e8267179;;
    dafny-4.11.0-arm64-macos-13.zip) echo c90c75e7d5db9c6ccbb7127840dfe43f0ac938b039a7ebed146d8ead383a572f;;
    dafny-4.11.0-x64-macos-13.zip) echo 5fc0de946c5b2fad33f16bd22a5b06f4fd0dfa7f6d770284237e3f1f3ca9f73d;;
    Qwen3.5-4B-Q4_K_M.gguf) echo 00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4;;
  esac
}

say "Checking this machine"
OS=$(uname -s); ARCH=$(uname -m)
case "$OS-$ARCH" in
  Linux-x86_64)
                # auto: an NVIDIA GPU that answers nvidia-smi (on PATH, or WSL2's /usr/lib/wsl/lib) gets the CUDA build
                if [ "$BUILD" = auto ]; then
                  BUILD=cpu
                  for smi in nvidia-smi /usr/lib/wsl/lib/nvidia-smi; do
                    "$smi" -L >/dev/null 2>&1 && { BUILD=cuda; break; }
                  done
                fi
                case $BUILD in cpu) LLAMA_ASSET=llama-$LLAMA_TAG-bin-ubuntu-x64.tar.gz;;
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
# what a fresh Ubuntu lacks (WSL's Ubuntu 26.04 image, measured 2026-10-03), asked for before anything downloads:
# llama.cpp's Linux builds link the GNU OpenMP runtime, which its own Docker images add as libgomp1
# (github.com/ggml-org/llama.cpp .devops/cpu.Dockerfile), and Dafny comes as a zip
NEED=""
if [ "$OS" = Linux ]; then
  LIBS=$(/sbin/ldconfig -p 2>/dev/null || ldconfig -p 2>/dev/null || true)
  [ -z "$LIBS" ] || grep -q 'libgomp\.so\.1' <<< "$LIBS" || NEED="$NEED libgomp1"
fi
[ "$DAFNY" = 0 ] || command -v unzip >/dev/null || NEED="$NEED unzip"
[ -z "$NEED" ] || fail "this machine lacks$NEED. On Ubuntu or Debian (WSL included) run:  sudo apt install$NEED
  (Fedora: sudo dnf install${NEED/libgomp1/libgomp}) and then ./install.sh again"
# dawnr runs model-written Python only in a sandbox; probed with the flags the jobs use (t/py_sandbox.py)
if ! WHY=$(cd "$REPO" && "$PY" -c 'import sys; sys.path.insert(0, "t"); import py_sandbox
ok = py_sandbox.available(); ok or print(py_sandbox.why_unavailable()); sys.exit(0 if ok else 1)'); then
  echo "  note: 'dawnr ask' will stop until this is fixed: $WHY"
fi
if [ "$OS" = Darwin ]; then
  echo "  note: on macOS model-written Python runs under Apple's Seatbelt (sandbox-exec) with Codex CLI's policies;"
  echo "        install and a first question pass on GitHub's Mac runner. If answers come back as 'no reply from the"
  echo "        model', run with DAWNR_GPU_LAYERS=0 (the CPU instead of Metal)."
fi
echo "  $OS $ARCH, $("$PY" -V), llama.cpp build $LLAMA_TAG ($BUILD)"

say "The model server (llama.cpp)"
fetch "https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA_TAG/$LLAMA_ASSET" "$DAWNR_HOME/downloads/$LLAMA_ASSET" "$(sum_of "$LLAMA_ASSET")" \
  || fail "could not download llama.cpp's $LLAMA_ASSET"
if [ ! -x "$DAWNR_HOME/llama.cpp/llama-server" ]; then
  rm -rf "$DAWNR_HOME/llama.cpp.tmp"; mkdir -p "$DAWNR_HOME/llama.cpp.tmp"
  tar -xzf "$DAWNR_HOME/downloads/$LLAMA_ASSET" -C "$DAWNR_HOME/llama.cpp.tmp"
  SERVER=$(find "$DAWNR_HOME/llama.cpp.tmp" -name llama-server -type f | head -1)
  [ -n "$SERVER" ] || fail "no llama-server in $LLAMA_ASSET"
  rm -rf "$DAWNR_HOME/llama.cpp"; mv "$(dirname "$SERVER")" "$DAWNR_HOME/llama.cpp"; rm -rf "$DAWNR_HOME/llama.cpp.tmp"
fi
if [ "$BUILD" = cuda ] && [ ! -e "$DAWNR_HOME/llama.cpp/.cudart" ]; then
  # the CUDA build needs the CUDA runtime and cuBLAS, which llama.cpp publishes beside it; a machine with only the
  # NVIDIA driver (a Windows laptop's WSL2, most desktops) has neither
  CUDART=cudart-$LLAMA_ASSET
  fetch "https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA_TAG/$CUDART" "$DAWNR_HOME/downloads/$CUDART" "$(sum_of "$CUDART")" \
    || fail "could not download llama.cpp's $CUDART"
  rm -rf "$DAWNR_HOME/cudart.tmp"; mkdir -p "$DAWNR_HOME/cudart.tmp"
  tar -xzf "$DAWNR_HOME/downloads/$CUDART" -C "$DAWNR_HOME/cudart.tmp"
  find "$DAWNR_HOME/cudart.tmp" -name "*.so*" -exec cp -P {} "$DAWNR_HOME/llama.cpp/" \;
  rm -rf "$DAWNR_HOME/cudart.tmp"; touch "$DAWNR_HOME/llama.cpp/.cudart"
fi
if ! LD_LIBRARY_PATH="$DAWNR_HOME/llama.cpp:${LD_LIBRARY_PATH:-}" "$DAWNR_HOME/llama.cpp/llama-server" --version >/dev/null 2>&1; then
  MISSING=$(command -v ldd >/dev/null && LD_LIBRARY_PATH="$DAWNR_HOME/llama.cpp:${LD_LIBRARY_PATH:-}" \
    ldd "$DAWNR_HOME/llama.cpp/llama-server" 2>/dev/null | awk '/not found/ {print $1}' | sort -u | tr '\n' ' ' || true)
  fail "llama-server does not run on this machine${MISSING:+; it cannot find: $MISSING}"
fi
echo "  llama-server ready"

say "The models"
fetch "$BASE_URL" "$DAWNR_HOME/models/Qwen3.5-4B-Q4_K_M.gguf" "$(sum_of Qwen3.5-4B-Q4_K_M.gguf)" || fail "could not download the base model"
if [ -n "$STUDENT" ] && [ -f "$STUDENT" ]; then
  # used where it is: a split model is found from its first shard's own name (llama.cpp's gguf-split)
  STUDENT_GGUF="$(cd "$(dirname "$STUDENT")" && pwd)/$(basename "$STUDENT")"
  echo "  student: $STUDENT_GGUF"
else
  # the release carries the student as shards under GitHub's 2 GiB a file, listed with their SHA-256s in a manifest
  BASE=${STUDENT:-$STUDENT_RELEASE}
  fetch "$BASE/dawnr-student.sha256" "$DAWNR_HOME/models/dawnr-student.sha256" \
    || fail "the student model is not published yet at $BASE; pass --student FILE"
  STUDENT_GGUF=""
  while read -r sum name; do
    [ -n "$name" ] || continue
    fetch "$BASE/$name" "$DAWNR_HOME/models/$name" "$sum" || fail "could not download $name"
    [ -z "$STUDENT_GGUF" ] && STUDENT_GGUF="$DAWNR_HOME/models/$name"
  done < "$DAWNR_HOME/models/dawnr-student.sha256"
  [ -n "$STUDENT_GGUF" ] || fail "the student manifest lists no files"
fi

if [ "$DAFNY" = 1 ]; then
  say "The first prover (Dafny $DAFNY_VERSION)"
  if [ -z "$DAFNY_ASSET" ]; then
    echo "  no Dafny release for $OS $ARCH; install it yourself (t/README.md)"
  elif [ -x "$DAWNR_HOME/provers/dafny/dafny" ]; then
    echo "  have Dafny"
  else
    command -v unzip >/dev/null || fail "unzip is needed for Dafny"
    fetch "https://github.com/dafny-lang/dafny/releases/download/v$DAFNY_VERSION/$DAFNY_ASSET" "$DAWNR_HOME/downloads/$DAFNY_ASSET" "$(sum_of "$DAFNY_ASSET")" \
      || fail "could not download Dafny"
    mkdir -p "$DAWNR_HOME/provers"; rm -rf "$DAWNR_HOME/provers/dafny"
    unzip -q "$DAWNR_HOME/downloads/$DAFNY_ASSET" -d "$DAWNR_HOME/provers"
  fi
  if [ -x "$DAWNR_HOME/provers/dafny/dafny" ]; then
    # Dafny is a .NET program, and .NET stops at start without the ICU library, which a fresh Ubuntu (WSL's included)
    # lacks. Its globalization-invariant mode needs no ICU and changes only culture-aware casing, sorting, normalization
    # and formatting (github.com/dotnet/runtime docs/design/features/globalization-invariant-mode.md); measured
    # 2026-10-03: the same 164 Dafny verdicts in both modes (82 tasks, real and twin: verified, refuted, unproved,
    # timeout). So it is turned on only where ICU is missing.
    INVARIANT=""
    if [ "$OS" = Linux ]; then
      LIBS=$(/sbin/ldconfig -p 2>/dev/null || ldconfig -p 2>/dev/null || true)
      [ -z "$LIBS" ] || grep -q 'libicuuc\.so' <<< "$LIBS" || INVARIANT=1
    fi
    V=$(env ${INVARIANT:+DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1} "$DAWNR_HOME/provers/dafny/dafny" --version 2>&1) \
      || fail "Dafny does not run on this machine: ${V%%$'\n'*}"
    NOTE=""; [ -z "$INVARIANT" ] || NOTE=" (no ICU library here, so it runs in the .NET invariant mode)"
    echo "  dafny ${V%%$'\n'*}$NOTE"
  fi
fi

say "The dawnr command"
mkdir -p "$BIN_DIR" "$DAWNR_HOME"
cat > "$DAWNR_HOME/env" <<ENV
DAWNR_REPO=$REPO
DAWNR_HOME=$DAWNR_HOME
DAWNR_PYTHON=$PY
LLAMA_SERVER=$DAWNR_HOME/llama.cpp/llama-server
DAWNR_BUILD=$BUILD
STUDENT_GGUF=$STUDENT_GGUF
BASE_GGUF=$DAWNR_HOME/models/Qwen3.5-4B-Q4_K_M.gguf
ENV
[ -x "$DAWNR_HOME/provers/dafny/dafny" ] && echo "T_DAFNY=$DAWNR_HOME/provers/dafny/dafny" >> "$DAWNR_HOME/env"
[ -n "${INVARIANT:-}" ] && echo "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1" >> "$DAWNR_HOME/env"
ln -sf "$REPO/bin/dawnr" "$BIN_DIR/dawnr"
echo "  $BIN_DIR/dawnr"
case ":$PATH:" in *":$BIN_DIR:"*) ;; *) echo "  add $BIN_DIR to your PATH to type 'dawnr' anywhere";; esac
say "Done. Try:  dawnr doctor   then   dawnr ask \"Write a function that doubles a number.\" --test \"assert double(3) == 6\""
