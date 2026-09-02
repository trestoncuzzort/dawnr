# tup layer agent: Node.js
# TUP_TARBALL_arm64=node-v24.20.0-linux-arm64.tar.xz
# TUP_TARBALL_x86_64=node-v24.20.0-linux-x64.tar.xz
#
# THE PREBUILT BINARY, and the honesty that requires. Every other package in
# tup is compiled from source on this machine; Node is not. It is a 100MB C++
# build and taking the official binary saves an hour, but it means this layer
# contains bytes tup did not produce. That is a real weakening of the
# provenance claim and it is recorded rather than glossed: the tarball's
# sha256 is checked against the MANIFEST before use, and the receipt says
# "prebuilt". Building Node from source is a later gate, not a lost cause.

[ -x bin/node ] || { echo "no bin/node here: the driver did not unpack a Node tarball for $TUP_ARCH"; exit 1; }
install -vdm755 /opt
cp -a . /opt/node-v24.20.0
for b in node npm npx; do
  ln -sfv /opt/node-v24.20.0/bin/$b /usr/bin/$b
done
echo "node $(/usr/bin/node --version), npm $(/usr/bin/npm --version)"
