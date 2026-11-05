"""Static checks of the system chapter: pages, units and the files they install.

The pages run only inside the layer chroot; nothing here executes one.
"""
import base64
import importlib.util
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import unittest

TUP = Path(__file__).resolve().parents[1]
SYSTEM, PAGES, UNITS = TUP / "system", TUP / "system/pages", TUP / "system/units"
BOOK = TUP / "book-x86_64-13.1-systemd"
SPEC = importlib.util.spec_from_file_location("remote_enroll", TUP / "remote/enroll.py")
enroll = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(enroll)
policy, firewall = enroll.policy, enroll.firewall
BLOB = struct.pack(">I", 11) + b"ssh-ed25519" + struct.pack(">I", 32) + bytes(range(1, 33))
KEY = b"ssh-ed25519 " + base64.b64encode(BLOB) + b"\n"
BASH = os.environ.get("TUP_TEST_BASH") or shutil.which("bash")
ANALYZE = shutil.which("systemd-analyze")
UNIT_NAMES = ["tup-console-status.service", "tup-enroll.service", "tup-firewall.service", "tup-sshd.service"]
# Every program a unit starts, as the target installs it.
EXECUTABLES = ("usr/bin/python3", "usr/bin/udevadm", "usr/bin/mount", "usr/bin/umount", "usr/bin/kill",
               "usr/bin/ssh-keygen", "usr/sbin/sshd", "usr/sbin/nft", "usr/lib/tup/remote/enroll.py")


def unit(name: str) -> str:
    return (UNITS / name).read_text(encoding="ascii")


def setting(text: str, key: str) -> list[str]:
    return [line.split("=", 1)[1] for line in text.splitlines() if line.startswith(key + "=")]


def book_block(page: str, number: str) -> str:
    text = (BOOK / page).read_text(encoding="utf-8")
    return text.split(f"# TUP_BLOCK_BEGIN={number}\n", 1)[1].split(f"# TUP_BLOCK_END={number}\n", 1)[0]


