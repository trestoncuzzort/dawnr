#!/usr/bin/env python3
"""t/landlock_exec.py -- restrict this process with Landlock and seccomp, then exec a program in it (2026-10-03).

    python3 -I -S t/landlock_exec.py JOB PROGRAM [ARG ...]

t/py_sandbox.py's second Linux backend (T_SANDBOX=landlock), for machines where bubblewrap cannot create its
namespaces and nobody can grant them: Ubuntu 23.10 and later restrict unprivileged user namespaces unless an
AppArmor profile allows them, which needs root (the lab workstation, 2026-10-03). Landlock needs neither root nor a
namespace: any process may restrict itself, and everything it execs inherits the restriction
(docs.kernel.org/userspace-api/landlock.html). Codex CLI keeps the same pair as its backup Linux sandbox,
Landlock for files and a seccomp filter for the network (github.com/openai/codex,
codex-rs/linux-sandbox/src/landlock.rs); this one is narrower on files, since a test of a pure function needs to
read nothing of the user's.

What the program can do afterwards, mirroring the bubblewrap backend (t/py_sandbox.py `_command`):
  read and execute beneath /usr, /lib, /lib64, /bin and /etc/alternatives; read JOB; read and write JOB/tmp
  (its working folder, HOME and TMPDIR); /dev/null, /dev/zero, /dev/full, /dev/random, /dev/urandom; its own
  /proc entry. Nothing else on any filesystem: not /home, not /tmp, not other processes' /proc.
What the seccomp filter refuses (EPERM), where bubblewrap's namespaces would have hidden the target instead:
  - every socket() (socketpair(AF_UNIX) stays), connect, bind, listen, accept, send/recv by address, socket
    options: Codex's restricted mode, tightened to no new sockets at all;
  - a signal, a resource limit or a scheduling change aimed at any process but itself (kill, tkill, tgkill,
    rt_sig*queueinfo, prlimit64, sched_set*, setpriority), pidfds, ptrace, process_vm_*, and the fcntl/ioctl
    forms that route SIGIO to another process (F_SETOWN, F_SETOWN_EX, F_SETSIG, FIOSETOWN, SIOCSPGRP);
    Landlock scopes signals itself only from ABI 6, and this lab kernel has 4;
  - System V IPC and POSIX message queues (bubblewrap unshares IPC), io_uring, mounts and namespaces, keyrings,
    bpf, perf, userfaultfd, kernel modules and other administration calls;
  - chmod, chown, utime and xattr changes by path: Landlock does not restrict these (its documentation's own
    warning), so a path outside the sandbox would otherwise be fair game;
  - TIOCSTI (pushing keystrokes into a terminal), as a second wall behind the absent terminal.
New processes and threads are refused by RLIMIT_NPROC 0, set here and again by the runner, as under bubblewrap.

It fails closed: if Landlock or seccomp cannot be applied the program is not run, and the exit code is 125.
"""
from __future__ import annotations

import ctypes
import os
import platform
import resource
import signal
import struct
import sys

LANDLOCK_CREATE_RULESET_VERSION = 1 << 0
LANDLOCK_RULE_PATH_BENEATH = 1
FS = {"EXECUTE": 1 << 0, "WRITE_FILE": 1 << 1, "READ_FILE": 1 << 2, "READ_DIR": 1 << 3, "REMOVE_DIR": 1 << 4,
      "REMOVE_FILE": 1 << 5, "MAKE_CHAR": 1 << 6, "MAKE_DIR": 1 << 7, "MAKE_REG": 1 << 8, "MAKE_SOCK": 1 << 9,
      "MAKE_FIFO": 1 << 10, "MAKE_BLOCK": 1 << 11, "MAKE_SYM": 1 << 12, "REFER": 1 << 13, "TRUNCATE": 1 << 14,
      "IOCTL_DEV": 1 << 15, "RESOLVE_UNIX": 1 << 16}
# the rights each ABI added (include/uapi/linux/landlock.h; the compatibility switch in the kernel's documentation)
FS_SINCE = {"REFER": 2, "TRUNCATE": 3, "IOCTL_DEV": 5, "RESOLVE_UNIX": 9}
NET_BIND_TCP, NET_CONNECT_TCP, NET_BIND_UDP, NET_CONNECT_SEND_UDP = 1 << 0, 1 << 1, 1 << 2, 1 << 3
SCOPE_ABSTRACT_UNIX_SOCKET, SCOPE_SIGNAL = 1 << 0, 1 << 1

