import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Five findings of the GPT-6 Astra review of 2026-10-13, each reproduced before its fix: sendmsg refused, fchmod on
# the read-only JOB refused, truncation refused on a Landlock older than ABI 3, inherited descriptors closed, an
# unusable JOB a named refusal (exit 125). The root-only NPROC finding was not reproducible here (not root).


def test_sendmsg_is_denied():
    import struct
    import landlock_exec as m

    for arch, sendmsg_nr in [('x86_64', 46), ('aarch64', 211)]:
        program = m.seccomp_program(arch, 1234)
        words = {m.OFF_ARCH: m.ARCH[arch], m.OFF_NR: sendmsg_nr}
        pc = acc = 0
        while True:
            op, jt, jf, k = struct.unpack_from('=HBBI', program, pc * 8)
            if op == m.LD_ABS_W:
                acc = words.get(k, 0)
                pc += 1
            elif op == m.JEQ_K:
                pc += 1 + (jt if acc == k else jf)
            elif op == m.JGE_K:
                pc += 1 + (jt if acc >= k else jf)
            else:
                assert op == m.RET_K
                assert k == m.RET_ERRNO_EPERM, (arch, 'sendmsg is allowed')
                break


def test_read_only_job_metadata_cannot_change():
    import os, pathlib, platform, stat, subprocess, sys, tempfile, unittest
    import landlock_exec as m

    arch = platform.machine()
    if sys.platform != 'linux' or arch not in m.NR or m.abi_version(m.NR[arch]) < 1:
        raise unittest.SkipTest('requires Linux with Landlock')
    python = os.path.realpath(sys.executable)
    payload = "import os, sys\nfd = os.open(sys.argv[1], os.O_RDONLY)\ntry:\n    os.fchmod(fd, 0o600)\nexcept PermissionError:\n    pass\n"
    with tempfile.TemporaryDirectory() as job:
        victim = pathlib.Path(job) / 'input'
        victim.write_text('specification')
        victim.chmod(0o644)
        result = subprocess.run(
            [python, m.__file__, job, python, '-I', '-S', '-c', payload, str(victim)],
            capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert stat.S_IMODE(victim.stat().st_mode) == 0o644


def test_old_abi_cannot_truncate_outside_job():
    import os, pathlib, platform, subprocess, sys, tempfile, unittest
    from pathlib import Path
    import landlock_exec as m

    arch = platform.machine()
    if sys.platform != 'linux' or arch not in m.NR:
        raise unittest.SkipTest('requires supported Linux')
    available = m.abi_version(m.NR[arch])
    if available < 1:
        raise unittest.SkipTest('requires Landlock')
    abi = min(available, 2)
    python = os.path.realpath(sys.executable)
    driver = (f'import sys; sys.path.insert(0, {str(Path(m.__file__).parent)!r}); import landlock_exec as m; '
              f'm.abi_version = lambda nr: {abi}; m.main(sys.argv[1:])')
    payload = "import os, sys\ntry:\n    os.truncate(sys.argv[1], 0)\nexcept PermissionError:\n    pass\n"
    with tempfile.TemporaryDirectory() as directory:
        base = pathlib.Path(directory)
        job = base / 'job'
        job.mkdir()
        victim = base / 'outside'
        victim.write_bytes(b'keep this')
        result = subprocess.run(
            [python, '-c', driver, str(job), python, '-I', '-S', '-c', payload, str(victim)],
            capture_output=True, text=True)
        assert result.returncode in (0, 125), result.stderr
        assert victim.read_bytes() == b'keep this'


def test_inherited_descriptor_cannot_write_outside_job():
    import os, pathlib, platform, subprocess, sys, tempfile, unittest
    import landlock_exec as m

    arch = platform.machine()
    if sys.platform != 'linux' or arch not in m.NR or m.abi_version(m.NR[arch]) < 1:
        raise unittest.SkipTest('requires Linux with Landlock')
    python = os.path.realpath(sys.executable)
    payload = "import os, sys\ntry:\n    os.write(int(sys.argv[1]), b'X')\nexcept OSError:\n    pass\n"
    with tempfile.TemporaryDirectory() as directory:
        base = pathlib.Path(directory)
        job = base / 'job'
        job.mkdir()
        victim = base / 'outside'
        victim.write_bytes(b'original')
        with victim.open('r+b') as inherited:
            fd = inherited.fileno()
            result = subprocess.run(
                [python, m.__file__, str(job), python, '-I', '-S', '-c', payload, str(fd)],
                pass_fds=(fd,), capture_output=True, text=True)
        assert result.returncode in (0, 125), result.stderr
        assert victim.read_bytes() == b'original'


def test_invalid_job_is_a_named_sandbox_refusal():
    import pathlib, tempfile, unittest
    from unittest import mock
    import landlock_exec as m

    class Refused(BaseException):
        pass

    with tempfile.TemporaryDirectory() as directory:
        job = pathlib.Path(directory) / 'job'
        job.write_text('not a directory')
        with mock.patch.object(m.sys, 'platform', 'linux'), \
             mock.patch.object(m.platform, 'machine', return_value='x86_64'), \
             mock.patch.object(m, 'abi_version', return_value=4), \
             mock.patch.object(m, 'die', side_effect=Refused):
            with unittest.TestCase().assertRaises(Refused):
                m.main([str(job), '/usr/bin/true'])


def test_program_prefix_names_the_install_root_outside_usr():
    import landlock_exec as le
    assert le.program_prefix("/usr/bin/python3") is None
    assert le.program_prefix("/bin/sh") is None
    import os
    # realpath may rewrite a prefix the host symlinks (macOS keeps /home under /System/Volumes/Data)
    real = os.path.realpath
    assert le.program_prefix("/opt/hostedtoolcache/Python/3.10.22/x64/bin/python3.10") == real("/opt/hostedtoolcache/Python/3.10.22/x64")
    assert le.program_prefix("/home/x/venv/bin/python") == real("/home/x/venv")
    assert le.program_prefix("/opt/tool/python") == real("/opt/tool")
