#!/usr/bin/env python3
"""Emit/check the native live-boot kernel fragment; never build or install itself."""
import argparse
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tup.boot.inputs import AVAILABLE, BUILTIN, SYSTEMD, Refusal, check_config

# This extends x86_64_defconfig. It is a boot floor, not final GPU/Wi-Fi or
# production hardening qualification. Core systemd and diagnostics need these.
LFS = "PSI CGROUP_SCHED RELOCATABLE RANDOMIZE_BASE STACKPROTECTOR STACKPROTECTOR_STRONG SYSFB_SIMPLEFB DRM DRM_PANIC DRM_FBDEV_EMULATION DRM_SIMPLEDRM FRAMEBUFFER_CONSOLE".split()
DISABLED = "WERROR PSI_DEFAULT_DISABLED IKHEADERS EXPERT RT_GROUP_SCHED UEVENT_HELPER FW_LOADER_USER_HELPER LEGACY_TIOCSTI".split()


def fragment():
    lines = ["# Native x86_64 direct-UEFI live-boot floor; merge into x86_64_defconfig.",
             'CONFIG_LOCALVERSION="-tup"', "# CONFIG_LOCALVERSION_AUTO is not set"]
    lines += ["CONFIG_" + key + "=y" for key in sorted(set(BUILTIN + AVAILABLE + SYSTEMD + LFS))]
    lines += ["# CONFIG_" + key + " is not set" for key in DISABLED]
    lines += ['CONFIG_DRM_PANIC_SCREEN="kmsg"', 'CONFIG_UEVENT_HELPER_PATH=""']
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("fragment", "check"))
    parser.add_argument("--config", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.action == "fragment":
            print(fragment(), end="")
        else:
            if args.config is None:
                raise Refusal("check requires --config after olddefconfig")
            values = check_config(args.config)
            missing = [key for key in SYSTEMD + LFS if values.get("CONFIG_" + key) != "y"]
            missing += [key for key in DISABLED if values.get("CONFIG_" + key) not in {None, "n"}]
            if missing:
                raise Refusal("systemd configuration requirements lost: " + ", ".join(missing))
            print("kernel boot-floor configuration accepted; build and boot still untested")
    except (OSError, ValueError) as error:
        print("kernel configuration refused: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
