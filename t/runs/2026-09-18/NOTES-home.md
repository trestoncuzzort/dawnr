- 2026-09-18 02:42 start `apps`: `for S in 1 2; do T=qwen2.5-coder-14b-apps-s$S; D=t/out/spec-experiment/$T; [ -d $D/grade-in ] && continue; TEMP=0.7; [ $S = 1 ] && TEMP=0; python3 t/spec_experiment.py generate --model qwen2.5-coder:14b --tag $T --pool v5 --min-id 200000 --prompt v3 --seed $S --temperature $TEMP --num-ctx 8192 --num-predict 2048 --timeout 1800 --jobs 4 && python3 t/spec_experiment.py extract --model $T --pool v5 && python3 t/spec_experiment.py tests --model $T --pool v5 && python3 t/pool_pick.py $D --control 25 || exit 1; done && T=deepseek-coder-v2-16b-apps-s1; D=t/out/spec-experiment/$T; [ -d $D/grade-in ] || { python3 t/spec_experiment.py generate --model deepseek-coder-v2:16b --tag $T --pool v5 --min-id 200000 --prompt v3 --seed 1 --temperature 0 --num-ctx 6144 --num-predict 2048 --timeout 1800 --jobs 2 && python3 t/spec_experiment.py extract --model $T --pool v5 && python3 t/spec_experiment.py tests --model $T --pool v5 && python3 t/pool_pick.py $D --control 25; }` (log `logs/apps.log`)
- 2026-09-18 02:53 end `apps`: exit 1 after 10 min
- 2026-09-18 03:26 start `apps`: `for S in 1 2; do T=qwen2.5-coder-14b-apps-s$S; D=t/out/spec-experiment/$T; [ -d $D/grade-in ] && continue; TEMP=0.7; [ $S = 1 ] && TEMP=0; python3 t/spec_experiment.py generate --model qwen2.5-coder:14b --tag $T --pool v5 --min-id 200000 --prompt v3 --seed $S --temperature $TEMP --num-ctx 8192 --num-predict 2048 --timeout 1800 --jobs 4 && python3 t/spec_experiment.py extract --model $T --pool v5 && python3 t/spec_experiment.py tests --model $T --pool v5 && python3 t/pool_pick.py $D --control 25 || exit 1; done && T=deepseek-coder-v2-16b-apps-s1; D=t/out/spec-experiment/$T; [ -d $D/grade-in ] || { python3 t/spec_experiment.py generate --model deepseek-coder-v2:16b --tag $T --pool v5 --min-id 200000 --prompt v3 --seed 1 --temperature 0 --num-ctx 6144 --num-predict 2048 --timeout 1800 --jobs 2 && python3 t/spec_experiment.py extract --model $T --pool v5 && python3 t/spec_experiment.py tests --model $T --pool v5 && python3 t/pool_pick.py $D --control 25; }` (log `logs/apps.log`)
- 2026-09-18 04:36 start `apps-grade`: `bash t/grade_lab.sh tags qwen2.5-coder-14b-apps-s1 qwen2.5-coder-14b-apps-s2 deepseek-coder-v2-16b-apps-s1` (log `logs/apps-grade.log`)
- 2026-09-18 04:51 start `grade`: `bash t/grade_lab.sh pending` (log `logs/grade.log`)
- 2026-09-18 05:39 start `apps`: `for S in 1 2; do T=qwen2.5-coder-14b-apps-s$S; D=t/out/spec-experiment/$T; [ -d $D/grade-in ] && continue; TEMP=0.7; [ $S = 1 ] && TEMP=0; python3 t/spec_experiment.py generate --model qwen2.5-coder:14b --tag $T --pool v5 --min-id 200000 --prompt v3 --seed $S --temperature $TEMP --num-ctx 8192 --num-predict 2048 --timeout 1800 --jobs 4 && python3 t/spec_experiment.py extract --model $T --pool v5 && python3 t/spec_experiment.py tests --model $T --pool v5 && python3 t/pool_pick.py $D --control 25 || exit 1; done && T=deepseek-coder-v2-16b-apps-s1; D=t/out/spec-experiment/$T; [ -d $D/grade-in ] || { python3 t/spec_experiment.py generate --model deepseek-coder-v2:16b --tag $T --pool v5 --min-id 200000 --prompt v3 --seed 1 --temperature 0 --num-ctx 6144 --num-predict 2048 --timeout 1800 --jobs 2 && python3 t/spec_experiment.py extract --model $T --pool v5 && python3 t/spec_experiment.py tests --model $T --pool v5 && python3 t/pool_pick.py $D --control 25; }` (log `logs/apps.log`)
- 2026-09-18 05:39 stopped `apps` by hand
- 2026-09-18 05:39 end `apps`: exit -15 after 0 min
- 2026-09-18 05:39 start `r5-pool`: `python3 t/loop_dataset.py --from-samples $(cd t/out/spec-experiment && ls -d qwen3.8-27b-fp8 qwen3.8-27b-fp8-v3 qwen3.8-27b-fp8-v3-s2 qwen2.5-coder-14b-* deepseek-coder-v2-16b-* 2>/dev/null) student-r4-train locallm-r4-train --split t/out/loop/split-v4.json --min-kernels 7 --out-suffix r5 && wc -l t/out/loop/sft-r5.jsonl t/out/loop/pairs-r5.jsonl` (log `logs/r5-pool.log`)
- 2026-09-18 05:39 stopped `grade` by hand
- 2026-09-18 05:39 end `r5-pool`: exit 0 after 0 min
- 2026-09-18 05:40 start `r5-locallm`: `python3 t/loop_locallm.py corpus --base t/runs/2026-09-16/loop-data/corpus.txt --sft t/out/loop/sft-r5.jsonl --out t/out/loop-locallm/corpus-r5.txt && ~/.venv-t/bin/python t/loop_locallm.py train --corpus t/out/loop-locallm/corpus-r5.txt --model t/out/loop-locallm/model-r5 --layers 8 --width 512 --steps 6000 && ~/.venv-t/bin/python t/loop_locallm.py generate --model t/out/loop-locallm/model-r5 --tag locallm-r5` (log `logs/r5-locallm.log`)
- 2026-09-18 05:40 end `r5-locallm`: exit 1 after 0 min
- 2026-09-18 05:42 start `r5-locallm`: `python3 t/loop_locallm.py corpus --base t/runs/2026-09-16/loop-data/corpus.txt --sft t/out/loop/sft-r5.jsonl --out t/out/loop-locallm/corpus-r5.txt && ~/.venv-t/bin/python t/loop_locallm.py train --corpus t/out/loop-locallm/corpus-r5.txt --model t/out/loop-locallm/model-r5 --layers 8 --width 512 --heads 8 --steps 6000 && ~/.venv-t/bin/python t/loop_locallm.py generate --model t/out/loop-locallm/model-r5 --tag locallm-r5` (log `logs/r5-locallm.log`)
- 2026-09-18 05:44 lab GPUs: stop
- 2026-09-18 05:44 lab GPUs: fetch
- 2026-09-18 05:44 stopped `r5-locallm` by hand
- 2026-09-18 05:44 end `r5-locallm`: exit -15 after 1 min
- 2026-09-18 05:44 start `r5-locallm`: `python3 t/loop_locallm.py corpus --base t/runs/2026-09-16/loop-data/corpus.txt --sft t/out/loop/sft-r5.jsonl --out t/out/loop-locallm/corpus-r5.txt && ~/.venv-t/bin/python t/loop_locallm.py train --corpus t/out/loop-locallm/corpus-r5.txt --model t/out/loop-locallm/model-r5 --layers 8 --width 512 --heads 8 --steps 6000 && ~/.venv-t/bin/python t/loop_locallm.py generate --model t/out/loop-locallm/model-r5 --tag locallm-r5` (log `logs/r5-locallm.log`)
- 2026-09-18 05:45 stopped `r5-locallm` by hand
- 2026-09-18 05:45 end `r5-locallm`: exit -15 after 0 min
- 2026-09-18 05:45 start `r5-locallm`: `python3 t/loop_locallm.py corpus --base t/runs/2026-09-16/loop-data/corpus.txt --sft t/out/loop/sft-r5.jsonl --out t/out/loop-locallm/corpus-r5.txt && ~/.venv-t/bin/python t/loop_locallm.py train --corpus t/out/loop-locallm/corpus-r5.txt --model t/out/loop-locallm/model-r5 --layers 8 --width 512 --heads 8 --steps 6000 && ~/.venv-t/bin/python t/loop_locallm.py generate --model t/out/loop-locallm/model-r5 --tag locallm-r5` (log `logs/r5-locallm.log`)
- 2026-09-18 05:54 run_everything: started (growth plan: repairs, HumanEval problems, a second generator)
- 2026-09-18 05:54 run_everything: Phi-4-mini answers starting (the model to beat)

