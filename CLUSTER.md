# ICF Cluster Guide

Operational guidance for this repository. Cluster availability and hardware
change: verify live state before relying on dated observations.

`ssh icf-ra` reaches the head node (`hastings.inf.ed.ac.uk`) as the RA account
`dmurra4`, via the `staff-gw` jump host. The shorter `ssh icf` alias is retained
and resolves to the same account. The student account `s2296274` and its home
directory are unrelated to this project and are not used here. Select resources
by Slurm partition, not by SSH alias.

## Access Baseline

Last checked 2026-09-18, account `dmurra4`, Slurm account `research`, QOS
`research`, MaxJobs 20:

- `sbatch --test-only` accepted a GPU request on `Interactive`, `Teaching`,
  `ICF-Free`, `ICF-Research` and `Open-Research`;
- `ICF-Research` and `Open-Research` estimated immediate starts, `ICF-Free`
  about two hours out, `Teaching` over a day — the research partitions are the
  ones this account should normally use;
- `anc_nodes` exists but is a group partition and was not tested;
- direct tiny `sbatch --test-only` checks remain more reliable than inferred
  account/QOS listings.

Recheck before a consequential run:

```bash
sinfo -o "%.22P %.6a %.12l %.6D %.6t %N"
squeue -p ICF-Research,ICF-Free,Open-Research
```

Do not infer current access from this document alone.

## Connect And Activate

```bash
ssh icf-ra
source /home/htang2/toolchain-20251006/toolchain.rc
source ~/venvs/causal/bin/activate
```

The local `~/.ssh/config` sets `ControlMaster auto` with an 8h `ControlPersist`
on the RA aliases and `staff-gw`. One interactive connection opens the master
socket; subsequent non-interactive commands reuse it without re-authenticating,
which is what lets an agent run read-only checks.

There is no `conda` and no `module` system on the cluster, so the project uses
`venv` there even though local development uses conda. The head node's system
Python is 3.12.3. `toolchain.rc` prepends its own `bin` and a CUDA 12.8
toolchain to `PATH`/`LD_LIBRARY_PATH`; it does not provide a Python. Install
packages on the head node, which has internet; compute nodes may not.

The canonical repository is now
`https://github.com/david6304/causal-benchmark.git`, branch `master`. For a new
cluster checkout:

```bash
git clone https://github.com/david6304/causal-benchmark.git ~/causal-benchmark
```

The checkout created before the repository was published has no remote. Add it
once, after checking that no local or untracked work would be overwritten:

```bash
cd ~/causal-benchmark
git status --short
git remote add origin https://github.com/david6304/causal-benchmark.git
git fetch origin
```

For each reportable run, synchronise and use an explicit commit:

```bash
cd ~/causal-benchmark
git fetch origin
git checkout <COMMIT>
git status --short
```

Do not run reportable work from an unidentified or dirty checkout.

## Partition Selection

Observed 2026-09-18. VRAM figures are the cards' nominal sizes, not measured.

| Partition | Time limit | GPUs present |
| --- | --- | --- |
| `Interactive` | 4 hours | 2080 Ti 11 GB (`landonia01-02`) |
| `Teaching` | 2 days | mostly 2080 Ti 11 GB; `saxa` H200 MIG slices; many nodes drained |
| `ICF-Free` | 2 days | A40 48 GB (`crannog`), L40S 48 GB (`scotia`), H200 141 GB (`herman`), `saxa` MIG slices, 2080 Ti, A6000 48 GB (`landonia11`, drained) |
| `ICF-Research` | 2 days | H200 141 GB (`herman`), L40S 48 GB (`scotia`), RTX PRO 6000 Blackwell 96 GB (`schoeman`, `sole`) |
| `Open-Research` | 2 days | A40 48 GB (`crannog`) |

Exact GRES names, which is what `--gres` must match:

```
gpu:nvidia_geforce_rtx_2080_ti   11 GB
gpu:a40                          48 GB
gpu:nvidia_l40s                  48 GB
gpu:nvidia_rtx_a6000             48 GB
gpu:nvidia_rtx_pro_6000_blackwell_server_edition   96 GB
gpu:nvidia_h200                 141 GB   (herman)
gpu:h200 / gpu:h200_3g.71gb / gpu:h200_1g.18gb     (saxa, MIG-partitioned)
```

Examples:

