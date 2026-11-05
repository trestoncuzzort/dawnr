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
import sys
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
        self.assertEqual(order, ["01-identity.sh", "02-network.sh", "03-access.sh", "04-installer.sh"])
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

    def test_graphics_module_without_staged_firmware_is_not_loaded_automatically(self):
        page = (PAGES / "01-identity.sh").read_text(encoding="ascii")
        self.assertIn('cat > /etc/modprobe.d/tup-graphics.conf << "EOF"\nblacklist amdgpu\nEOF\n', page)
        # The boot chapter stages network firmware and microcode only. When amdgpu
        # firmware is added there, this entry has to be reconsidered with it.
        self.assertNotIn("amdgpu", (TUP / "hardware/firmware-files.sha256").read_text(encoding="ascii"))

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

    def test_time_synchronization_waits_for_the_owners_word_about_the_hardware_clock(self):
        # A synchronized clock is copied to the hardware clock as UTC; a Windows
        # installation on the same machine keeps local time there.
        page = (PAGES / "02-network.sh").read_text(encoding="ascii")
        self.assertIn('systemd-timesyncd.service.d/10-tup-hardware-clock.conf << "EOF"\n[Unit]\n'
                      "ConditionPathExists=/" + enroll.CLOCK + "\nEOF\n", page)
        access = (PAGES / "03-access.sh").read_text(encoding="ascii")
        final = access.split("# Final state of a generic image", 1)[1]
        self.assertIn("[ ! -e /" + enroll.CLOCK + " ] || fail", final)
        self.assertIn("grep -qx 'ConditionPathExists=/" + enroll.CLOCK + "'", final)
        # Enrollment decides before the service's condition is evaluated in the same boot.
        self.assertIn("systemd-timesyncd.service", setting(unit("tup-enroll.service"), "Before")[0].split())

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


