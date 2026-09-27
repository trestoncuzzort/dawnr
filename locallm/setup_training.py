#!/usr/bin/env python3
"""setup_training.py -- set up a training-capable Python environment for locallm.

    python3 setup_training.py

Builds a virtual environment inside this folder and installs the PyTorch build
that matches this machine, so `studio.py` and `train.py` can train instead of
only talking to a model that is already trained. Nothing here is required to
use the app: `home.py`, `plain_generate.py` and the included model work with no
PyTorch and no network at all (see START-HERE.md).

STDLIB ONLY, for the same reason install.py and check_my_computer.py are: this
is a setup step that has to run on a machine where nothing beyond Python is
installed yet, so it cannot import anything it might be the one to install.

HOW IT INSTALLS PYTORCH, AND WHY THAT CHANGED FROM install.py. install.py picks
one of exactly two indexes -- a single hardcoded CUDA build or the CPU build --
by asking whether `nvidia-smi` exists at all. That is one bit of information
thrown away: a driver too old for the pinned CUDA build looks identical to no
driver, and the failure ("torch installed fine but sees no graphics card") shows
up long after setup claimed success. This script instead uses uv's own PyTorch
integration, which asks the driver ITS VERSION and picks the newest CUDA index
that driver can actually run, automatically:

    uv pip install torch --torch-backend=auto

uv queries the installed CUDA driver, AMD GPU or Intel GPU and selects the
matching PyTorch index, falling back to the CPU-only build if it finds none
(docs.astral.sh/uv/guides/integration/pytorch/, "Automatic backend selection").
`--torch-backend` needs uv 0.6.9 or newer (where it shipped, preview) and was
stabilised -- `--preview` is no longer needed -- in uv 0.7.14
(github.com/astral-sh/uv/pull/12070, github.com/astral-sh/uv/pull/14119). The
version pinned below is well past both.

GETTING uv ITSELF, WITHOUT `curl | sh`. The installer astral-sh publishes pipes
a script into a shell, which is exactly the pattern this project's own
supply-chain posture refuses: no verification happens before code from the
network executes. Instead this downloads the same release ASSET the installer
script would have (a plain tarball or zip from a versioned GitHub Releases URL,
no code execution), checks its bytes against a sha256 PINNED IN THIS FILE
before anything is extracted, and only then unpacks the one binary it needs.
The pin is a deliberate supply-chain choice: a hash fetched over the same
network path at install time would not catch a compromise of that path, so the
value has to already be in source control, reviewed like any other line here.
Checksums were read from each release asset's own `.sha256` file at
github.com/astral-sh/uv/releases/tag/0.12.19 (astral-sh's cargo-dist release
process publishes one per asset).

WHEN uv CANNOT BE USED -- no pinned build for this OS/CPU combination, `--no-uv`
was passed, or the network is refused -- CUDA_WHEEL_TABLE below picks a
PyTorch wheel index from the NVIDIA driver version directly, the same
information `uv --torch-backend=auto` uses internally, so the fallback degrades
gracefully instead of guessing. Its thresholds and the approach of reading
`nvidia-smi --query-gpu=driver_version` both come from light-the-torch
(github.com/Slicer/light-the-torch, light_the_torch/_cb.py), a maintained tool
that solves exactly this problem; the numbers there are NVIDIA's own published
minimum driver version for CUDA minor-version compatibility (a driver that
supports CUDA X.0 can run a PyTorch wheel built against any later X.y toolkit),
from the "CUDA Toolkit and Corresponding Driver Version" table in each CUDA
release's own release notes (docs.nvidia.com/cuda/archive/<ver>/cuda-toolkit-
release-notes/).

CONSENT AND OFFLINE. Nothing is downloaded without the user first seeing what
and agreeing (`--yes` skips the prompt for scripted use; declining, or piping
stdin with no `--yes`, refuses rather than downloading). `--offline` refuses
outright the moment anything would need the network, and says exactly what
would have been fetched and how to place it by hand -- the same shape of
refusal `t/RUN-NEXT-locallm-r12.md` and `AGENTS.md` rule 2 ask for elsewhere in
this repository: an honest refusal instead of a guess.

EVERYTHING LIVES INSIDE THIS FOLDER. The virtual environment
(`.venv-train`, matching the name `Train My AI.bat` and `Check My Computer.bat`
already look for and the name already reserved in `.gitignore`), the fetched uv
binary, and uv's own package cache (`UV_CACHE_DIR`, so a re-run does not refetch
wheels from outside this tree) all live under this folder. Nothing is written
to the registry, to `$HOME`, or anywhere else on the machine.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MIN_PYTHON = (3, 10)

# Where everything this script manages lives. All inside this folder, on
# purpose -- see the docstring's "EVERYTHING LIVES INSIDE THIS FOLDER".
VENV_DIR = HERE / ".venv-train"
TOOLS_DIR = HERE / ".tools"
DOWNLOADS_DIR = TOOLS_DIR / "downloads"
UV_INSTALL_ROOT = TOOLS_DIR / "uv"
UV_CACHE_DIR = TOOLS_DIR / "uv-cache"

# ---------------------------------------------------------------------------
# The pinned uv release. Bump both together, from a release's own asset page.
# ---------------------------------------------------------------------------
UV_VERSION = "0.12.19"
UV_BASE_URL = f"https://github.com/astral-sh/uv/releases/download/{UV_VERSION}"

# (system, arch) -> (release asset filename, its published sha256).
# system/arch are platform_key()'s normalized names, not Rust target triples.
# Checksums copied from each asset's own `<name>.sha256` file, read 2026-09-27
# (github.com/astral-sh/uv/releases/tag/0.12.19); not every platform uv ships
# for is listed, only the ones this product targets (Windows, macOS, Linux) --
# an unlisted platform falls back to the stdlib path below rather than failing.
UV_RELEASES: dict[tuple[str, str], tuple[str, str]] = {
    ("linux", "x86_64"): (
        "uv-x86_64-unknown-linux-gnu.tar.gz",
        "23bf5552d220e0842b65c862097b2ebaeba0064b74eda5e565e77fd25969d8c8"),
    ("linux", "aarch64"): (
        "uv-aarch64-unknown-linux-gnu.tar.gz",
        "0804e9b164c64b6914182d5920c08551958a095986f10a3731056df701126436"),
    ("darwin", "aarch64"): (
        "uv-aarch64-apple-darwin.tar.gz",
        "a9a8df1eedeb192f2e47e40e2faabfb387db4b850209118786d42f89dde3e0ba"),
    ("darwin", "x86_64"): (
        "uv-x86_64-apple-darwin.tar.gz",
        "cb5fa57bafe68fc0fb94b17f06bee0b0b9a7feb94ccbd110445afa0696e39273"),
    ("windows", "x86_64"): (
        "uv-x86_64-pc-windows-msvc.zip",
        "6dbb02d79e419522f1c500f0adb1cddcff0cda7d59b0d66ea7f5e3b4a1b2f5f0"),
}

# ---------------------------------------------------------------------------
# The stdlib fallback's driver -> PyTorch wheel index table. Newest first;
# see the docstring for where these numbers and this approach come from.
# ---------------------------------------------------------------------------
WHEEL_INDEX_BASE = "https://download.pytorch.org/whl/"
CPU_WHEEL = "cpu"
# (pytorch index name, minimum Linux driver, minimum Windows driver)
CUDA_WHEEL_TABLE: tuple[tuple[str, tuple[int, ...], tuple[int, ...]], ...] = (
    ("cu130", (580, 65, 6), (580, 0, 0)),
    ("cu128", (525, 60, 13), (528, 33)),
    ("cu118", (450, 80, 2), (452, 39)),
)


class SetupError(Exception):
    """Something needs the user's attention. Printed as a sentence, not a
    traceback -- see main()."""


class ChecksumMismatch(SetupError):
    """A downloaded or locally-placed file does not match its pinned hash."""


def say(msg: str = "") -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# Platform identification and venv layout -- pure functions, no I/O.
# ---------------------------------------------------------------------------
def platform_key() -> tuple[str, str]:
    """This machine's (system, arch), normalized to UV_RELEASES' spelling.

    Two names collapse to one each: "amd64" and "x86_64" are the same chip,
    and Apple spells 64-bit ARM "arm64" where the uv/Linux world spells it
    "aarch64" -- platform.machine() gives back whichever the OS itself uses.
    """
    system = platform.system().lower()
    raw = platform.machine().lower()
    if raw in ("amd64", "x86_64"):
        arch = "x86_64"
    elif raw in ("arm64", "aarch64"):
        arch = "aarch64"
    else:
        arch = raw
    return system, arch


def venv_python(venv_dir: Path, os_name: str = os.name) -> Path:
    """Where the interpreter lives inside a venv, on os_name's layout.

    Parameterized on os_name (default: the real os.name) rather than reading
    the global directly, so the Windows and POSIX layouts are both checkable
    from any one machine's test run.
    """
    if os_name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def uv_binary_name(system: str) -> str:
    return "uv.exe" if system == "windows" else "uv"


def uv_install_dir(key: tuple[str, str]) -> Path:
    system, arch = key
    return UV_INSTALL_ROOT / UV_VERSION / f"{system}-{arch}"


def cached_uv_path(key: tuple[str, str]) -> Path | None:
    """A uv binary already fetched and extracted by a previous run, if any.

    Existence at this exact version-qualified path IS the "verified" signal:
    verify_and_extract_uv() is the only code that ever writes here, and only
    after a checksum match, so nothing re-checks it on every run.
    """
    p = uv_install_dir(key) / uv_binary_name(key[0])
    return p if p.is_file() else None


# ---------------------------------------------------------------------------
# Consent.
# ---------------------------------------------------------------------------
def confirm(prompt: str, assume_yes: bool) -> bool:
    """Ask before doing anything that reaches the network.

    Declines rather than hanging when stdin is not a terminal and --yes was
    not passed (a script or CI invocation with nobody to answer), instead of
    blocking on input() forever.
    """
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        return False
    try:
        answer = input(f"{prompt} [y/N] ")
    except EOFError:
        return False
    return answer.strip().lower() in ("y", "yes")


# ---------------------------------------------------------------------------
# The stdlib fallback: which PyTorch wheel index for this driver.
# ---------------------------------------------------------------------------
def parse_driver_version(text: str) -> tuple[int, ...]:
    """"550.54.14" -> (550, 54, 14). Empty on anything with no digits."""
    return tuple(int(p) for p in re.findall(r"\d+", text))


def nvidia_driver_info() -> tuple[str, str] | None:
    """(gpu name, driver version string), or None if nvidia-smi is not here.

    Its absence is the signal, the same reasoning install.py's has_nvidia_gpu
    uses: no driver means nothing CUDA-capable is worth asking further about.
    """
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        p = subprocess.run(
            [exe, "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if p.returncode != 0 or not p.stdout.strip():
        return None
    name, _, driver = p.stdout.strip().splitlines()[0].rpartition(",")
    if not name:
        return None
    return name.strip(), driver.strip()


def pick_wheel_index(system: str, driver_info: tuple[str, str] | None) -> tuple[str, str]:
    """Which download.pytorch.org index this machine should install from, and why.

    Only used by the stdlib fallback -- the uv path leaves this decision to
    `--torch-backend=auto`, which asks the driver itself.
    """
    if system == "darwin":
        return (WHEEL_INDEX_BASE + CPU_WHEEL,
                "macOS has no CUDA build; using the universal CPU/Apple-silicon build")
    if driver_info is None:
        return WHEEL_INDEX_BASE + CPU_WHEEL, "no NVIDIA driver found"
    name, driver_str = driver_info
    driver = parse_driver_version(driver_str)
    if not driver:
        return (WHEEL_INDEX_BASE + CPU_WHEEL,
                f"{name}: could not read a driver version from {driver_str!r}")
    windows = system == "windows"
    for cuda, min_linux, min_windows in CUDA_WHEEL_TABLE:
        threshold = min_windows if windows else min_linux
        if driver >= threshold:
            return WHEEL_INDEX_BASE + cuda, f"{name}, driver {driver_str} supports {cuda}"
    oldest, min_linux, min_windows = CUDA_WHEEL_TABLE[-1]
    needs = min_windows if windows else min_linux
    needed = ".".join(str(n) for n in needs)
    return (WHEEL_INDEX_BASE + CPU_WHEEL,
            f"{name}, driver {driver_str} is older than {oldest} needs ({needed})")


def unusable_nvidia_message(name: str, driver: str, index_url: str) -> str:
    """What to tell someone whose NVIDIA card the installed PyTorch cannot use
    -- the exact fix, not just "get the CUDA build". Used by
    check_my_computer.py, which has already confirmed torch.cuda.is_available()
    is False on a machine nvidia-smi says has a card."""
    return (
        f"You have an NVIDIA {name} (driver {driver}), but this PyTorch install "
        f"cannot use it -- it looks like the processor-only build. Fix it with:\n"
        f"      python3 setup_training.py\n"
        f"  or by hand:\n"
        f"      python3 -m pip install torch --upgrade --force-reinstall "
        f"--index-url {index_url}")


# ---------------------------------------------------------------------------
# Fetching uv: download (or reuse a local copy), verify, extract.
# ---------------------------------------------------------------------------
def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_file(url: str, dest: Path, *, timeout: int = 120) -> None:
    """GET url to dest. Never sends a body -- this only ever fetches."""
    req = urllib.request.Request(url, headers={"User-Agent": "locallm-setup_training"})
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            with open(tmp, "wb") as f:
                shutil.copyfileobj(resp, f)
    except urllib.error.URLError as e:
        tmp.unlink(missing_ok=True)
        raise SetupError(f"could not download {url}: {e}") from e
    tmp.replace(dest)


def obtain_uv_archive(key: tuple[str, str], *, offline: bool) -> Path:
    """The release archive's bytes on disk, fetching them if not already here.

    Checked BEFORE the offline flag is consulted: a file a user placed by hand
    (per the instructions ensure_uv() prints under --offline) is used with no
    network call at all, whether or not --offline was passed this time.
    """
    asset, digest = UV_RELEASES[key]
    local = DOWNLOADS_DIR / asset
    if local.is_file():
        return local
    if offline:
        raise SetupError(
            f"offline: uv is not set up yet and {asset} is not on disk.\n"
            f"  Download it yourself from:\n    {UV_BASE_URL}/{asset}\n"
            f"  It must match this sha256:\n    {digest}\n"
            f"  Save it as:\n    {local}\n"
            f"  then run this script again -- it will verify and use that file, "
            f"no network needed.")
    download_file(f"{UV_BASE_URL}/{asset}", local)
    return local


def _find_archive_member(names: list[str], binary_name: str) -> str:
    matches = [n for n in names
               if not n.endswith("/") and Path(n).name == binary_name]
    if not matches:
        raise SetupError(
            f"no {binary_name!r} found inside the uv archive "
            f"(it contains: {', '.join(names[:8])}{', ...' if len(names) > 8 else ''})")
    if len(matches) > 1:
        raise SetupError(f"more than one {binary_name!r} inside the uv archive: {matches}")
    return matches[0]


def extract_uv_binary(archive_path: Path, binary_name: str, dest: Path) -> None:
    """Pull just binary_name out of archive_path and place it at dest.

    Only the one named member is ever read out, never the whole archive --
    zipfile/tarfile's own extractall() trusts member paths verbatim, which is
    exactly the traversal risk (docs.python.org/3/library/tarfile.html,
    "extraction filters") a fetched third-party archive should not get.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    if archive_path.name.endswith(".zip"):
        with zipfile.ZipFile(archive_path) as zf:
            member = _find_archive_member(zf.namelist(), binary_name)
            with zf.open(member) as src, open(tmp, "wb") as dst:
                shutil.copyfileobj(src, dst)
    else:
        with tarfile.open(archive_path, "r:gz") as tf:
            member = _find_archive_member(tf.getnames(), binary_name)
            info = tf.getmember(member)
            if not info.isfile():
                raise SetupError(f"{member} inside the uv archive is not a regular file")
            src = tf.extractfile(info)
            if src is None:
                raise SetupError(f"could not read {member} out of the uv archive")
            with open(tmp, "wb") as dst:
                shutil.copyfileobj(src, dst)
    if os.name != "nt":
        tmp.chmod(tmp.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    tmp.replace(dest)


def verify_and_extract_uv(archive_path: Path, key: tuple[str, str]) -> Path:
    """Check archive_path against the pin for key, then extract it. Refuses
    on any mismatch rather than using an unverified binary."""
    asset, digest = UV_RELEASES[key]
    actual = sha256_of(archive_path)
    if actual != digest:
        raise ChecksumMismatch(
            f"{archive_path.name} does not match the pinned checksum for uv "
            f"{UV_VERSION}.\n  expected sha256 {digest}\n  got      sha256 {actual}\n"
            f"Refusing to use it -- delete {archive_path} and run again for a "
            f"fresh download, or replace it with a verified one.")
    dest = uv_install_dir(key) / uv_binary_name(key[0])
    extract_uv_binary(archive_path, uv_binary_name(key[0]), dest)
    return dest


def ensure_uv(*, offline: bool) -> Path | None:
    """A usable, verified uv binary, or None if this platform has no pinned
    build (the caller falls back to the stdlib path in that case)."""
    key = platform_key()
    cached = cached_uv_path(key)
    if cached is not None:
        return cached
    if key not in UV_RELEASES:
        return None
    archive = obtain_uv_archive(key, offline=offline)
    return verify_and_extract_uv(archive, key)


# ---------------------------------------------------------------------------
# Building the environment.
# ---------------------------------------------------------------------------
def _uv_env() -> dict[str, str]:
    env = dict(os.environ)
    env["UV_CACHE_DIR"] = str(UV_CACHE_DIR)
    return env


def create_venv_with_uv(uv_exe: Path, venv_dir: Path) -> None:
    # --python pins the interpreter to the one running this script, so uv
    # wraps it rather than searching for or downloading a managed Python --
    # this script downloads uv and PyTorch and nothing else.
    cmd = [str(uv_exe), "venv", str(venv_dir), "--python", sys.executable]
    p = subprocess.run(cmd, env=_uv_env())
    if p.returncode != 0:
        raise SetupError(f"could not create the virtual environment (uv venv exited {p.returncode})")


def install_torch_with_uv(uv_exe: Path, venv_dir: Path, *, backend: str) -> None:
    py = venv_python(venv_dir)
    cmd = [str(uv_exe), "pip", "install", "--python", str(py),
           "--torch-backend", backend, "torch"]
    p = subprocess.run(cmd, env=_uv_env())
    if p.returncode != 0:
        raise SetupError(f"installing PyTorch with uv failed (exit {p.returncode})")


def create_venv_stdlib(venv_dir: Path) -> None:
    import venv as venv_module
    venv_module.create(venv_dir, with_pip=True)


def install_torch_stdlib(venv_dir: Path, index_url: str) -> None:
    py = venv_python(venv_dir)
    p = subprocess.run([str(py), "-m", "pip", "install", "--upgrade", "pip"])
    if p.returncode != 0:
        raise SetupError(f"could not upgrade pip in the new environment (exit {p.returncode})")
    p = subprocess.run([str(py), "-m", "pip", "install", "torch", "--index-url", index_url])
    if p.returncode != 0:
        raise SetupError(f"installing PyTorch failed (exit {p.returncode})")


# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Set up a training-capable environment for locallm: a "
                    "virtual environment inside this folder with the PyTorch "
                    "build that matches this machine.")
    ap.add_argument("--offline", action="store_true",
                    help="never touch the network; refuse clearly if a download would be needed")
    ap.add_argument("--yes", "-y", action="store_true",
                    help="do not ask for confirmation before downloading anything")
    ap.add_argument("--cpu-only", action="store_true",
                    help="install the processor-only PyTorch build even if an NVIDIA card is present")
    ap.add_argument("--no-uv", action="store_true",
                    help="skip uv and install with pip directly (the stdlib fallback)")
    ap.add_argument("--venv-dir", default=None,
                    help=f"where to create the environment (default: {VENV_DIR})")
    args = ap.parse_args(argv)

    venv_dir = Path(args.venv_dir) if args.venv_dir else VENV_DIR

    say("=" * 68)
    say("  LOCALLM - TRAINING SETUP")
    say("=" * 68)

    v = sys.version_info
    if (v.major, v.minor) < MIN_PYTHON:
        say(f"\n  Python {v.major}.{v.minor} is too old for this; it needs "
            f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer.")
        say("  Get it from https://www.python.org/downloads/ and run this again.")
        return 1

    key = platform_key()
    use_uv = not args.no_uv and key in UV_RELEASES
    backend = "cpu" if args.cpu_only else "auto"
    index_url = reason = ""
    if use_uv:
        cached = cached_uv_path(key)
        plan = []
        if cached is None:
            asset, _digest = UV_RELEASES[key]
            plan.append(f"download uv {UV_VERSION} ({asset}, ~15 MB) from GitHub, "
                        f"verified against a sha256 pinned in this script")
        plan.append(f"create a virtual environment at {venv_dir}")
        plan.append(f"run: uv pip install torch --torch-backend {backend}  "
                    f"(uv picks the PyTorch build for your hardware; the "
                    f"download itself can be anywhere from ~200 MB to a few GB)")
    else:
        if not args.no_uv:
            say(f"\n  (no pinned uv build for {key[0]}/{key[1]}; installing with pip directly)")
        driver_info = None if args.cpu_only else nvidia_driver_info()
        index_url, reason = pick_wheel_index(key[0], driver_info)
        say(f"  chosen PyTorch build: {index_url} ({reason})")
        cached = None
        plan = [f"create a virtual environment at {venv_dir} (Python's own venv module)",
                f"install PyTorch from {index_url}"]

    if args.offline:
        say("\n  OFFLINE MODE: this cannot finish without the network.")
        say("  Installing PyTorch always needs a connection, with or without uv,")
        say("  so this refuses now rather than getting partway through.")
        if use_uv and cached is None:
            asset, digest = UV_RELEASES[key]
            say(f"\n  To fetch just uv by hand: {UV_BASE_URL}/{asset}")
            say(f"  It must match sha256 {digest}")
            say(f"  Save it as {DOWNLOADS_DIR / asset} and run this again -- with or")
            say("  without --offline, that file will be used with no download.")
        return 1

    say("\nThis will:")
    for step in plan:
        say(f"  - {step}")
    if not confirm("\nProceed?", args.yes):
        say("\nStopped. Nothing was installed.")
        return 1

    try:
        if use_uv:
            uv_exe = ensure_uv(offline=False)
            if uv_exe is None:
                raise SetupError("no pinned uv build could be found or fetched for this computer")
            say(f"\nuv: {uv_exe}")
            create_venv_with_uv(uv_exe, venv_dir)
            install_torch_with_uv(uv_exe, venv_dir, backend=backend)
            say(f"\ninstalled PyTorch with uv (--torch-backend {backend})")
        else:
            create_venv_stdlib(venv_dir)
            install_torch_stdlib(venv_dir, index_url)
            say(f"\ninstalled PyTorch from {index_url}")
    except SetupError as e:
        say(f"\nSETUP STOPPED: {e}")
        return 1

    py = venv_python(venv_dir)
    say("\n" + "=" * 68)
    say("  READY")
    say("=" * 68)
    say(f"  Python for training: {py}")
    say(f"  Check it:       {py} check_my_computer.py")
    say(f"  Start training: {py} studio.py")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n  Stopped. Nothing was left half-installed that re-running will not fix.")
        raise SystemExit(1)
