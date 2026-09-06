# train 2: locallm, the local learning model, onto the box itself.
mkdir -p /opt/locallm
cp -r /tup-build/locallm-src/. /opt/locallm/
rm -rf /opt/locallm/__pycache__ /opt/locallm/out /opt/locallm/checkpoints 2>/dev/null || true
cd /opt/locallm && python3 -c "import train, data, model_def 2>/dev/null or __import__('train'); print('locallm imports clean')"
