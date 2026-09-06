# prove 7: t itself, and the acceptance test that gives this layer its name.
# The suite below runs INSIDE tup: two kernels present (Lean, Rocq), every
# task must verify and every twin must be refuted, or this page, and the
# layer with it, fails. A prove layer that cannot prove is not a layer.
mkdir -p /opt/t
cp -r /tup-build/t-src/. /opt/t/
cd /opt/t
python3 run_all.py