```bash
# Short interactive validation
srun -p Interactive --gres=gpu:1 --time=00:30:00 --pty bash

# Single 48 GB GPU for the current Gemma-4-12B bf16 generation
sbatch -p ICF-Research --gres=gpu:nvidia_l40s:1 --time=02:00:00 run.sh

# A MIG slice instead of a whole H200, when the job does not need the card
sbatch -p ICF-Free --gres=gpu:h200_3g.71gb:1 --time=02:00:00 run.sh
```

Never request bare `--gres=gpu:1` on a heterogeneous partition when the job has
a known VRAM minimum: `ICF-Free` spans 11 GB to 141 GB. Inspect live GRES names
and request a capable device. Prefer the smallest card that fits — taking an
H200 or a Blackwell for a job a 48 GB L40S would run is the main way to be a bad
citizen here. Request multiple GPUs only when the code is explicitly multi-GPU.

## GPU Selection Workflow

Choose resources from live evidence immediately before submission. `sinfo`
shows advertised hardware and node state, while `squeue` shows current demand;
neither reliably predicts a job's start time. Compare eligible requests with
`sbatch --test-only`, which asks the scheduler for its current estimated start.

`--test-only` reports the priority-ordered estimate and **ignores backfill**, so
it is a pessimistic upper bound, sometimes days out even when capable GPUs sit
idle. Do not read it as "no GPUs". Find physically-free devices from `sinfo`
(advertised `gres` minus `gresused`); a short, small, resumable job submitted
against idle capacity usually backfills in within minutes. Keep wall-time short
and watch the `squeue` REASON column rather than waiting on the estimate.

1. Define the job contract before checking availability:

   - minimum safe VRAM and acceptable GPU models;
   - CPUs, host memory, and one versus multiple GPUs;
   - a measured or conservative wall-time request;
   - whether the output can resume safely after timeout or interruption.

2. Inspect live resources and queues:

   ```bash
   sinfo -N -O partition:16,nodelist:14,statecompact:8,gres:42,gresused:42,memory:9,cpus:6

   squeue -p ICF-Research,ICF-Free,Open-Research \
     -o "%.10i %.14P %.18j %.8u %.2t %.10M %.10l %.4D %R"
   ```

3. Exclude GPU types below the job's measured or justified VRAM requirement.
   Do not choose a smaller GPU only because its queue appears shorter.

4. Run one non-submitting scheduler estimate for each eligible target:

   ```bash
   sbatch --test-only \
     --partition=<PARTITION> \
     --gres=gpu:<GRES_NAME>:1 \
     --time=<WALL_TIME> \
     scripts/<JOB_SCRIPT>
   ```

5. Compare the estimated starts, then submit exactly one request. Do not leave
   competing jobs that write to the same output path. Cancel the old pending
   job before switching targets, or give the alternative job a distinct output
   path when an intentional comparison requires both.

6. Monitor the selected job:

   ```bash
   squeue -j <JOB_ID> -o "%.18i %.14P %.18j %.2t %.10M %.10l %.4D %R"
   tail -f <SLURM_OUTPUT>
   ```

7. Record actual resource use after the job leaves the queue:

   ```bash
   sacct -j <JOB_ID> \
     --format=JobID,Partition,State,Elapsed,Timelimit,AllocTRES,MaxRSS,ExitCode
   ```

Use measured elapsed time, peak memory, failures, and resume behaviour to
tighten the next request. An agent may interpret the live outputs and recommend
one exact command, but submission requires explicit user authorisation for that
target and action.

## Storage And Model Caches

| Location | Use |
| --- | --- |
| `/home/dmurra4` | persistent checkout, venvs, small metadata; Lustre, no quota set as of 2026-09-18 |
| `~/.cache/huggingface` | Hugging Face cache (default; do NOT set `HF_HOME`) |
| `/disk/scratch/$USER` | node-local, fast, ephemeral; create it inside the job and treat it as disposable |

- Keep irreplaceable metadata on persistent storage.
- On `landonia01` (2026-09-18) `/disk/scratch` is a symlink to
  `/disk/scratch_big`, 9.1 TB with 8.0 TB free, and `/disk/scratch/$USER` did
  not exist until the job created it. Capacity and backing filesystem may differ
  on other nodes. Scratch is node-local either way, so a path written by one job
  is not visible to a job that lands elsewhere.
- Home is Lustre and handles large sequential files far better than thousands of
  tiny ones; prefer one archive or shard.
- Do not commit model weights, gated datasets, or generated corpora.