ARCH = {"x86_64": 0xC000003E, "aarch64": 0xC00000B7}        # AUDIT_ARCH_X86_64, AUDIT_ARCH_AARCH64 (linux/audit.h)
# syscall numbers read from the kernel headers (asm/unistd_64.h for x86_64, asm-generic/unistd.h for aarch64)
NR = {
    "x86_64": {"landlock_create_ruleset": 444, "landlock_add_rule": 445, "landlock_restrict_self": 446,
               "ptrace": 101, "process_vm_readv": 310, "process_vm_writev": 311, "io_uring_setup": 425,
               "io_uring_enter": 426, "io_uring_register": 427, "connect": 42, "accept": 43, "accept4": 288,
               "bind": 49, "listen": 50, "getpeername": 52, "getsockname": 51, "shutdown": 48, "sendto": 44,
               "sendmmsg": 307, "recvmmsg": 299, "getsockopt": 55, "setsockopt": 54, "pidfd_open": 434,
               "pidfd_send_signal": 424, "pidfd_getfd": 438, "process_madvise": 440, "process_mrelease": 448,
               "kcmp": 312, "ioprio_set": 251, "migrate_pages": 256, "move_pages": 279, "perf_event_open": 298,
               "bpf": 321, "userfaultfd": 323, "keyctl": 250, "add_key": 248, "request_key": 249, "mount": 165,
               "umount2": 166, "pivot_root": 155, "chroot": 161, "unshare": 272, "setns": 308, "open_tree": 428,
               "move_mount": 429, "fsopen": 430, "fsconfig": 431, "fsmount": 432, "fspick": 433,
               "mount_setattr": 442, "chmod": 90, "fchmodat": 268, "fchmodat2": 452, "chown": 92, "lchown": 94,
               "fchownat": 260, "setxattr": 188, "lsetxattr": 189, "removexattr": 197, "lremovexattr": 198,
               "setxattrat": 463, "removexattrat": 466, "utime": 132, "utimes": 235, "futimesat": 261,
               "utimensat": 280, "inotify_add_watch": 254, "fanotify_init": 300, "fanotify_mark": 301,
               "quotactl": 179, "quotactl_fd": 443, "name_to_handle_at": 303, "open_by_handle_at": 304, "acct": 163,
               "swapon": 167, "swapoff": 168, "reboot": 169, "kexec_load": 246, "kexec_file_load": 320,
               "init_module": 175, "finit_module": 313, "delete_module": 176, "iopl": 172, "ioperm": 173,
               "syslog": 103, "sethostname": 170, "setdomainname": 171, "settimeofday": 164, "clock_settime": 227,
               "adjtimex": 159, "clock_adjtime": 305, "lookup_dcookie": 212, "vhangup": 153,
               "shmget": 29, "shmat": 30, "shmctl": 31, "shmdt": 67, "semget": 64, "semop": 65, "semctl": 66,
               "semtimedop": 220, "msgget": 68, "msgsnd": 69, "msgrcv": 70, "msgctl": 71, "mq_open": 240,
               "mq_unlink": 241, "mq_timedsend": 242, "mq_timedreceive": 243, "mq_notify": 244,
               "mq_getsetattr": 245, "socket": 41,
               "kill": 62, "tkill": 200, "tgkill": 234, "rt_sigqueueinfo": 129, "rt_tgsigqueueinfo": 297,
               "prlimit64": 302, "sched_setaffinity": 203, "sched_setscheduler": 144, "sched_setparam": 142,
               "sched_setattr": 314, "setpriority": 141, "socketpair": 53, "fcntl": 72, "ioctl": 16},
    "aarch64": {"landlock_create_ruleset": 444, "landlock_add_rule": 445, "landlock_restrict_self": 446,
                "ptrace": 117, "process_vm_readv": 270, "process_vm_writev": 271, "io_uring_setup": 425,
                "io_uring_enter": 426, "io_uring_register": 427, "connect": 203, "accept": 202, "accept4": 242,
                "bind": 200, "listen": 201, "getpeername": 205, "getsockname": 204, "shutdown": 210,
                "sendto": 206, "sendmmsg": 269, "recvmmsg": 243, "getsockopt": 209, "setsockopt": 208,
                "pidfd_open": 434, "pidfd_send_signal": 424, "pidfd_getfd": 438, "process_madvise": 440,
                "process_mrelease": 448, "kcmp": 272, "ioprio_set": 30, "migrate_pages": 238, "move_pages": 239,
                "perf_event_open": 241, "bpf": 280, "userfaultfd": 282, "keyctl": 219, "add_key": 217,
                "request_key": 218, "mount": 40, "umount2": 39, "pivot_root": 41, "chroot": 51, "unshare": 97,
                "setns": 268, "open_tree": 428, "move_mount": 429, "fsopen": 430, "fsconfig": 431,
                "fsmount": 432, "fspick": 433, "mount_setattr": 442, "fchmodat": 53, "fchmodat2": 452,
                "fchownat": 54, "setxattr": 5, "lsetxattr": 6, "removexattr": 14, "lremovexattr": 15,
                "setxattrat": 463, "removexattrat": 466, "utimensat": 88, "inotify_add_watch": 27,
                "fanotify_init": 262, "fanotify_mark": 263, "quotactl": 60, "quotactl_fd": 443,
                "name_to_handle_at": 264, "open_by_handle_at": 265, "acct": 89, "swapon": 224, "swapoff": 225,
                "reboot": 142, "kexec_load": 104, "kexec_file_load": 294, "init_module": 105,
                "finit_module": 273, "delete_module": 106, "syslog": 116, "sethostname": 161,
                "setdomainname": 162, "settimeofday": 170, "clock_settime": 112, "adjtimex": 171,
                "clock_adjtime": 266, "lookup_dcookie": 18, "vhangup": 58,
                "shmget": 194, "shmat": 196, "shmctl": 195, "shmdt": 197, "semget": 190, "semop": 193,
                "semctl": 191, "semtimedop": 192, "msgget": 186, "msgsnd": 189, "msgrcv": 188, "msgctl": 187,
                "mq_open": 180, "mq_unlink": 181, "mq_timedsend": 182, "mq_timedreceive": 183, "mq_notify": 184,
                "mq_getsetattr": 185, "socket": 198,
                "kill": 129, "tkill": 130, "tgkill": 131, "rt_sigqueueinfo": 138, "rt_tgsigqueueinfo": 240,
                "prlimit64": 261, "sched_setaffinity": 122, "sched_setscheduler": 119, "sched_setparam": 118,
                "sched_setattr": 274, "setpriority": 140, "socketpair": 199, "fcntl": 25, "ioctl": 29},
}
DENY = ("ptrace process_vm_readv process_vm_writev io_uring_setup io_uring_enter io_uring_register connect accept "
        "accept4 bind listen getpeername getsockname shutdown sendto sendmmsg recvmmsg getsockopt setsockopt "
        "pidfd_open pidfd_send_signal pidfd_getfd process_madvise process_mrelease kcmp ioprio_set migrate_pages "
        "move_pages perf_event_open bpf userfaultfd keyctl add_key request_key mount umount2 pivot_root chroot "
        "unshare setns open_tree move_mount fsopen fsconfig fsmount fspick mount_setattr chmod fchmodat fchmodat2 "
        "chown lchown fchownat setxattr lsetxattr removexattr lremovexattr setxattrat removexattrat utime utimes "
        "futimesat utimensat inotify_add_watch fanotify_init fanotify_mark quotactl quotactl_fd name_to_handle_at "
        "open_by_handle_at acct swapon swapoff reboot kexec_load kexec_file_load init_module finit_module "
        "delete_module iopl ioperm syslog sethostname setdomainname settimeofday clock_settime adjtimex "
        "clock_adjtime lookup_dcookie vhangup shmget shmat shmctl shmdt semget semop semctl semtimedop msgget "
        "msgsnd msgrcv msgctl mq_open mq_unlink mq_timedsend mq_timedreceive mq_notify mq_getsetattr socket").split()
