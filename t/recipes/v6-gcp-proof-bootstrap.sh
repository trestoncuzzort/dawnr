#!/usr/bin/env bash
# Build the pinned seven-prover environment around dawnr's own evaluation source.
# Toolchain recipe: t-proof-engine d13d11d01f8f50687ef645d60aa08c870d664b84/Dockerfile.
# The VM request supplies an eight-hour DELETE deadline and DAWNR_SOURCE_COMMIT.
set -euo pipefail
exec > >(tee -a /var/log/dawnr-proof-setup.log) 2>&1
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends docker.io git curl python3
systemctl enable --now docker
mkdir -p /opt/dawnr-proof/context /opt/dawnr-proof/smoke
chmod 777 /opt/dawnr-proof/smoke
cd /opt/dawnr-proof/context
git init
git remote add origin https://github.com/trestoncuzzort/dawnr.git
git config core.sparseCheckout true
mkdir -p .git/info
cat > .git/info/sparse-checkout <<'PATHS'
/t/*
!/t/*/
/t/verifiers/
/t/lib/
/t/stdlib/
/t/tasks/
/t/nested/
/t/recipes/
PATHS
git fetch --depth 1 --filter=blob:none origin "${DAWNR_SOURCE_COMMIT:?pin the dawnr source commit}"
git checkout --detach FETCH_HEAD
curl -fL --retry 3 -o Dockerfile \
  https://raw.githubusercontent.com/trestoncuzzort/t-proof-engine/d13d11d01f8f50687ef645d60aa08c870d664b84/Dockerfile
echo '1483aad08f6b9ba291e5f1880a057a3c20a9f6f52074e43111d8de215a7f456c  Dockerfile' | sha256sum -c -
printf '.git\n' > .dockerignore
docker build -t dawnr-v6-provers .
docker image inspect dawnr-v6-provers --format '{{.Id}}' > /opt/dawnr-proof/image-id.txt
docker run --rm --network none -e T_MIN_KERNELS=7 -e T_SPARK_JOBS=1 \
  -v /opt/dawnr-proof/smoke:/work --entrypoint sh dawnr-v6-provers -c '
    mkdir /tmp/tasks && cp t/tasks/abs.t t/tasks/gcd.t t/tasks/reverse.t t/tasks/swap_at.t /tmp/tasks/ &&
    python3 t/run_par.py --tasks /tmp/tasks --out /work/artifacts --table /work/kernels.md --jobs 2 --no-cache'
touch /opt/dawnr-proof/PROVERS_READY