class SystemPagesTests(unittest.TestCase):
    def pages(self):
        return sorted(path.name for path in PAGES.glob("*.sh"))

    def test_order_lists_every_page_once_in_numeric_order(self):
        raw = (PAGES / "ORDER").read_bytes()
        self.assertTrue(raw.endswith(b"\n") and b"\r" not in raw)
        order = raw.decode("ascii").splitlines()
        self.assertEqual(order, self.pages())
        self.assertEqual(order, ["01-identity.sh", "02-network.sh", "03-access.sh"])
        for name in order:  # The driver's own ORDER pattern, plus the NN-name convention.
            self.assertRegex(name, r"^[a-zA-Z0-9][a-zA-Z0-9_.+-]*\.sh$")
            self.assertRegex(name, r"^[0-9]{2}-[a-z0-9-]+\.sh$")
        self.assertEqual(sorted(path.name for path in PAGES.iterdir()), [*order, "ORDER"])

    def test_pages_follow_the_layer_contract_and_carry_no_machine_data(self):
        for path in [*PAGES.glob("*.sh"), *UNITS.iterdir(), SYSTEM / "issue", SYSTEM / "firewall.nft"]:
            raw = path.read_bytes()
            with self.subTest(path=path.name):
                self.assertNotIn(b"\r", raw)
                self.assertTrue(raw.endswith(b"\n"))
                text = raw.decode("ascii")
                for forbidden in ("/srv/", "C:\\", "/mnt/c", "/home/lfs"):
                    self.assertNotIn(forbidden, text)
                # The only addresses anywhere are the private source prefixes of the firewall.
                for address in re.findall(r"\b\d+\.\d+\.\d+\.\d+(?:/\d+)?", text):
                    self.assertIn(address, [str(network) for network in policy.PRIVATE_SOURCES])
        for name in self.pages():
            lines = (PAGES / name).read_text(encoding="ascii").splitlines()
            with self.subTest(name=name):
                self.assertEqual(lines[:2], ["#!/bin/bash", "source /tup-layer/common.sh"])
                self.assertFalse([line for line in lines if line.startswith("# TUP_TARBALL")])
                # Offline only: units are enabled as files and never started or reloaded.
                for line in lines:
                    for call in re.findall(r"systemctl[^)|;]*", "" if line.lstrip().startswith("#") else line):
                        self.assertRegex(call, r"^systemctl --root=/ (enable|is-enabled) ")
                self.assertNotRegex("\n".join(lines), r"/dev/(stdin|fd)|<\(")  # Not in the chroot's minimal /dev.

    @unittest.skipUnless(BASH, "requires bash (set TUP_TEST_BASH)")
    def test_every_page_parses(self):
        for name in self.pages():
            with self.subTest(name=name):
                done = subprocess.run([BASH, "-n", str(PAGES / name)], capture_output=True, check=False)
                self.assertEqual((done.returncode, done.stderr), (0, b""))

    def test_identity_page_reuses_the_book_and_satisfies_the_offline_root_check(self):
        page = (PAGES / "01-identity.sh").read_text(encoding="ascii")
        for source, number in (("ch09/08-inputrc.sh", "001"), ("ch09/09-etcshells.sh", "001"), ("ch09/10-systemd-custom.sh", "001")):
            self.assertIn(book_block(source, number), page, source)
        profile = book_block("ch09/07-locale.sh", "005")
        self.assertIn(profile, page)
        self.assertIn('cat > /etc/locale.conf << "EOF"\nLANG=C.UTF-8\nEOF\n', page)
        self.assertIn('echo "tup" > /etc/hostname\n', page)
        release = page.split('cat > /etc/os-release << "EOF"\n', 1)[1].split("EOF\n", 1)[0]
        # The two expressions boot/inputs.py check_offline_root() applies.
        self.assertEqual(len(re.findall(r'^ID=(?:tup|"tup")$', release, re.M)), 1)
        self.assertEqual(len(re.findall(r'^VERSION_ID="?[A-Za-z0-9._+-]+"?$', release, re.M)), 1)
        self.assertEqual(sorted(line.split("=")[0] for line in release.splitlines()),
                         ["ID", "NAME", "PRETTY_NAME", "VERSION", "VERSION_ID"])
        for source in ("chapter11/theend.html", "chapter09/network.html", "chapter09/locale.html", "chapter09/inputrc.html",
                       "chapter09/etcshells.html", "chapter09/systemd-custom.html"):
            self.assertIn("https://www.linuxfromscratch.org/lfs/view/13.1-systemd/" + source, page)

    def test_network_page_configures_wired_dhcp_mdns_and_bounded_waits(self):
        page = (PAGES / "02-network.sh").read_text(encoding="ascii")
        network = page.split('cat > /etc/systemd/network/20-wired.network << "EOF"\n', 1)[1].split("EOF\n", 1)[0]
        self.assertEqual(network, "[Match]\nKind=!*\nType=ether\n\n[Network]\nDHCP=yes\nMulticastDNS=yes\nLLMNR=no\n\n"
                                  "[DHCPv4]\nClientIdentifier=mac\n")
        self.assertIn('resolved.conf.d/10-tup.conf << "EOF"\n[Resolve]\nMulticastDNS=yes\nLLMNR=no\nEOF\n', page)
        self.assertIn("ln -sfnv ../run/systemd/resolve/stub-resolv.conf /etc/resolv.conf\n", page)
        self.assertIn('journald.conf.d/10-tup-size.conf << "EOF"\n[Journal]\nSystemMaxUse=256M\nRuntimeMaxUse=64M\nEOF\n', page)
        self.assertIn("[Service]\nExecStart=\nExecStart=/usr/lib/systemd/systemd-networkd-wait-online --any --timeout=30\nEOF\n", page)
        self.assertNotRegex(page, r"(?m)^\s*(Name|MACAddress|Address|Gateway|DNS)=")  # Nothing machine-specific.
        self.assertIn("https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/network.html", page)

    def test_access_page_installs_and_enables_exactly_what_the_units_need(self):
        page = (PAGES / "03-access.sh").read_text(encoding="ascii")
        self.assertEqual(sorted(path.name for path in UNITS.iterdir()), UNIT_NAMES)
        declared = re.search(r'^units="([^"]*)"$', page, re.M).group(1).split()
        self.assertEqual(sorted(declared), UNIT_NAMES)
        self.assertIn("systemctl --root=/ enable systemd-networkd.service systemd-resolved.service "
                      "systemd-timesyncd.service $units\n", page)
        for name in ("policy.py", "firewall.py", "enroll.py"):
            self.assertRegex(page, rf'install -v -m 0[67][45][45] [^\n]*"\$src/remote/{name}"[^\n]* /usr/lib/tup/remote/\n')
        self.assertIn('install -v -m 0600 "$src/system/firewall.nft" /etc/tup/firewall.nft\n', page)
        self.assertIn('install -v -m 0644 "$src/system/issue" /etc/issue\n', page)
        # Each executable a unit names is checked by the page before anything is installed.
        for name in UNIT_NAMES:
            for line in unit(name).splitlines():
                if line.startswith("Exec"):
                    program = line.split("=", 1)[1].lstrip("-").split()[0]
                    self.assertIn("/" + program.lstrip("/"), ["/" + relative for relative in EXECUTABLES], line)
                    if not program.startswith("/usr/lib/tup/"):
                        self.assertIn(program, page, line)
        self.assertIn("/usr/sbin/useradd", page)
        # The table names a protocol nft looks up, and enrollment's sudo rule lives in sudoers.d.
        self.assertIn(b"meta l4proto ipv6-icmp", (SYSTEM / "firewall.nft").read_bytes())
        self.assertIn('[ -s /etc/protocols ] || fail', page)
        self.assertIn("includedir[[:space:]]+/etc/sudoers\\.d", page)
        self.assertEqual(Path("/" + enroll.SUDOERS).parent.as_posix(), "/etc/sudoers.d")
        for check in ("/etc/machine-id", "/etc/ssh/ssh_host_*", "/etc/shadow", "/etc/os-release", "/etc/fstab",
                      "/etc/tup/owner-enrolled.json", "/etc/tup/authorized_keys", "/etc/sudoers.d/10-tup-owner"):
            self.assertIn(check, page.split("# Final state of a generic image", 1)[1], check)

    def test_shipped_units_and_default_firewall_are_what_the_renderers_emit(self):
        access = policy.render("owner", None, KEY, scope=policy.PRIVATE)
        wall = firewall.render(None, None, scope=policy.PRIVATE)
        self.assertEqual((UNITS / "tup-sshd.service").read_bytes(), access["tup-sshd.service"])
        self.assertEqual((UNITS / "tup-firewall.service").read_bytes(), wall["tup-firewall.service"])
        default = (SYSTEM / "firewall.nft").read_bytes()
        self.assertEqual(default, firewall.render(None, None, scope=firewall.UNENROLLED)["firewall.nft"])
        self.assertNotIn(b"ct state { new, established } counter accept", default)
        self.assertIn(b"policy drop;", default)
        self.assertNotEqual(default, wall["firewall.nft"])
        # The same bytes enrollment and the access page compare against.
        page = (PAGES / "03-access.sh").read_text(encoding="ascii")
        for expression in ('policy.render("owner", None,', "scope=policy.PRIVATE)", "scope=firewall.UNENROLLED)"):
            self.assertIn(expression, page)

    def test_enrollment_unit_runs_early_once_and_never_fails_a_boot_without_input(self):
        text = unit("tup-enroll.service")
        self.assertEqual(setting(text, "DefaultDependencies"), ["no"])
        self.assertIn("local-fs.target", setting(text, "After")[0].split())
        before = setting(text, "Before")[0].split()
        for later in ("tup-firewall.service", "tup-sshd.service", "tup-console-status.service"):
            self.assertIn(later, before)
        self.assertEqual(setting(text, "ConditionPathExists"), ["!/" + enroll.MARKER])
        self.assertEqual(setting(text, "Type"), ["oneshot"])
        label, mount = setting(text, "ExecStartPre")
        self.assertEqual(label, "-/usr/bin/udevadm wait --timeout=5 /dev/disk/by-label/TUP-ENROLL")
        self.assertEqual(mount, "-/usr/bin/mount --mkdir -o ro,nosuid,nodev,noexec /dev/disk/by-label/TUP-ENROLL /run/tup-enroll")
        self.assertEqual("/" + enroll.INPUT_DIRECTORIES[0], "/run/tup-enroll/tup-enroll")
        self.assertEqual(setting(text, "ExecStart"), ["/usr/bin/python3 -I -B /usr/lib/tup/remote/enroll.py"])
        self.assertEqual(setting(text, "ExecStopPost"), ["-/usr/bin/umount /run/tup-enroll"])
        self.assertEqual(setting(text, "StandardOutput"), ["journal+console"])
        self.assertTrue(0 < int(setting(text, "TimeoutStartSec")[0]) <= 300)
        self.assertNotIn("Requires", text)
        for other in ("tup-firewall.service", "tup-sshd.service", "tup-console-status.service"):
            self.assertNotRegex(unit(other), r"(?m)^(Requires|BindsTo|Requisite)=.*tup-enroll")  # Its failure blocks nothing.

    def test_console_unit_and_issue_show_state_addresses_and_fingerprint_before_login(self):
        text = unit("tup-console-status.service")
        self.assertEqual(setting(text, "After"), ["tup-enroll.service"])
        self.assertEqual((setting(text, "Wants"), setting(text, "Before")), (["getty-pre.target"], ["getty-pre.target"]))
        self.assertEqual(setting(text, "ExecStart"), ["/usr/bin/python3 -I -B /usr/lib/tup/remote/enroll.py --console-status"])
        self.assertRegex(enroll.ISSUE, r"^run/issue\.d/[0-9a-z-]+\.issue$")
        issue = (SYSTEM / "issue").read_text(encoding="ascii")
        self.assertIn("\\4", issue)
        self.assertIn("\\6", issue)
        self.assertIn("\\S{PRETTY_NAME}", issue)

    def test_ssh_unit_starts_only_after_enrollment_and_behind_the_firewall(self):
        text = unit("tup-sshd.service")
        self.assertEqual(setting(text, "ConditionPathExists"), ["/" + enroll.MARKER])
        self.assertEqual(setting(text, "Requires"), ["tup-firewall.service"])
        self.assertNotIn("network-online.target", text)
        self.assertIn("-f /" + enroll.SSHD_CONFIG, setting(text, "ExecStart")[0])
        wall = unit("tup-firewall.service")
        self.assertEqual(setting(wall, "ExecStart"), ["/usr/sbin/nft -f /" + enroll.FIREWALL])
        self.assertIn("network-pre.target", setting(wall, "Before")[0].split())
        self.assertFalse(setting(wall, "ConditionPathExists"))  # Always loaded, enrolled or not.

    @unittest.skipUnless(ANALYZE, "requires systemd-analyze (Linux hosts with systemd)")
    def test_units_verify_with_systemd_analyze(self):
        version = int(re.search(r"systemd (\d+)", subprocess.run([ANALYZE, "--version"], capture_output=True, text=True,
                                                                check=True).stdout).group(1))
        if version < 250:
            self.skipTest("systemd-analyze verify --recursive-errors needs systemd 250 or later")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in EXECUTABLES:  # Stubs: verification checks that each program exists.
                (root / relative).parent.mkdir(parents=True, exist_ok=True)
                (root / relative).write_text("#!/bin/sh\n")
                (root / relative).chmod(0o755)
            units = root / "usr/lib/systemd/system"
            units.mkdir(parents=True)
            (root / "etc/systemd/system").mkdir(parents=True)

            def verify():
                # Targets of the real system are absent from this root; only the named units are judged.
                return subprocess.run([ANALYZE, "verify", "--man=no", "--recursive-errors=no", "--root=" + str(root), *UNIT_NAMES],
                                      capture_output=True, text=True, check=False)
            for name in UNIT_NAMES:
                shutil.copyfile(UNITS / name, units / name)
            done = verify()
            self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))
            # Negative controls: the same invocation must notice a damaged unit.
            for name, old, new in (("tup-enroll.service", "Type=oneshot", "Type=oneshot\nNoSuchSetting=1"),
                                   ("tup-console-status.service", "/usr/bin/python3", "/usr/bin/python-absent"),
                                   ("tup-enroll.service", "[Service]", "[Servce]")):
                original = (units / name).read_text()
                self.assertIn(old, original)
                (units / name).write_text(original.replace(old, new))
                with self.subTest(name=name, new=new):
                    self.assertNotEqual(verify().returncode, 0)
                (units / name).write_text(original)


if __name__ == "__main__":
    unittest.main()