class InstallerPageTests(unittest.TestCase):
    """04-installer.sh ships tup/install/disk.py and the two boot modules it imports, and /usr/sbin/tup-install."""

    PAGE = PAGES / "04-installer.sh"

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("installer_disk", TUP / "install/disk.py")
        cls.disk = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.disk)
        cls.text = cls.PAGE.read_text(encoding="ascii")

    def test_it_runs_after_the_access_page_and_the_runner_stages_what_it_installs(self):
        spec = importlib.util.spec_from_file_location("target_build", TUP / "target/build.py")
        target = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(target)
        self.assertIn("install", target.HELPERS)
        self.assertEqual(target.chapter_pages(TUP, "system")[-2:], ["03-access.sh", "04-installer.sh"])
        for staged in ("install/disk.py", "boot/__init__.py", "boot/inputs.py"):
            self.assertTrue((TUP / staged).is_file(), staged)
            self.assertIn(f'"$src/{staged}"', self.text)
        self.assertIn('install -v -m 0755 "$src/install/disk.py" "$dest/tup/install/disk.py"\n', self.text)
        self.assertIn('install -v -m 0644 "$src/boot/__init__.py" "$src/boot/inputs.py" "$dest/tup/boot/"\n', self.text)
        self.assertIn("dest=/usr/lib/tup-installer\n", self.text)

    def test_what_disk_py_imports_is_what_the_page_installs(self):
        source = (TUP / "install/disk.py").read_text(encoding="utf-8")
        self.assertEqual(set(re.findall(r"^from (tup\.[a-z.]+) import", source, re.M)), {"tup.boot", "tup.boot.inputs"})
        inputs_source = (TUP / "boot/inputs.py").read_text(encoding="utf-8")
        self.assertEqual(set(re.findall(r"^(?:from|import) (\w+)", inputs_source, re.M)),
                         {"__future__", "hashlib", "json", "os", "pathlib", "re", "stat", "struct"})  # nothing else to ship

    def test_the_wrapper_runs_the_explicit_script_isolated_without_bytecode(self):
        wrapper = self.text.split('cat > /usr/sbin/tup-install << "EOF"\n', 1)[1].split("EOF\n", 1)[0]
        self.assertEqual(wrapper.splitlines()[0], "#!/bin/sh")
        self.assertEqual(wrapper.splitlines()[-1],
                         'exec /usr/bin/python3 -I -B /usr/lib/tup-installer/tup/install/disk.py "$@"')
        self.assertIn("chmod 0755 /usr/sbin/tup-install\n", self.text)
        self.assertIn("rm -f /usr/sbin/tup-install\n", self.text)  # never written through an existing link

    def test_it_refuses_a_root_without_any_program_the_installer_runs(self):
        loop = self.text.split("for tool in ", 1)[1].split("; do", 1)[0].replace("\\\n", " ").split()
        self.assertEqual(set(loop), set(self.disk.TOOLS) | {"blockdev", "findmnt", "python3"})
        self.assertEqual(len(loop), len(set(loop)))
        self.assertIn('[ -x "$path" ] || fail "$tool is missing"', self.text)
        self.assertIn("[ -d /usr/lib/grub/x86_64-efi ] || fail", self.text)
        # Every module the generated menu loads, and the serial command, must exist for the platform.
        layout = self.disk.make_layout({"log_sec": 512, "size_bytes": 64 << 30}, 512, lambda n: b"\x05" * n)
        menu = self.disk.grub_cfg_text(layout, {"name": "vmlinuz-x"}, {"loaded": True}, "0" * 64)
        modules = set(re.findall(r"^insmod (\w+)$", menu, re.M)) | {"serial"}
        self.assertEqual(set(self.text.split("for module in ", 1)[1].split(";", 1)[0].split()), modules)

    def test_it_changes_nothing_the_access_page_asserts_and_leaves_no_bytecode(self):
        body, final = self.text.split("# Final state of a generic image", 1)
        code = "\n".join(line for line in body.splitlines() if not line.lstrip().startswith("#"))
        for forbidden in ("systemctl", "ssh-keygen", "useradd", "/etc/machine-id", "/etc/fstab", "/etc/ssh", "/etc/shadow",
                          "/etc/tup", "/etc/sudoers", "/etc/passwd"):
            self.assertNotIn(forbidden, code.replace("/usr/lib/tup/remote", ""))
        for assertion in ("__pycache__", "owner-enrolled.json", "/etc/machine-id", "ssh_host_", "/etc/fstab"):
            self.assertIn(assertion, final)
        self.assertIn("python3 -I -B", self.text)
        self.assertNotIn("python3 -c", self.text)
        access = (PAGES / "03-access.sh").read_text(encoding="ascii")
        self.assertIn("[ ! -e /usr/lib/tup/remote/__pycache__ ]", access)  # the same -B discipline, checked there

    @unittest.skipUnless(os.name == "posix" and shutil.which("grub-script-check") and shutil.which("grub-mkstandalone"),
                         "needs GRUB's tools and Linux")
    def test_the_pages_python_check_passes_against_an_installed_copy_with_this_hosts_tools(self):
        """The embedded check, run with this host's tools and its paths pointed at a temporary prefix. Not the layer
        runner and not the target's Python or GRUB: it shows the check is coherent and that its failure arm works."""
        snippet = self.text.split('python3 -I -B - << "EOF"\n', 1)[1].split("\nEOF\n", 1)[0]
        with tempfile.TemporaryDirectory() as temporary:
            prefix = Path(temporary)
            tree = prefix / "usr/lib/tup-installer/tup"
            for name in ("install", "boot", "remote"):
                (tree / name).mkdir(parents=True)
            shutil.copyfile(TUP / "install/disk.py", tree / "install/disk.py")
            for name in ("__init__.py", "inputs.py"):
                shutil.copyfile(TUP / "boot" / name, tree / "boot" / name)
            for name in ("enroll.py", "policy.py", "firewall.py"):
                shutil.copyfile(TUP / "remote" / name, tree / "remote" / name)
            local = snippet.replace("/usr/lib/tup-installer", str(prefix / "usr/lib/tup-installer")).replace(
                "/usr/lib/tup/remote/enroll.py", str(tree / "remote/enroll.py")).replace(
                "host = disk.Host()", "disk.PATH = os.environ['PATH']\nhost = disk.Host()")
            self.assertNotEqual(local, snippet)
            done = subprocess.run([sys.executable, "-I", "-B", "-"], input=local, capture_output=True, text=True, timeout=300)
            self.assertEqual((done.returncode, done.stderr), (0, ""))
            broken = local.replace('host.which("grub-script-check")', 'host.which("grub-script-check-absent")')
            self.assertNotEqual(broken, local)
            done = subprocess.run([sys.executable, "-I", "-B", "-"], input=broken, capture_output=True, text=True, timeout=300)
            self.assertNotEqual(done.returncode, 0)
            self.assertFalse(list(prefix.rglob("__pycache__")))


if __name__ == "__main__":
    unittest.main()
