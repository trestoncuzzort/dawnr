# prove 1: Lean 4.33.1 — the official release binary, verbatim.
# The one prebuilt thing in this layer, and it says so: kernel-checked proof
# terms are the point of Lean, and the binary's hash is pinned in MANIFEST.
case "$(uname -m)" in
  aarch64) LEAN=lean-4.33.1-linux_aarch64 ;;
  x86_64)  LEAN=lean-4.33.1-linux ;;
  *) echo "no Lean release for $(uname -m)"; exit 1 ;;
esac
mkdir -p /opt
tar --zstd -xf /sources/$LEAN.tar.zst -C /opt
mv /opt/$LEAN /opt/lean-4.33.1
ln -sfv /opt/lean-4.33.1/bin/lean /usr/bin/lean
ln -sfv /opt/lean-4.33.1/bin/lake /usr/bin/lake
lean --version
