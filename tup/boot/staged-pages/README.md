# Staged layer pages

`04-dosfstools.sh` is complete and host-rehearsed (`../evidence/dosfstools/host-rehearsal.json`)
but is not part of the boot chapter yet. `target/build.py` refuses a chapter whose `ORDER` and page
files disagree, and refuses an archive that has no verified source record, so a page cannot sit in
`../pages` before it is wired in. To wire it in:

1. `git mv tup/boot/staged-pages/04-dosfstools.sh tup/boot/pages/04-dosfstools.sh` and add the line
   `04-dosfstools.sh` to `tup/boot/pages/ORDER`.
2. In `tup/target/build.py` `verify_sources`, authenticate the record with the existing verifier:
   `record = load_json(source / "boot/dosfstools-source.json")` then
   `results[record["name"]] = verifier.verify_record(record, cache, source / "boot/evidence", gpg)`.
   The cache must also hold `dosfstools-4.2.tar.gz` (the signed Gentoo snapshot is already needed).
3. Update the expected archive list in `tests/test_target_layers.py` and the chapter table in
   `target/README.md`; change `PAGE` in `tests/test_boot_dosfstools.py` to the new page path.

The page needs `xxd` (Vim) and `blkid` (util-linux) in the layer chroot, both from the core.
