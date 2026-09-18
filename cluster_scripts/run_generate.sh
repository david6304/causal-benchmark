#!/usr/bin/env bash
#SBATCH --job-name=causal-gen
#SBATCH --output=logs/slurm-%j.out
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G

# Generation job. Partition and GPU type are NOT set here -- pass them at submit
# time, chosen from live `sinfo`, e.g.
#   sbatch -p ICF-Research --gres=gpu:nvidia_l40s:1 -t 00:30:00 \
#          run_generate.sh --limit 6 --out data/natural_smoke.jsonl
# Anything after the script name is forwarded to generate.py.
set -euo pipefail
source /home/htang2/toolchain-20251006/toolchain.rc
source ~/venvs/causal/bin/activate
cd ~/causal-benchmark

# Weights are prefetched on the head node; fail loudly rather than fall back to
# a network route that may not exist on a compute node.
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

date --iso-8601=seconds
hostname
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
git rev-parse HEAD
git status --short
python -c "import torch, transformers; \
print('torch', torch.__version__, 'transformers', transformers.__version__, \
'cuda', torch.cuda.is_available())"

python -u generate.py "$@"

date --iso-8601=seconds