SELF_ONLY = "kill tkill tgkill rt_sigqueueinfo rt_tgsigqueueinfo".split()       # first argument must be this pid
SELF_OR_ZERO = "prlimit64 sched_setaffinity sched_setscheduler sched_setparam sched_setattr".split()
AF_UNIX, PRIO_PROCESS = 1, 0
F_SETOWN, F_SETSIG, F_SETOWN_EX = 8, 10, 15                    # asm-generic/fcntl.h
TIOCSTI, FIOSETOWN, SIOCSPGRP = 0x5412, 0x8901, 0x8902         # asm-generic/ioctls.h, asm-generic/sockios.h

PR_SET_NO_NEW_PRIVS, PR_SET_PDEATHSIG, PR_SET_SECCOMP, SECCOMP_MODE_FILTER = 38, 1, 22, 2
RET_ALLOW, RET_ERRNO_EPERM, RET_KILL_PROCESS = 0x7FFF0000, 0x00050000 | 1, 0x80000000
LD_ABS_W, JEQ_K, JGE_K, RET_K = 0x20, 0x15, 0x35, 0x06         # BPF_LD|BPF_W|BPF_ABS, BPF_JMP|BPF_JEQ|BPF_K, ...
OFF_NR, OFF_ARCH, OFF_ARG = 0, 4, 16                           # struct seccomp_data; args[i] at 16 + 8 i (low word)

