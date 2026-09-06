# train 3: the acceptance test that gives this layer its name: a model
# TRAINS inside tup. Five steps, CPU, the repo's own Dafny corpus. Loss must
# be finite and a checkpoint must exist, or the layer fails. A train layer
# that cannot train is not a layer.
cd /opt/locallm
python3 train.py --data corpus.txt --out /tmp/train-witness \
  --steps 5 --batch-size 4 --block-size 32 2>&1 | tail -5
ls /tmp/train-witness/ | head -3
rm -rf /tmp/train-witness
