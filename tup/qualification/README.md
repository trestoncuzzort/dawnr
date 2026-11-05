# Resource observations

`observe_cgroup.py` reads the Linux cgroup v2 counters for a build and all its
descendants. Use the existing systemd service manager to create and limit the
group; the collector does not create cgroups or change limits.

For a supervised build, run the collector as the service's main process with
`--cgroup self --output NEW_LOG -- COMMAND ARGUMENTS...`. Use a fresh service
with `KillMode=control-group`, an explicit memory/swap/CPU budget and no automatic
restart. A collector timeout or failure must stop that entire service. Invoke
the service without combining `--wait` and `--remain-after-exit`, which waits
for an explicitly retained unit to be stopped.

The collector stays alive after its child exits long enough to save the final
kernel memory peak and counters. An external observer alone lost the final
sample because systemd removed the exited service's cgroup; that failed probe
is retained. Child failure propagates, and remaining tasks anywhere in the
descendant hierarchy refuse a successful completion observation.

Memory peak includes charged cache/kernel memory and collector overhead. The
`max_processes` field is the maximum sampled Linux `pids.current` task count,
including threads; it is not a distinct-process count. These measurements are
separate from package correctness and do not establish native-hardware stress
qualification. A removed cgroup, timeout or inaccessible counter is reported
as incomplete, never replaced with zero.

The [actual bounded probes](../receipts/native-dev-20261105/resource-collector-probe.json)
cover an 80 MiB allocation under a 128 MiB limit, exit status 7, and both direct
and nested-cgroup leftover workers. The collector uses the
[kernel's documented cgroup v2 interface](https://docs.kernel.org/admin-guide/cgroup-v2.html).