## Round 5's two arms did not see quite the same pool (2026-09-18, 06:2x)

locallm-r5 trained on the corpus built at 05:52 from an 87-row `sft-r5` as it
stood then: 82 rows, seed 1's 16 clean APPS answers included, seed 2's 7 not,
because seed 2 was still being graded on the lab workstation. The pool was
rebuilt at 06:2x with seed 2's verdicts (87 rows) and the student's training
(`r5-train`) started after that, so the student saw five answers locallm did
not. Small, and recorded rather than smoothed over: a comparison between the
two arms of this round carries that difference, and round 6 rebuilds both from
one pool.
- 2026-09-18 15:29 start `grammar`: `L=$(grep '^T_LAB=' t/lab-workstation.conf | cut -d= -f2) && ssh -o BatchMode=yes $L "cd ~/tup && git fetch -q origin && git reset -q --hard origin/main && ~/.venv-vllm/bin/python t/grammar_check.py --refused 600" | tee t/out/grammar-check.txt` (log `logs/grammar.log`)
- 2026-09-18 15:29 end `grammar`: exit 0 after 0 min
- 2026-09-18 22:45 run_everything: start `grade` (Grade what is ungraded), attempt 1
- 2026-09-18 22:45 run_everything: end `grade`: exit 0, ok
- 2026-09-18 22:45 run_everything: finished
