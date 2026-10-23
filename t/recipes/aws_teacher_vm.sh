#!/bin/bash
# An AWS g5.2xlarge (one A10G, 24 GB) that runs the primed 9B teacher over the second half of the failed training
# problems, beside the laptop's GPU (the user, 2026-10-22: "do we not have aws and google cloud"; AWS session
# restored 14:30Z). Deep Learning AMI (PyTorch 2.7, Ubuntu 22.04) from the SSM parameter, the account's existing
# key pair and security group (dawnr-prove), instance-initiated shutdown = terminate and `shutdown -h +840` from
# user data, so the instance ends itself after 14 h. llama.cpp is built as in t/recipes/v6-gcp-inference-setup.sh
# with CUDA arch 86 (A10G). Files move over plain ssh. On-demand price read 2026-10-22: 1.212 USD an hour.
#   bash t/recipes/aws_teacher_vm.sh create | pull | status | delete
# env: SLICE=out/v9/teacher-ids-aws.txt, REGION=us-east-1, HOURS=14, TYPE=g5.2xlarge
# UNRUN as of 2026-10-23: the account's Free plan refuses every GPU instance type ("not eligible for Free Tier"; only
# t-class, c7i-flex.large and m7i-flex.large launch). Kept for the day the plan changes; nothing here has been exercised
# against a real instance. Bedrock itself works on this account (t/recipes/teacher_bedrock_specs.sh).
set -u
export AWS_PAGER="" PATH=$HOME/.local/bin:$PATH   # the aws CLI lives in ~/.local/bin, which a user unit's PATH lacks
REGION=${REGION:-us-east-1}; TYPE=${TYPE:-g5.2xlarge}; HOURS=${HOURS:-14}; D=$HOME/Projects/dawnr
SLICE=${SLICE:-out/v9/teacher-ids-aws.txt}; KEY=$HOME/.ssh/dawnr-prove.pem; KEYNAME=dawnr-prove; SG=sg-02400b3e84349c796
GGUF=$HOME/.local/share/dawnr/models/Qwen3.5-9B-Q4_K_M.gguf
LOG=$D/out/v9/aws-teacher.log; IDF=$D/out/v9/aws-teacher.id; IPF=$D/out/v9/aws-teacher.ip; KH=$D/out/v9/aws-known-hosts
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o UserKnownHostsFile=$KH -o ConnectTimeout=20"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a $LOG; }
vm() { $SSH ubuntu@$(cat $IPF) "$@"; }
case "${1:-}" in
create)
  cd $D || exit 1; mkdir -p out/v9
  AMI=$(aws ssm get-parameter --region $REGION --name /aws/service/deeplearning/ami/x86_64/oss-nvidia-driver-gpu-pytorch-2.7-ubuntu-22.04/latest/ami-id --query Parameter.Value --output text)
  MYIP=$(curl -s -m 10 https://checkip.amazonaws.com)
  aws ec2 authorize-security-group-ingress --region $REGION --group-id $SG --protocol tcp --port 22 --cidr $MYIP/32 >/dev/null 2>&1 || true
  log "launching $TYPE ($AMI) in $REGION, self-terminating in ${HOURS}h"
  ID=$(aws ec2 run-instances --region $REGION --image-id $AMI --instance-type $TYPE --key-name $KEYNAME --security-group-ids $SG \
    --instance-initiated-shutdown-behavior terminate --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":150,"VolumeType":"gp3","DeleteOnTermination":true}}]' \
    --user-data "#!/bin/bash
shutdown -h +$((HOURS * 60))" --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=dawnr-teacher-$(date -u +%m%d%H%M)}]" \
    --query 'Instances[0].InstanceId' --output text) || { log "run-instances failed"; exit 1; }
  echo $ID > $IDF; log "instance $ID"
  aws ec2 wait instance-running --region $REGION --instance-ids $ID
  aws ec2 describe-instances --region $REGION --instance-ids $ID --query 'Reservations[0].Instances[0].PublicIpAddress' --output text > $IPF
  log "address $(cat $IPF); waiting for ssh"
  for i in $(seq 1 40); do vm true 2>/dev/null && break; sleep 15; done
  vm true || { log "ssh never came up"; exit 1; }
  vm "sudo mkdir -p /opt/dawnr-run && sudo chown ubuntu /opt/dawnr-run && mkdir -p /opt/dawnr-run/evaluation /opt/dawnr-run/inference/models"
  sed 's/-DCMAKE_CUDA_ARCHITECTURES=89/-DCMAKE_CUDA_ARCHITECTURES=86/' t/recipes/v6-gcp-inference-setup.sh > out/v9/aws-setup.sh
  scp -i $KEY -o StrictHostKeyChecking=no -o UserKnownHostsFile=$KH out/v9/aws-setup.sh ubuntu@$(cat $IPF):/opt/dawnr-run/setup.sh
  log "building llama.cpp on the instance (background, CUDA arch 86)"
  vm "cd /opt/dawnr-run && nohup bash setup.sh > setup.log 2>&1 &"
  log "syncing t/ (without t/out), nl/data, t/out/loop, then the 9B GGUF"
  rsync -a --exclude 'out' --exclude '__pycache__' -e "$SSH" $D/t/ ubuntu@$(cat $IPF):/opt/dawnr-run/evaluation/t/ 2>>$LOG || log "t/ rsync returned $?"
  rsync -a -e "$SSH" $D/nl/data/ ubuntu@$(cat $IPF):/opt/dawnr-run/evaluation/nl/data/ 2>>$LOG || log "nl/data rsync returned $?"
  rsync -a -e "$SSH" $D/t/out/loop/ ubuntu@$(cat $IPF):/opt/dawnr-run/evaluation/t/out/loop/ 2>>$LOG || log "t/out/loop rsync returned $?"
  rsync -a --partial -e "$SSH" $GGUF ubuntu@$(cat $IPF):/opt/dawnr-run/inference/models/ 2>>$LOG || log "gguf rsync returned $?"
  log "gguf on the instance: $(vm 'sha256sum /opt/dawnr-run/inference/models/Qwen3.5-9B-Q4_K_M.gguf | cut -c1-16')"
  for i in $(seq 1 120); do vm "test -f /opt/dawnr-run/inference/INFERENCE_READY" 2>/dev/null && break; sleep 30; done
  vm "test -f /opt/dawnr-run/inference/INFERENCE_READY" || { log "llama.cpp build not ready after 60 min; see setup.log on the instance"; exit 1; }
  log "instance ready; starting the teacher chunks on the slice ($(wc -l < $SLICE) problems)"
  vm "mkdir -p /opt/dawnr-run/evaluation/out/v9 /opt/dawnr-run/evaluation/t/out/laptop-runs ~/.local/share/dawnr/models ~/Projects"
  scp -i $KEY -o StrictHostKeyChecking=no -o UserKnownHostsFile=$KH $SLICE ubuntu@$(cat $IPF):/opt/dawnr-run/evaluation/out/v9/teacher-ids-aws.txt
  vm "ln -sfn /opt/dawnr-run/inference/llama.cpp/build/bin ~/.local/share/dawnr/llama.cpp; ln -sfn /opt/dawnr-run/inference/models/Qwen3.5-9B-Q4_K_M.gguf ~/.local/share/dawnr/models/Qwen3.5-9B-Q4_K_M.gguf; ln -sfn /opt/dawnr-run/evaluation ~/Projects/dawnr; cd ~/Projects/dawnr && T_SANDBOX=landlock IDS=out/v9/teacher-ids-aws.txt SERIES=teacher9b-20261022aws PARALLEL=4 CONCURRENCY=4 nohup bash t/recipes/teacher_train_specs.sh > out/v9/teacher-vm.log 2>&1 &"
  log "chunks started on $ID"
  ;;
pull)
  cd $D || exit 1
  rsync -a --include 'teacher9b-*/' --include 'teacher9b-*/kept-specs.jsonl' --include 'teacher9b-*/scored-specs.jsonl' --include 'teacher9b-*/spec_first.json' --exclude '*' \
    -e "$SSH" ubuntu@$(cat $IPF):/opt/dawnr-run/evaluation/t/out/spec-experiment/ $D/t/out/spec-experiment/ 2>>$LOG
  vm "tail -3 /opt/dawnr-run/evaluation/out/v9/teacher.log 2>/dev/null"
  ;;
status)
  vm "tail -2 /opt/dawnr-run/evaluation/out/v9/teacher.log 2>/dev/null; nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader; tail -1 /opt/dawnr-run/setup.log"
  ;;
delete)
  aws ec2 terminate-instances --region $REGION --instance-ids $(cat $IDF) --query 'TerminatingInstances[0].CurrentState.Name' --output text && log "terminated $(cat $IDF)"
  ;;
*) echo "usage: aws_teacher_vm.sh create|pull|status|delete"; exit 2;;
esac
