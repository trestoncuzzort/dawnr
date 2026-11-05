# Private owner access

This is the first remote-access layer, not a working remote TUP installation.
`source.json` records authenticated OpenSSH **10.6p1** source. The portable
release signature was checked against the primary fingerprint published by
[OpenSSH](https://www.openssh.org/portable.html); retained key and signature
bytes live in `evidence/`. The tarball stays in the external source cache.
The [10.6 release](https://www.openssh.org/txt/release-10.6) includes security
fixes newer than the BLFS 13.1 book's OpenSSH 10.5p1 recipe.

`policy.py` renders a complete owner configuration and checks actual `sshd -T`
output. It accepts one named normal account, one to eight Ed25519 public keys,
and explicit private or loopback IP listeners. Comments are removed from keys.
Malformed SSH wire encodings, private-key files, authorized_keys options,
wildcards, public listeners and configuration injection are refused.

The policy requires public-key authentication, disables root/password/keyboard
interactive login, and reads owner keys from the root-controlled
`/etc/tup/authorized_keys/%u`. It keeps current upstream cryptographic defaults.
Local TCP forwarding supports accessing an owner's local services; agent,
remote TCP, Unix socket, tunnel and X11 forwarding are disabled. These settings
do not sandbox an owner who has a shell. Compartment and tenant authority remain
separate work.

Render enrollment only into a **new private Linux directory** beneath a
caller-owned parent that others cannot write. The parent must already exist.
For example, with explicit private configuration variables:

```sh
python3 tup/remote/policy.py \
  --owner "$TUP_OWNER" --listen "$TUP_MANAGEMENT_ADDRESS" \
  --public-keys "$TUP_OWNER_PUBLIC_KEYS" --output "$TUP_ENROLLMENT_OUTPUT"
```

This operation does not create an account, generate host keys, change `/etc`,
enable a firewall, or start a service. Output contains private provisioning
metadata and must stay outside this public repository. Existing output paths
are refused. A failed write may leave a partial private directory; it is never
an applied enrollment or a successful installation marker.

The generated unit requires `tup-firewall.service` and an applied owner
enrollment marker. Those prerequisites are not implemented by this renderer,
so the unit must not be enabled yet. It generates unique host keys at first
start using `ssh-keygen -A` and then checks configuration before listening.
Generic images must contain neither host private keys nor owner enrollment.
Do not mask failure with a shared key or a default password.

The eventual account must have a valid home/shell and an explicit administration
policy. With portable OpenSSH on Linux, a shadow password beginning with `!`
can lock out public-key login too; test the selected account state rather than
assuming `passwd -l` means only password authentication is disabled. The current
build excludes PAM and GSSAPI; their explicit `no` settings produce unsupported
option warnings in that build. Enabling either feature later requires new
configuration, session and authentication tests.

## Evidence and remaining work

A disposable Ubuntu host build of the authenticated source accepted the policy
with a temporary host key. OpenSSH 10.6 prints canonical mixed-case keywords in
`sshd -T`; an initial checker incorrectly expected lowercase output. The checker
now normalizes keyword case while preserving argument values, with negative
tests for altered authentication, owner, key authority and listen addresses.
The initial missing-host-key refusal and checker failure are retained in the
host-check receipt. No daemon was started and no remote login was performed.

This host build uses Ubuntu's compiler and OpenSSL 3. It does not establish
compatibility with TUP's compiler, OpenSSL 4 or target service environment.
Target construction must follow the
[BLFS portable OpenSSH recipe](https://www.linuxfromscratch.org/blfs/view/stable-systemd/postlfs/openssh.html),
with bounded jobs, retained upstream test logs, a dedicated locked privilege
separation account and directory, and `make install-nokeys` when producing an
unenrolled image. No build or install command is executed on module import.

H24-H28 remain open through target compilation, firewall/VPN integration,
account/privilege provisioning, host-key verification, denied authentication,
actual login/file transfer, reconnect and reboot tests. Late private-interface
availability and address changes need a tested recovery policy. A listener
bound to an old address is not a working remote service. SSH disconnect does
not provide durable jobs by itself; explicit job management and separate
resource reservations are still required. External-network MacBook access,
key rotation/revocation and hardware stress remain qualification gates.

Configuration semantics follow the
[OpenSSH manual](https://man.openbsd.org/sshd_config). In particular, most
keywords take their first supplied value; this layer replaces a reviewed full
configuration instead of appending options to an unknown file.
