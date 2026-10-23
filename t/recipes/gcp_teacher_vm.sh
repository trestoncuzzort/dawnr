#!/bin/bash
# A Google Cloud L4 VM that runs the primed 9B teacher over a slice of the failed training problems, beside the
# laptop's GPU (the user, 2026-10-22: "do we not have aws and google cloud"). The project is the active account's
# own billed one (GPU quota: one L4 per region); the zone, image and self-delete pattern follow the v6 training VM
# of 2026-10-17 (~/scratch/gcp-v6/instance-request.json); llama.cpp is built as in t/recipes/v6-gcp-inference-setup.sh
# (pinned commit, CUDA arch 89 = L4). The VM deletes itself after TERMINATE_HOURS. Files move over plain ssh to the
# VM's address with the key gcloud registers on first contact (the gcloud CLI itself is slow here).
#   bash t/recipes/gcp_teacher_vm.sh create     # create, build, sync the repo slice and the 9B GGUF, start the chunks
#   bash t/recipes/gcp_teacher_vm.sh pull       # fetch finished chunks' kept files (idempotent)
#   bash t/recipes/gcp_teacher_vm.sh status | delete
# env: SLICE=out/v9/teacher-ids-gcp.txt, TERMINATE_HOURS=14, ZONE=us-central1-a, PROJECT
# UNRUN as of 2026-10-23: the active account's project carries a global GPU quota of 0 (an increase was denied on
# 2026-10-18 and the daily request quota is spent) and the project that ran v6 needs another account's login. Kept for
# the day one of those changes; nothing here has been exercised against a real VM.
set -u
G=$HOME/google-cloud-sdk/bin/gcloud; PROJECT=${PROJECT:-project-3d8cc36f-7446-43a0-910}; ZONE=${ZONE:-us-central1-a}
TERMINATE_HOURS=${TERMINATE_HOURS:-14}; D=$HOME/Projects/dawnr; SLICE=${SLICE:-out/v9/teacher-ids-gcp.txt}
GGUF=$HOME/.local/share/dawnr/models/Qwen3.5-9B-Q4_K_M.gguf
IMAGE=projects/deeplearning-platform-release/global/images/pytorch-2-9-cu129-ubuntu-2204-nvidia-580-v20261001
LOG=$D/out/v9/gcp-teacher.log; STATE=$D/out/v9/gcp-teacher.name; IPF=$D/out/v9/gcp-teacher.ip
KEY=$HOME/.ssh/google_compute_engine; KH=$D/out/v9/gcp-known-hosts
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o UserKnownHostsFile=$KH -o ConnectTimeout=20"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a $LOG; }
vm() { $SSH t@$(cat $IPF) "$@"; }
case "${1:-}" in
create)
  cd $D || exit 1; mkdir -p out/v9
  NAME=${NAME:-dawnr-teacher-$(date -u +%m%d%H%M)}
  log "creating $NAME in $PROJECT/$ZONE (g2-standard-8, one L4, self-delete in ${TERMINATE_HOURS}h)"
  $G compute instances create $NAME --project $PROJECT --zone $ZONE --machine-type g2-standard-8 \
    --accelerator type=nvidia-l4,count=1 --maintenance-policy TERMINATE --no-restart-on-failure \
    --boot-disk-size 150GB --boot-disk-type pd-balanced --image $IMAGE \
    --instance-termination-action DELETE --max-run-duration ${TERMINATE_HOURS}h \
    --metadata install-nvidia-driver=True --quiet >> $LOG 2>&1 || { log "create failed"; exit 1; }
  echo $NAME > $STATE
  $G compute instances describe $NAME --project $PROJECT --zone $ZONE --format 'value(networkInterfaces[0].accessConfigs[0].natIP)' > $IPF 2>>$LOG
  log "address $(cat $IPF); registering the ssh key"
  for i in $(seq 1 40); do $G compute ssh $NAME --project $PROJECT --zone $ZONE --quiet --command true >> $LOG 2>&1 && break; sleep 15; done
  vm true || { log "ssh never came up"; exit 1; }
  vm "sudo mkdir -p /opt/dawnr-run && sudo chown \$USER /opt/dawnr-run && mkdir -p /opt/dawnr-run/evaluation /opt/dawnr-run/inference/models"
  log "building llama.cpp on the VM (background)"
  scp -i $KEY -o StrictHostKeyChecking=no -o UserKnownHostsFile=$KH t/recipes/v6-gcp-inference-setup.sh t@$(cat $IPF):/opt/dawnr-run/setup.sh
  vm "cd /opt/dawnr-run && nohup bash setup.sh > setup.log 2>&1 &"
  log "syncing t/ (without t/out), nl/data, t/out/loop, then the 9B GGUF"
  rsync -a --exclude 'out' --exclude '__pycache__' -e "$SSH" $D/t/ t@$(cat $IPF):/opt/dawnr-run/evaluation/t/ 2>>$LOG || log "t/ rsync returned $?"
  rsync -a -e "$SSH" $D/nl/data/ t@$(cat $IPF):/opt/dawnr-run/evaluation/nl/data/ 2>>$LOG || log "nl/data rsync returned $?"
  rsync -a -e "$SSH" $D/t/out/loop/ t@$(cat $IPF):/opt/dawnr-run/evaluation/t/out/loop/ 2>>$LOG || log "t/out/loop rsync returned $?"
  rsync -a --partial -e "$SSH" $GGUF t@$(cat $IPF):/opt/dawnr-run/inference/models/ 2>>$LOG || log "gguf rsync returned $?"
  log "gguf on the VM: $(vm 'sha256sum /opt/dawnr-run/inference/models/Qwen3.5-9B-Q4_K_M.gguf | cut -c1-16')"
  for i in $(seq 1 120); do vm "test -f /opt/dawnr-run/inference/INFERENCE_READY" 2>/dev/null && break; sleep 30; done
  vm "test -f /opt/dawnr-run/inference/INFERENCE_READY" || { log "llama.cpp build not ready after 60 min; see setup.log on the VM"; exit 1; }
  log "VM ready; starting the teacher chunks on the slice ($(wc -l < $SLICE) problems)"
  vm "mkdir -p /opt/dawnr-run/evaluation/out/v9 /opt/dawnr-run/evaluation/t/out/laptop-runs ~/.local/share/dawnr/models ~/Projects"
  scp -i $KEY -o StrictHostKeyChecking=no -o UserKnownHostsFile=$KH $SLICE t@$(cat $IPF):/opt/dawnr-run/evaluation/out/v9/teacher-ids.txt
  vm "ln -sfn /opt/dawnr-run/inference/llama.cpp/build/bin ~/.local/share/dawnr/llama.cpp; ln -sfn /opt/dawnr-run/inference/models/Qwen3.5-9B-Q4_K_M.gguf ~/.local/share/dawnr/models/Qwen3.5-9B-Q4_K_M.gguf; ln -sfn /opt/dawnr-run/evaluation ~/Projects/dawnr; cd ~/Projects/dawnr && T_SANDBOX=landlock CHUNK=100 nohup bash t/recipes/teacher_train_specs.sh > out/v9/teacher-vm.log 2>&1 &"
  log "chunks started on $NAME"
  ;;
pull)
  cd $D || exit 1
  rsync -a --include 'teacher9b-*/' --include 'teacher9b-*/kept-specs.jsonl' --include 'teacher9b-*/scored-specs.jsonl' --include 'teacher9b-*/spec_first.json' --exclude '*' \
    -e "$SSH" t@$(cat $IPF):/opt/dawnr-run/evaluation/t/out/spec-experiment/ $D/t/out/spec-experiment/ 2>>$LOG
  vm "tail -3 /opt/dawnr-run/evaluation/out/v9/teacher.log 2>/dev/null"
  ;;
status)
  vm "tail -2 /opt/dawnr-run/evaluation/out/v9/teacher.log 2>/dev/null; nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader; tail -1 /opt/dawnr-run/setup.log"
  ;;
delete)
  NAME=$(cat $STATE); $G compute instances delete $NAME --project $PROJECT --zone $ZONE --quiet && log "deleted $NAME"
  ;;
*) echo "usage: gcp_teacher_vm.sh create|pull|status|delete"; exit 2;;
esac
