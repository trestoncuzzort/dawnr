#!/usr/bin/env python3
"""Package an explicitly exported TUP root into a direct-UEFI test ISO.

No disk installation, mount, firmware-variable write or download is performed.
External build tools execute trusted code: use a disposable Linux builder.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tup.boot.inputs import (Refusal, canonical, check_kernel, check_offline_root,
                             checked_file, digest, file_hash, inventory, load_json, tree_hash)

HERE = Path(__file__).resolve().parent
TOOLS = {"mksquashfs", "dracut", "lsinitrd", "grub-mkrescue", "grub-script-check", "xorriso"}
GRUB_TEXT_OPTIONS = ("--fonts=", "--themes=", "--locales=")
# Dracut's own init runs the hooks. Dracut 112's systemd-journald module needs
# systemd-sysusers, which the LFS systemd build omits, and a systemd initramfs
# without dracut-systemd would never source a hook.
MODULES = "bash base udev-rules kernel-modules rootfs-block dmsquash-live"
HOOKS = {"verify-live.sh": "usr/lib/dracut/hooks/pre-pivot/01-tup-live-verify.sh",
         "ventoy-live.sh": "usr/lib/dracut/hooks/initqueue/settled/20-tup-ventoy-live.sh"}
# Dracut exits 0 when it cannot install its own scripts; these prove it did.
LIVE_FILES = (r"init", r"(?:usr/)?bin/od", r"(?:usr/)?bin/sha256sum",
              r"var/lib/dracut/hooks/cmdline/30-parse-dmsquash-live\.sh",
              r"var/lib/dracut/hooks/pre-udev/30-dmsquash-live-genrules\.sh",
              r"var/lib/dracut/hooks/pre-mount/01-prepare-overlayfs\.sh",
              r"var/lib/dracut/hooks/mount/01-mount-overlayfs\.sh")
# Ventoy only tests that this file exists in the ISO root. It then adds no hook
# of its own and leaves the ISO's initramfs and kernel parameters alone.
VENTOY_MARKER = b"TUP finds its own ISO through VentoyOsParam. Booting through Ventoy is not yet qualified.\n"
POLICY = {"schema": "tup.live-policy.v1", "architecture": "x86_64", "init": "systemd",
          "firmware": "x86_64-efi", "dracut_version": "112", "grub_version": "2.14",
          "systemd_version": "261", "initramfs_init": "dracut-without-systemd",
          "squashfs_compression": "zstd", "overlay_mib": 512,
          "root_discovery": "unique-content-label",
          "ventoy": "marker-and-efi-handoff-loop-hook-unbooted",
          "grub_assets": "text-console-without-fonts-themes-locales",
          "secure_boot": "unsigned-test-artifact", "installer": False}


def check_tools(path, expected):
    checked_file(path, expected)
    lock = load_json(path)
    if lock.get("schema") != "tup.boot-tools.v1" or set(lock.get("commands", {})) != TOOLS:
        raise Refusal("boot tool lock schema/command set mismatch")
    if lock.get("versions", {}).get("dracut") != "112" or lock.get("versions", {}).get("grub") != "2.14":
        raise Refusal("this boot policy requires reviewed dracut112 and GRUB2.14")
    if not lock.get("provenance") or not lock.get("support_trees"):
        raise Refusal("tool provenance and support-tree identities are required")
    directories = lock.get("path", [])
    if not directories or any(not Path(p).is_absolute() or not Path(p).is_dir() for p in directories):
        raise Refusal("tool PATH must name explicit absolute directories")
    for item in lock["commands"].values():
        command = Path(item["path"])
        if not command.is_absolute() or str(command.parent) not in directories:
            raise Refusal("tool command is outside the declared PATH")
        checked_file(command, item["sha256"])
    for item in lock["support_trees"]:
        if not Path(item["path"]).is_absolute() or tree_hash(item["path"]) != item["sha256"]:
            raise Refusal("boot tool support-tree identity mismatch")
    dracut = Path(lock["dracut_base"])
    if not any(Path(item["path"]) == dracut for item in lock["support_trees"]):
        raise Refusal("explicit hashed host dracut framework is required")
    for name in ("dracut-functions.sh", "dracut-logger.sh", "dracut-install", "skipcpio",
                 "modules.d/70dmsquash-live/module-setup.sh"):
        file_hash(dracut / name)
    modules = Path(lock["grub_modules"])
    if modules.name != "x86_64-efi" or not any(Path(item["path"]) == modules for item in lock["support_trees"]):
        raise Refusal("explicit hashed x86_64-efi GRUB modules are required")
    for name in ("modinfo.sh", "normal.mod", "linux.mod", "iso9660.mod", "search_label.mod"):
        file_hash(modules / name)
    font = lock.get("grub_label_font", {})
    font_path = Path(font.get("path", ""))
    if not font_path.is_absolute():
        raise Refusal("explicit hashed GRUB EFI label font is required")
    checked_file(font_path, font.get("sha256"))
    return lock


def check_core_spec(path):
    spec = load_json(path)
    if spec.get("schema") != "tup.boot-core-validator.v1":
        raise Refusal("missing native core validation command")
    checked_file(spec["script"], spec["script_sha256"])
    args = spec.get("args")
    allowed = {"--workspace", "--source-cache", "--source-lock", "--lock-sha256", "--source", "--book",
               "--build-user", "--jobs", "--memory-mib", "--free-gib", "--through", "--profile"}
    if (not isinstance(args, list) or not args or args[0] != "validate" or len(args) % 2 != 1
            or any(not isinstance(arg, str) or "\0" in arg or "\n" in arg for arg in args)
            or any(flag not in allowed for flag in args[1::2])
            or len(set(args[1::2])) != len(args[1::2])):
        raise Refusal("native validation must explicitly require the complete ch08 core")
    options = dict(zip(args[1::2], args[2::2]))
    if (not {"--workspace", "--source-cache", "--source-lock", "--lock-sha256"} <= options.keys()
            or options.get("--through") != "ch08" or options.get("--profile") != "lfs-13.1-systemd"):
        raise Refusal("native validation is missing complete input arguments")
    inputs = Path(options["--workspace"]).resolve() / "root/tup-build/BUILD-INPUTS.json"
    checked_file(inputs, spec["inputs_sha256"])
    return spec


def completion_path(spec):
    options = dict(zip(spec["args"][1::2], spec["args"][2::2]))
    return Path(options["--workspace"]).resolve() / "state/CORE-COMPLETION.json"


def stamp(path):
    if not path.exists():
        return None
    st = path.lstat()
    return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns


def check_completion(spec, previous):
    path = completion_path(spec)
    file_hash(path)
    if stamp(path) == previous:
        raise Refusal("native validate did not rewrite its completion receipt")
    receipt = load_json(path)
    stages = {"ch05", "ch06", "ownership", "ch07-inner", "ch08"}
    if (receipt.get("schema") != "tup-native-core-completion-v1"
            or receipt.get("scope") != "ch05-ch08-core-only"
            or receipt.get("profile") != "lfs-13.1-systemd"
            or receipt.get("inputs_sha256") != spec["inputs_sha256"]
            or set(receipt.get("stages", {})) != stages):
        raise Refusal("native completion identity/stages mismatch")
    options = dict(zip(spec["args"][1::2], spec["args"][2::2]))
    if (receipt.get("source_lock_sha256") != options["--lock-sha256"]
            or receipt.get("release_eligible") is not False or not isinstance(receipt.get("release_gates"), list)):
        raise Refusal("native completion lacks explicit source/release-gate policy")
    for stage in receipt["stages"].values():
        for field in ("receipt_sha256", "log_sha256"):
            if not re.fullmatch("[0-9a-f]{64}", stage.get(field, "")):
                raise Refusal("native completion lacks stage evidence digests")
    for field in ("driver_receipts_sha256", "driver_state_sha256"):
        if not re.fullmatch("[0-9a-f]{64}", receipt.get(field, "")):
            raise Refusal("native completion lacks driver evidence digests")
    original = path.parent.parent / "root"
    st = original.stat()
    if receipt.get("root_identity") != {"device": st.st_dev, "inode": st.st_ino}:
        raise Refusal("native completion belongs to a different original root")
    return path


def describe(root, release, core_spec, layer_receipt, tools_path, tools_sha256):
    root = check_offline_root(root)
    core = check_core_spec(core_spec)
    tools = check_tools(tools_path, tools_sha256)
    layer = load_json(layer_receipt)
    if (layer.get("schema") != "tup.boot-layer.v1" or layer.get("status") != "complete"
            or layer.get("architecture") != "x86_64" or not layer.get("source_lock_sha256")
            or not layer.get("core_inputs_sha256") or not layer.get("recipe_sha256")):
        raise Refusal("completed, separately receipted boot layer is required")
    for field in ("source_lock_sha256", "core_inputs_sha256", "recipe_sha256", "root_tree_sha256"):
        if not isinstance(layer.get(field), str) or not re.fullmatch("[0-9a-f]{64}", layer[field]):
            raise Refusal("boot layer receipt has an invalid digest: " + field)
    if layer["core_inputs_sha256"] != core["inputs_sha256"]:
        raise Refusal("boot layer was built from a different native core")
    entries = inventory(root)
    identity = digest(canonical(entries))
    if layer.get("root_tree_sha256") != identity:
        raise Refusal("boot layer receipt does not describe the supplied root")
    return {"schema": "tup.boot-inputs.v1", "policy": POLICY,
            "root_tree_sha256": identity, "kernel": check_kernel(root, release),
            "core_validator_sha256": file_hash(core_spec), "layer_receipt_sha256": file_hash(layer_receipt),
            "core_inputs_sha256": layer["core_inputs_sha256"],
            "tools_lock_sha256": tools_sha256,
            "boot_code_sha256": digest(canonical({p.name: file_hash(p) for p in sorted(HERE.iterdir())
                                                    if p.suffix in {".py", ".sh", ".config", ".json"}}))}


def grub_config(label):
    if not re.fullmatch(r"TUP_[A-F0-9]{24}", label):
        raise Refusal("unsafe ISO label")
    return f'''set default=0
set timeout=3
serial --unit=0 --speed=115200 --word=8 --parity=no --stop=1
terminal_input console serial
terminal_output console serial
insmod iso9660
insmod search_label
search --no-floppy --label --set=root {label}
menuentry 'TUP x86_64 UEFI disposable test' {{
    linux /boot/vmlinuz root=live:LABEL={label} ro rd.live.image rd.live.dir=LiveOS rd.live.squashimg=squashfs.img rd.overlay=tmpfs:size={POLICY["overlay_mib"]}M,nr_inodes=100000 rd.live.overlay.nouserconfirmprompt rd.live.ram=0 rd.luks=0 rd.lvm=0 rd.md=0 rd.shell rd.debug rd.retry=90 console=tty0 console=ttyS0,115200n8 systemd.log_target=console
    initrd /boot/initramfs.img
}}
'''


def through(root, path):
    # Dracut 112 looks every source up below --sysroot unless its text starts
    # with the sysroot (dracut-install.c:1398-1405, dracut-functions.sh:1149-1150).
    # Host files therefore need a spelling that passes through the sysroot.
    return os.path.join(root, os.path.relpath(path, root))


def environment(lock, stage, root=None):
    # Do not inherit DRACUT_EXTRA_ARGS, LD_PRELOAD, compiler flags, or the
    # preparation host's root command line. Target files come from --sysroot.
    env = {"PATH": os.pathsep.join(lock["path"]), "LANG": "C", "LC_ALL": "C",
            "HOME": str(stage / "home"), "TMPDIR": str(stage / "tmp"),
            "DRACUT_ARCH": "x86_64", "DRACUT_INSTALL_PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
            "dracutbasedir": lock["dracut_base"], "DRACUT_TESTBIN": "/usr/bin/bash",
            "SYSTEMD_VERSION": POLICY["systemd_version"]}
    if root is not None:
        env.update(dracutbasedir=through(root, lock["dracut_base"]), PKG_CONFIG_SYSROOT_DIR=str(root),
                   PKG_CONFIG_LIBDIR=f"{root}/usr/lib/pkgconfig:{root}/usr/share/pkgconfig")
    return env


def execute(command, *, cwd, env, log):
    with open(log, "ab") as stream:
        stream.write(canonical({"argv": [str(x) for x in command]}))
        stream.flush()
        start = stream.tell()
        result = subprocess.run([str(x) for x in command], cwd=cwd, env=env,
                                stdin=subprocess.DEVNULL, stdout=stream,
                                stderr=subprocess.STDOUT, check=False)
        stream.flush()
        end = stream.tell()
        os.fsync(stream.fileno())
    if result.returncode:
        raise Refusal(f"build command failed ({result.returncode}); see {log.name}")
    # Preserve complete logs as they arrive; only inspection output is read
    # back into memory. An unexpectedly verbose tool cannot consume host RAM.
    if end - start > 8 * 1024 * 1024:
        raise Refusal(f"tool output exceeded inspection limit; full output retained in {log.name}")
    with open(log, "rb") as stream:
        stream.seek(start)
        return stream.read(end - start).decode("utf-8", errors="replace")


def check_unmounted(root):
    # st_dev alone cannot detect same-filesystem bind mounts.
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        name = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), line.split()[4])
        mountpoint = Path(name)
        if mountpoint == root or root in mountpoint.parents:
            raise Refusal("source root must be an unmounted offline export")
    runtime = Path("/run/initramfs/dracut.conf.d")
    if runtime.exists() and (not runtime.is_dir() or any(runtime.iterdir())):
        raise Refusal("ambient runtime dracut configuration is not permitted")


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def sync_tree(root):
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
    for path in sorted((p for p in root.rglob("*") if p.is_dir() and not p.is_symlink()),
                       key=lambda p: len(p.parts), reverse=True):
        sync_directory(path)
    sync_directory(root)


def assemble(root, expected_path, core_spec, layer_receipt, tools_path, tools_sha256,
             output, *, jobs=4, memory_mib=1024, runner=execute):
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "AMD64"}:
        raise Refusal("artifact tools require a disposable Linux x86_64 builder")
    if not 1 <= jobs <= 24 or not 256 <= memory_mib <= 4096:
        raise Refusal("explicit build budget outside supported bounds")
    if Path(root).is_symlink():
        raise Refusal("source root must not be a symbolic link")
    root, output = Path(root).resolve(), Path(output).absolute()
    if (output.exists() or output.is_symlink() or root == output
            or root in output.resolve().parents or output.resolve() in root.parents):
        raise Refusal("output must be a new directory disjoint from the root")
    output.parent.mkdir(parents=True, exist_ok=True)
    check_unmounted(root)
    expected = load_json(expected_path)
    release = expected.get("kernel", {}).get("release", "")
    current = describe(root, release, core_spec, layer_receipt, tools_path, tools_sha256)
    if expected != current:
        raise Refusal("boot inputs changed; review and seal a new input specification")
    lock = check_tools(tools_path, tools_sha256)
    native = check_core_spec(core_spec)
    stage = Path(tempfile.mkdtemp(prefix=".tup-boot-", dir=output.parent))
    try:
        for name in ("iso/boot/grub", "iso/LiveOS", "tmp", "home", "empty-conf.d",
                     "overlay/etc/tup-live", *("overlay/" + target.rsplit("/", 1)[0] for target in HOOKS.values())):
            (stage / name).mkdir(parents=True, exist_ok=True)
        env = environment(lock, stage, root)
        log = stage / "build.log"
        # This command can only validate, never resume an unfinished core.
        previous = stamp(completion_path(native))
        runner([sys.executable, native["script"], *native["args"]], cwd=stage,
               env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C"}, log=log)
        completion = check_completion(native, previous)
        core_receipt = load_json(completion)
        shutil.copyfile(completion, stage / "CORE-COMPLETION.json")
        if describe(root, release, core_spec, layer_receipt, tools_path, tools_sha256) != expected:
            raise Refusal("inputs changed during native validation")
        (stage / "ROOT-INVENTORY.json").write_bytes(canonical(inventory(root)))
        checked_file(stage / "ROOT-INVENTORY.json", expected["root_tree_sha256"])
        (stage / "MODULES-INVENTORY.json").write_bytes(canonical(inventory(root / "usr/lib/modules" / release)))
        checked_file(stage / "MODULES-INVENTORY.json", expected["kernel"]["modules_sha256"])
        command = lambda name: lock["commands"][name]["path"]
        label = "TUP_" + digest(canonical(expected))[:24].upper()
        (stage / "iso/boot/grub/grub.cfg").write_text(grub_config(label), encoding="utf-8", newline="\n")
        (stage / "iso/ventoy.dat").write_bytes(VENTOY_MARKER)
        shutil.copyfile(root / "boot" / ("vmlinuz-" + release), stage / "iso/boot/vmlinuz")
        runner([command("grub-script-check"), stage / "iso/boot/grub/grub.cfg"], cwd=stage, env=env, log=log)
        squash = stage / "iso/LiveOS/squashfs.img"
        runner([command("mksquashfs"), root, squash, "-noappend", "-comp", "zstd", "-processors", str(jobs),
                "-mem", f"{memory_mib}M", "-no-progress", "-one-file-system"], cwd=stage, env=env, log=log)
        with squash.open("rb") as stream:
            magic = stream.read(4)
        if magic != b"hsqs":
            raise Refusal("mksquashfs did not produce a SquashFS image")
        squash_hash = file_hash(squash)
        (stage / "overlay/etc/tup-live/root.sha256").write_text(
            squash_hash + "  /run/initramfs/live/LiveOS/squashfs.img\n", encoding="ascii", newline="\n")
        for name, target in HOOKS.items():
            shutil.copyfile(HERE / name, stage / "overlay" / target)
            (stage / "overlay" / target).chmod(0o755)
        # A directory given to --include is copied from below the sysroot
        # (dracut.sh:2915-2917); a file goes through dracut-install like the rest.
        overlay = sorted(path for path in (stage / "overlay").rglob("*") if path.is_file())
        includes = [arg for path in overlay for arg in (
            "--include", through(root, path), "/" + path.relative_to(stage / "overlay").as_posix())]
        conf = stage / "dracut.conf"
        conf.write_text('hostonly="no"\nhostonly_cmdline="no"\n', encoding="ascii", newline="\n")
        initrd = stage / "iso/boot/initramfs.img"
        runner([command("dracut"), "--sysroot", root, "--kver", release, "--conf", conf,
                "--confdir", stage / "empty-conf.d", "--tmpdir", stage / "tmp", "--logfile", stage / "dracut.log",
                "--no-hostonly", "--no-hostonly-cmdline", "--no-hostonly-default-device", "--no-early-microcode",
                "--nohardlink", "--nostrip", "--gzip", "--no-uefi", "--no-ukify",
                "--modules", MODULES, "--install", "/usr/bin/sha256sum /usr/bin/od", *includes, initrd],
               cwd=stage, env=env, log=log)
        file_hash(initrd)
        modules = runner([command("lsinitrd"), "-m", initrd], cwd=stage, env=env, log=log)
        listed = lambda name: re.search(r"(?m)^\s*" + re.escape(name) + r"\s*$", modules)
        if (not all(listed(name) for name in ("base", "dmsquash-live", "initqueue", "overlayfs"))
                or listed("systemd") and not listed("dracut-systemd")):
            raise Refusal("initramfs is missing required live modules")
        embedded = runner([command("lsinitrd"), "-f", "etc/tup-live/root.sha256", initrd], cwd=stage, env=env, log=log)
        if embedded.strip() != (stage / "overlay/etc/tup-live/root.sha256").read_text().strip():
            raise Refusal("initramfs payload identity was not embedded")
        for name, target in HOOKS.items():
            embedded_hook = runner([command("lsinitrd"), "-f", target, initrd], cwd=stage, env=env, log=log)
            if embedded_hook.strip() != (HERE / name).read_text().strip():
                raise Refusal("initramfs hook was not embedded: " + name)
        listing = runner([command("lsinitrd"), initrd], cwd=stage, env=env, log=log)
        if not all(re.search(r"(?m)\s" + name + "$", listing) for name in LIVE_FILES):
            raise Refusal("initramfs lacks dracut's live scripts or the hook tools; see " + log.name)
        iso = stage / "tup-x86_64-uefi-test.iso"
        runner([command("grub-mkrescue"), *GRUB_TEXT_OPTIONS,
                "--directory=" + lock["grub_modules"], "--output=" + str(iso),
                "--label-font=" + lock["grub_label_font"]["path"],
                "--xorriso=" + command("xorriso"), stage / "iso", "-volid", label], cwd=stage, env=env, log=log)
        report = runner([command("xorriso"), "-indev", iso, "-report_el_torito", "plain"], cwd=stage, env=env, log=log)
        if not re.search(r"El Torito boot img\s*:\s*\d+\s+UEFI\b", report):
            raise Refusal("ISO has no inspected UEFI El Torito boot entry")
        if describe(root, release, core_spec, layer_receipt, tools_path, tools_sha256) != expected:
            raise Refusal("input tree/tool identities changed during packaging")
        receipt = {"schema": "tup.boot-artifact.v1", "status": "packaged-unbooted",
                   "scope": "direct-uefi-disposable-test-only", "release_eligible": False,
                   "release_gates": [*core_receipt["release_gates"], "native-boot-unqualified", "ventoy-unqualified"],
                   "core_source_policy": {field: core_receipt.get(field) for field in (
                       "source_lock_sha256", "source_lock_purpose", "source_release_eligible", "advisory_review_sha256")},
                   "inputs": expected, "label": label, "boot_tested": False, "ventoy_tested": False,
                   "artifacts": {str(p.relative_to(stage)): file_hash(p)
                                 for p in (iso, squash, initrd, stage / "iso/boot/vmlinuz", stage / "iso/boot/grub/grub.cfg",
                                           stage / "iso/ventoy.dat")},
                   "build_log_sha256": file_hash(log),
                   "core_completion_sha256": file_hash(stage / "CORE-COMPLETION.json")}
        (stage / "ARTIFACT.json").write_bytes(canonical(receipt))
        # A fresh-directory rename is the publish point. No overwrite/resume.
        sync_tree(stage)
        os.rename(stage, output)
        sync_directory(output.parent)
        return receipt
    except BaseException as error:
        failed = stage if stage.exists() else output
        if (failed / "ARTIFACT.json").exists():
            (failed / "ARTIFACT.json").rename(failed / "ARTIFACT.uncertain.json")
        (failed / "FAILED.txt").write_text(type(error).__name__ + ": " + str(error) + "\n", encoding="utf-8")
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("inspect", "build"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--kernel-release", required=True)
    parser.add_argument("--core-validator", type=Path, required=True)
    parser.add_argument("--layer-receipt", type=Path, required=True)
    parser.add_argument("--tools-lock", type=Path, required=True)
    parser.add_argument("--tools-lock-sha256", required=True)
    parser.add_argument("--expected-inputs", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--memory-mib", type=int, default=1024)
    args = parser.parse_args(argv)
    try:
        if args.action == "inspect":
            print(canonical(describe(args.root, args.kernel_release, args.core_validator, args.layer_receipt,
                                     args.tools_lock, args.tools_lock_sha256)).decode(), end="")
        else:
            if args.expected_inputs is None or args.output is None:
                raise Refusal("build requires separately reviewed --expected-inputs and a fresh --output")
            if load_json(args.expected_inputs).get("kernel", {}).get("release") != args.kernel_release:
                raise Refusal("requested kernel differs from sealed inputs")
            receipt = assemble(args.root, args.expected_inputs, args.core_validator, args.layer_receipt,
                               args.tools_lock, args.tools_lock_sha256, args.output,
                               jobs=args.jobs, memory_mib=args.memory_mib)
            print("packaged-unbooted: " + receipt["artifacts"]["tup-x86_64-uefi-test.iso"])
    except (OSError, ValueError, KeyError, IndexError) as error:
        print("boot packaging refused: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
