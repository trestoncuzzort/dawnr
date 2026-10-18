#!/usr/bin/env bash
# Ubuntu 24.04 worker for the Dafny and SPARK columns of the v6 comparison.
# Pinned releases/checksums from the engine's Dockerfile and RUN-ON-LINUX.md.
# EC2 must use instance-initiated-shutdown-behavior=terminate.
set -euo pipefail
shutdown -h +240
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y --no-install-recommends python3 curl unzip libicu74 libgomp1 rsync bubblewrap
install -d -o ubuntu -g ubuntu /opt/dawnr
runuser -u ubuntu -- bash <<'PROVERS'
set -euo pipefail
cd "$HOME"
mkdir -p .local/gnatprove
curl -fL --retry 3 -o /tmp/dawnr-dafny.zip \
  https://github.com/dafny-lang/dafny/releases/download/v4.11.0/dafny-4.11.0-x64-ubuntu-22.04.zip
echo 'a46a9ff7cdd720f7955854c78e95df13f4cfe6b80691b05f8654fe19e8267179  /tmp/dawnr-dafny.zip' | sha256sum -c -
unzip -q /tmp/dawnr-dafny.zip -d .local
curl -fL --retry 3 -o /tmp/dawnr-gnatprove.tgz \
  https://github.com/alire-project/GNAT-FSF-builds/releases/download/gnatprove-16.1.0-1/gnatprove-x86_64-linux-16.1.0-1.tar.gz
echo '82528bef29857e239373fcc36732837d743f5a00805d502c70455422ffc97191  /tmp/dawnr-gnatprove.tgz' | sha256sum -c -
tar -xzf /tmp/dawnr-gnatprove.tgz -C .local/gnatprove
{
  .local/dafny/dafny --version
  .local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin/gnatprove --version
} > /opt/dawnr/tool-versions.txt
touch /opt/dawnr/PROVERS_READY
PROVERS
