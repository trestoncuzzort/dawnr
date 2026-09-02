# tup layer agent: an unprivileged user, and no self-modification
# TUP_ACTION_PAGE
#
# Two findings from the first outside boots of tup 0.1 (a Windows host, QEMU,
# 2026-09-02), both about what the agent layer left out.
#
# 1. Root was the only usable account, and Claude Code refuses its bypass
#    mode as root ("--dangerously-skip-permissions cannot be used with
#    root/sudo privileges"). The mode an agent box actually runs in was
#    therefore unreachable out of the box; the workaround was a useradd by
#    hand on every fresh image. So the layer now ships the user: `agent`,
#    home /home/agent, shell bash, password LOCKED. Reach it from root with
#    `su - agent`; nothing logs in as it directly. /usr/bin/claude and
#    /usr/bin/node are already symlinked by the earlier pages, so its PATH
#    needs nothing extra (measured in the guest: `su - <user> -c 'command -v
#    claude'` -> /usr/bin/claude).
#
# 2. On its first boot with a network, Claude Code updated ITSELF in place
#    (2.1.251 -> 2.1.258, measured), rewriting files under /opt/node-*/lib
#    that the layer's INVENTORY had just hashed. A distro whose claim is that
#    every byte is accounted for cannot have a layer that changes its own
#    bytes in the background, so the updater is disabled system-wide in the
#    profile. Upgrading Claude Code is a rebuilt layer with a new receipt, not
#    a download.
#
# Cost, stated: this page modifies /etc/passwd, /etc/group, /etc/shadow,
# /etc/gshadow and /etc/profile, and adds /home/agent with the skeleton
# files. The layer diff will list every one.

useradd -m -s /bin/bash -c "tup agent (unprivileged; su - agent)" agent
passwd -l agent >/dev/null
cat >> /etc/profile << "EOF"
# tup: the agent layer does not update itself. A new Claude Code is a new
# layer build with a new INVENTORY, never a background download.
export DISABLE_AUTOUPDATER=1
EOF
echo "agent user: $(id agent)"
echo "autoupdater: $(grep -c DISABLE_AUTOUPDATER /etc/profile) line(s) in /etc/profile"