libc = ctypes.CDLL(None, use_errno=True)
libc.syscall.restype = ctypes.c_long


def prctl(option: int, arg2: int = 0, arg3: int = 0) -> int:
    """prctl(2), variadic like syscall(2): the unused arguments must reach the kernel as zero"""
    return libc.prctl(ctypes.c_int(option), ctypes.c_ulong(arg2), ctypes.c_ulong(arg3), ctypes.c_ulong(0), ctypes.c_ulong(0))


def die(msg: str) -> None:
    sys.stderr.write(f"landlock_exec: {msg}\n")
    os._exit(125)


def sys_call(nr: int, *args) -> int:
    """syscall(2) with every argument a full register: variadic, so a bare Python int would go as a 32-bit int
    whose upper half is undefined"""
    r = libc.syscall(ctypes.c_long(nr), *[a if isinstance(a, (ctypes.Array, ctypes._Pointer)) or a is None
                                         else ctypes.c_ulong(a) for a in args])
    if r < 0:
        e = ctypes.get_errno()
        raise OSError(e, os.strerror(e))
    return r


def abi_version(nr: dict) -> int:
    """The running kernel's Landlock ABI, or 0 when it has none (ENOSYS) or it is disabled (EOPNOTSUPP)."""
    try:
        return sys_call(nr["landlock_create_ruleset"], None, 0, LANDLOCK_CREATE_RULESET_VERSION)
    except OSError:
        return 0


def fs_rights(abi: int, names) -> int:
    return sum(FS[n] for n in names if FS_SINCE.get(n, 1) <= abi)


def landlock(nr: dict, abi: int, job: str) -> None:
    handled = fs_rights(abi, FS)
    net = (NET_BIND_TCP | NET_CONNECT_TCP if abi >= 4 else 0) | (NET_BIND_UDP | NET_CONNECT_SEND_UDP if abi >= 10 else 0)
    scoped = SCOPE_ABSTRACT_UNIX_SOCKET | SCOPE_SIGNAL if abi >= 6 else 0
    attr = struct.pack("=QQQ", handled, net, scoped)       # a kernel older than a field reads only its own prefix,
    size = 8 if abi < 4 else 16 if abi < 6 else 24         # and refuses nonzero bytes it does not know
    buf = ctypes.create_string_buffer(attr[:size], size)
    ruleset = sys_call(nr["landlock_create_ruleset"], buf, size, 0)
    read_x = fs_rights(abi, ("EXECUTE", "READ_FILE", "READ_DIR"))
    read = fs_rights(abi, ("READ_FILE", "READ_DIR"))
    write = fs_rights(abi, ("READ_FILE", "READ_DIR", "WRITE_FILE", "TRUNCATE", "REMOVE_DIR", "REMOVE_FILE",
                            "MAKE_DIR", "MAKE_REG", "MAKE_SYM", "REFER"))
    dev_rw = fs_rights(abi, ("READ_FILE", "WRITE_FILE", "TRUNCATE"))
    rules = [(d, read_x) for d in ("/usr", "/lib", "/lib64", "/bin", "/etc/alternatives")]
    rules += [(job, read), (os.path.join(job, "tmp"), write), (f"/proc/{os.getpid()}", read)]
    rules += [(d, dev_rw) for d in ("/dev/null", "/dev/zero", "/dev/full")]
    rules += [(d, fs_rights(abi, ("READ_FILE",))) for d in ("/dev/random", "/dev/urandom")]
    for path, access in rules:
        if not os.path.exists(path):
            continue
        fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
        try:
            if not os.path.isdir(path):     # a rule on a file may name only file rights
                access &= fs_rights(abi, ("EXECUTE", "READ_FILE", "WRITE_FILE", "TRUNCATE", "IOCTL_DEV"))
            rule = ctypes.create_string_buffer(struct.pack("=Qi", access & handled, fd), 12)    # packed in the uapi
            sys_call(nr["landlock_add_rule"], ruleset, LANDLOCK_RULE_PATH_BENEATH, rule, 0)
        finally:
            os.close(fd)
    sys_call(nr["landlock_restrict_self"], ruleset, 0)
    os.close(ruleset)


def bpf(code: int, jt: int, jf: int, k: int) -> bytes:
    return struct.pack("=HBBI", code, jt, jf, k & 0xFFFFFFFF)