Compute nodes are intended to be offline. In practice one short allocation on
`landonia01` (2026-09-18) did reach `huggingface.co`, apparently through an HTTP
proxy, with no proxy variables set on the head node. Do not rely on it: prefetch
every required model and dataset on the head node before submitting a job, and
set the offline flags so a job fails loudly rather than silently depending on a
route that may not be there next time. Set offline flags in compute jobs:

```bash
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
```

An offline smoke test should load the exact pinned model/tokenizer from cache
before a long run is submitted. Export the same offline flags the batch job uses
when running it: a pilot on the head node without them silently passes on live
API calls (e.g. `list_repo_files`) that the offline batch job then fails on.

For model-backed jobs, the preflight must exercise the same loading and input
preparation path as the production command: load the exact tokenizer and model
class from the pinned local cache, format one real input, and run the smallest
meaningful forward pass or one-token generation. A config-only or tokenizer-only
check is not sufficient to establish checkpoint compatibility, CUDA
availability, or memory fit.

## Job Script Contract

A cluster job should:

- use `set -euo pipefail`;
- activate the toolchain and venv;
- change to the repository checkout explicitly;
- print hostname, timestamp, commit, dirty status, command, and versions;
- accept config, output path, and resource-sensitive values as arguments;
- write to a unique run directory;
- checkpoint or append atomically when practical;
- emit periodic progress to the Slurm output for long-running work
  (completed/total, failures, elapsed, rate or ETA), with output buffering
  disabled when necessary;
- log before and after long blocking stages such as model loading and first
  generation, with a simple heartbeat when a stage may stay silent;
- fail early if required caches or inputs are absent.

Minimal shape:

```bash
#!/usr/bin/env bash
set -euo pipefail

source /home/htang2/toolchain-20251006/toolchain.rc
source ~/venvs/causal/bin/activate
cd ~/causal-benchmark

export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1

date --iso-8601=seconds
hostname
git rev-parse HEAD
git status --short

python <entrypoint> --model <model> --out <unique-run-dir>
```

Do not edit a script body for each run when the value belongs in a
command-line argument.

## Preflight Before Submission

Validate locally or in a short interactive allocation:

1. targeted tests and Ruff checks when the milestone contains Python;
2. entrypoint `--help` when an entrypoint exists;
3. argument parsing and path validation;
4. offline model/tokenizer loading;
5. a tiny end-to-end or dry run;
6. output metadata and resume behaviour;
7. the exact rendered `sbatch` command.

The cluster is not the first-pass debugger. A GPU-only step may remain, but
imports, arguments, paths, data shape and failure messages should be checked
locally or on the head node first. Request a GPU only for checks that genuinely
require CUDA.

## Monitoring

```bash
squeue -u "$USER"
tail -f slurm-<JOB_ID>.out
scancel <JOB_ID>
```

For GPU utilisation inside an allocation:

```bash
srun --jobid=<JOB_ID> --overlap nvidia-smi \
  --query-gpu=timestamp,name,utilization.gpu,memory.used,memory.total \
  --format=csv -l 5
```

Tune batch size from a small measured pilot for the exact model, sequence
length and precision. Historical measurements from a different experiment are
not defaults.

## Results And Recovery

- Write exploratory and reportable runs to distinct run directories.
- Copy required outputs off node-local scratch before job expiry.
- Preserve run metadata even when large artifacts remain on the cluster.
- Do not push generated outputs indiscriminately; commit only compact,
  explicitly selected artifacts.
- Long jobs must checkpoint often enough to recover within the partition time
  limit.

## Common Failures

- **No CUDA:** confirm `toolchain.rc` is sourced and the shell is inside a GPU
  allocation.
- **Pending job:** inspect `squeue` reason and current partition/node state;
  many `Teaching` and `landonia` nodes are drained.
- **Out of memory:** reduce batch/sequence size or request a GPU meeting the
  measured VRAM requirement.
- **Offline hang:** confirm all dependencies are cached and offline environment
  variables are set.
- **Timeout:** resume from a validated checkpoint rather than overwriting the
  prior run.

## Open Items

- The toolchain lives in another user's home (`/home/htang2`). It works today;
  it is not ours and could vanish.
- `~/venvs/causal` uses Python 3.12.3. The current generation path requires
  `torch`, `transformers` and `accelerate`; after installing or upgrading them,
  verify imports and CUDA in a short allocation before relying on it.
- `google/gemma-4-12B-it` was not yet present in the RA account's Hugging Face
  cache on 2026-09-18. Prefetch it on the head node and pin the resolved model
  revision before the first reportable generation.
