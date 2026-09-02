#!/bin/bash
# OVERRIDE ch11/reboot: the build VM is NOT rebooted. tup's first boot
# happens from the host under QEMU, as the boot witness — see tup/receipts.
echo "reboot skipped: tup boots under QEMU from the host (boot witness step)"
