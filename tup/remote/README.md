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

The unit uses `KillMode=control-group` with a 30-second stop deadline. Stopping
or restarting SSH therefore ends its existing sessions and descendants; a
reload uses SIGHUP. Durable workloads must run in separately supervised service
cgroups so an access-service restart does not become a job-lifetime policy.
This follows [systemd's process-killing interface](https://www.freedesktop.org/software/systemd/man/latest/systemd.kill.html).
The stop behavior still needs a target service test with real sessions.

## Evidence and remaining work

A disposable Ubuntu host build of the authenticated source accepted the policy
with a temporary host key. OpenSSH 10.6 prints canonical mixed-case keywords in
`sshd -T`; an initial checker incorrectly expected lowercase output. The checker
now normalizes keyword case while preserving argument values, with negative
tests for altered authentication, owner, key authority and listen addresses.
The initial missing-host-key refusal and checker failure are retained in the
host-check receipt. No daemon was started and no remote login was performed.

Independent review reproduced acceptance of a substituted host-key path and
missing or weakened connection limits. The checker now requires every selected
directive, including the host-key path, authentication limits, logging, SFTP,
keepalives and compression. Fifteen focused Linux tests pass, including the new
negative controls. The existing OpenSSH 10.6p1 binary also passed global and
IPv4/IPv6 connection-context checks; [the receipt](evidence/policy-check.json)
records its exact binary and the explicit extra test-key adjustment. These
configuration checks do not test actual authentication or service shutdown.

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

## Firewall sources and working probe

`firewall-sources.json` selects nftables 1.1.7, libnftnl 1.3.2 and libmnl 1.0.5.
The first two verified under the current Netfilter release primary
`8C5F7146A1757A65E2422A94D70D1A666ACF2B21`, using the complete key published on
the [official key page](https://www.netfilter.org/about.html#pgp). That page
explicitly revokes the older key used for libmnl's signature. Libmnl instead
verified against its exact filename, size and SHA512 in the authenticated
Gentoo snapshot already used for the core. The old signature is retained as
historical evidence and is not treated as valid current authorization.

`verify_sources.py` calls the existing `sources/source_lock.py` verifier for all
four remote sources; a previous success receipt never bypasses verification.
It also checks the full dated LFS 13.1 advisory query. Its selected advisory,
`sa-13.1-057`, is fixed by OpenSSH 10.6p1. Core library and kernel advisories
retain their separate source-lock dispositions and release gates.

```sh
python3 tup/remote/verify_sources.py --cache "$REMOTE_SOURCE_CACHE" \
  --gpg /usr/bin/gpg --output "$REMOTE_VERIFICATION_OUTPUT"
```

The [host build receipt](evidence/firewall-host-build.json) records an isolated
Ubuntu build and all 32 libnftnl tests passing. That probe uses nftables'
supported mini-GMP option because the host lacks GMP development headers;
the target recipe will use the core's GMP. No JSON, interactive CLI, iptables
compatibility, Python binding or upstream service is installed by this layer.
Those features are unnecessary for the selected policy. The release archive's
`INSTALL` and `configure.ac` define these supported options.

`firewall.py` renders a private nftables policy for exact listener and peer IP
addresses. Input and forwarding default to drop; outbound host traffic remains
allowed. The policy permits loopback, required ICMP/neighbor discovery, DHCP
replies and established return traffic. SSH has a separate peer gate **before**
the general established-connection rule, so removing a peer also blocks its
existing SSH flow. Key revocation still requires terminating the corresponding
SSH sessions; changing a key file alone does not do that. This host policy is
not a tenant-network isolation implementation.

The selected table is replaced with one [atomic nft transaction](https://wiki.nftables.org/wiki-nftables/index.php/Atomic_rule_replacement).
Other tables are preserved. A missing policy fails service startup, and stopping
the firewall unit retains the kernel's rules while SSH's dependency stops
access. No service is enabled by rendering. Overlay integration and a tested
network-change rollback remain required before unattended use.

```sh
python3 tup/remote/firewall.py --listen "$TUP_MANAGEMENT_ADDRESS" \
  --peer "$TUP_OWNER_PEER_ADDRESS" --output "$TUP_FIREWALL_OUTPUT"
sudo python3 tup/remote/probe_firewall.py --nft "$AUTHENTICATED_PROBE_NFT"
```

The probe automatically creates private network, PID and mount namespaces and
disposable IPv4/IPv6 peers. [Its result](evidence/firewall-probe.json) proves
allowed and denied TCP paths, repeated rule loading, preservation of another
table, malformed-batch rollback, and rejection of an established flow after
peer removal. Its listeners are confined to those namespaces. The target kernel,
DHCP, physical network, SSH authentication, service lifecycle and private
transport are still unqualified. The full upstream nftables kernel suite also
remains unrun; these bounded probes do not stand in for that suite.