def seccomp_program(arch: str, me: int) -> bytes:
    nr = NR[arch]
    out = [bpf(LD_ABS_W, 0, 0, OFF_ARCH), bpf(JEQ_K, 1, 0, ARCH[arch]), bpf(RET_K, 0, 0, RET_KILL_PROCESS),
           bpf(LD_ABS_W, 0, 0, OFF_NR)]
    if arch == "x86_64":                                    # the x32 ABI's numbers carry bit 30: refuse them all
        out += [bpf(JGE_K, 0, 1, 0x40000000), bpf(RET_K, 0, 0, RET_ERRNO_EPERM)]
    for name in DENY:
        if name in nr:
            out += [bpf(JEQ_K, 0, 1, nr[name]), bpf(RET_K, 0, 0, RET_ERRNO_EPERM)]

    def block(name: str, body: list) -> None:               # if nr == name: body (which always returns)
        out.append(bpf(JEQ_K, 0, len(body), nr[name]))
        out.extend(body)

    def allow_if_arg(i: int, values) -> list:
        body = [bpf(LD_ABS_W, 0, 0, OFF_ARG + 8 * i)]
        for v in values:
            body += [bpf(JEQ_K, 0, 1, v), bpf(RET_K, 0, 0, RET_ALLOW)]
        return body + [bpf(RET_K, 0, 0, RET_ERRNO_EPERM)]

    def deny_if_arg(i: int, values) -> list:
        body = [bpf(LD_ABS_W, 0, 0, OFF_ARG + 8 * i)]
        for v in values:
            body += [bpf(JEQ_K, 0, 1, v), bpf(RET_K, 0, 0, RET_ERRNO_EPERM)]
        return body + [bpf(RET_K, 0, 0, RET_ALLOW)]

    for name in SELF_ONLY:
        block(name, allow_if_arg(0, [me]))
    for name in SELF_OR_ZERO:
        block(name, allow_if_arg(0, [0, me]))
    block("setpriority", [bpf(LD_ABS_W, 0, 0, OFF_ARG), bpf(JEQ_K, 1, 0, PRIO_PROCESS), bpf(RET_K, 0, 0, RET_ERRNO_EPERM)]
          + allow_if_arg(1, [0, me]))
    block("socketpair", allow_if_arg(0, [AF_UNIX]))
    block("fcntl", deny_if_arg(1, [F_SETOWN, F_SETSIG, F_SETOWN_EX]))
    block("ioctl", deny_if_arg(1, [TIOCSTI, FIOSETOWN, SIOCSPGRP]))
    out.append(bpf(RET_K, 0, 0, RET_ALLOW))
    return b"".join(out)


def seccomp(arch: str, me: int) -> None:
    prog = seccomp_program(arch, me)
    n = len(prog) // 8
    if n > 4096:                                            # BPF_MAXINSNS
        die(f"seccomp program too long ({n})")
    filt = ctypes.create_string_buffer(prog, len(prog))

    class SockFprog(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.c_void_p)]

    fprog = SockFprog(n, ctypes.cast(filt, ctypes.c_void_p))
    if prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, ctypes.addressof(fprog)) != 0:
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_SECCOMP)")


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        die("usage: landlock_exec.py JOB PROGRAM [ARG ...]")
    job, program, args = os.path.realpath(argv[0]), argv[1], argv[1:]
    arch = platform.machine()
    if sys.platform != "linux" or arch not in NR:
        die(f"only Linux on x86_64 or aarch64 (this is {sys.platform} {arch})")
    nr, me, parent = NR[arch], os.getpid(), os.getppid()
    abi = abi_version(nr)
    if abi < 1:
        die("this kernel has no Landlock (or it is disabled); the program was not run")
    os.makedirs(os.path.join(job, "tmp"), exist_ok=True)
    try:
        if prctl(PR_SET_PDEATHSIG, signal.SIGKILL) != 0 or os.getppid() != parent:
            die("could not tie this process to its parent")
        if prctl(PR_SET_NO_NEW_PRIVS, 1) != 0:
            die("could not set no_new_privs")
        landlock(nr, abi, job)
        seccomp(arch, me)
    except Exception as e:                                  # noqa: BLE001 -- any failure: do not run the program
        die(f"the sandbox could not be applied ({type(e).__name__}: {e}); the program was not run")
    resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    tmp = os.path.join(job, "tmp")
    os.chdir(tmp)
    env = {"HOME": tmp, "TMPDIR": tmp, "PATH": "/usr/bin:/bin"}
    env.update({k: v for k, v in os.environ.items() if k in ("LANG", "LC_ALL", "LC_CTYPE")})
    try:
        os.execve(program, args, env)
    except OSError as e:
        die(f"could not run {program}: {e}")


if __name__ == "__main__":
    main(sys.argv[1:])
