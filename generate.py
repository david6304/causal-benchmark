"""Write the natural-style passages with a local open-weight model.

Reads the prompts `documents.py` wrote to data/gen_prompts.jsonl and writes
data/natural.jsonl ({"doc_id": ..., "text": ...}), which `documents.py` then
picks up on its next run to build the natural arm of the corpus.

The generator is deliberately not the model under test. A model extracts its own
phrasing more easily than another model's, so using one model for both roles
would make the natural arm optimistic by an amount we cannot bound.

Decoding is greedy. The Gemma 4 card recommends temperature 1.0 / top_p 0.95 /
top_k 64, which is right for open-ended chat and wrong here: the passage is a
fixed set of propositions rendered as prose, and a corpus that changes between
runs cannot be re-generated after a prompt fix. `--temp` is there if greedy
prose turns out to be degenerate, in which case the seed is recorded and the
corpus is still reproducible, just not deterministic across library versions.

Thinking is disabled. Gemma 4 emits a reasoning block by default, which is not
what we want in the document and would have to be stripped post hoc.

Each record carries the model id, the revision it was generated from and the
decoding settings, so a corpus file is self-describing and a silent upstream
reupload cannot quietly change what the documents say.
"""

import json
import random
import sys

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = "google/gemma-4-12B-it"
REVISION = "707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7"   # pinned 2026-09-18
SEED = 0
MAX_NEW_TOKENS = 400     # ~90 words of prose, with room for a long passage
BATCH = 8


def main(limit=None, temp=0.0, out="data/natural.jsonl"):
    random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)

    prompts = [json.loads(line) for line in open("data/gen_prompts.jsonl")]
    if limit:
        prompts = prompts[:limit]
    print(f"{len(prompts)} prompts, model {MODEL} rev {REVISION}", flush=True)

    tok = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
    tok.padding_side = "left"            # batched generation needs left padding
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, revision=REVISION, dtype=torch.bfloat16, device_map="auto")
    model.eval()
    print(f"loaded on {model.device}", flush=True)

    records = []
    for start in range(0, len(prompts), BATCH):
        batch = prompts[start:start + BATCH]
        texts = [tok.apply_chat_template(
            [{"role": "user", "content": p["prompt"]}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False)
            for p in batch]
        enc = tok(texts, return_tensors="pt", padding=True,
                  add_special_tokens=False).to(model.device)
        with torch.no_grad():
            out_ids = model.generate(
                **enc, max_new_tokens=MAX_NEW_TOKENS,
                do_sample=temp > 0, temperature=temp if temp > 0 else None,
                pad_token_id=tok.pad_token_id if tok.pad_token_id
                is not None else tok.eos_token_id)
        for p, ids in zip(batch, out_ids):
            text = tok.decode(ids[enc["input_ids"].shape[1]:],
                              skip_special_tokens=True).strip()
            records.append({"doc_id": p["doc_id"], "text": text,
                            "model": MODEL, "revision": REVISION,
                            "temp": temp, "seed": SEED})
        print(f"{len(records)}/{len(prompts)}", flush=True)

    with open(out, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    words = [len(r["text"].split()) for r in records]
    print(f"\n{len(records)} passages -> {out}")
    print(f"words: min {min(words)} mean {sum(words) / len(words):.0f} "
          f"max {max(words)}")
    empty = [r["doc_id"] for r in records if not r["text"]]
    if empty:
        print(f"EMPTY: {len(empty)} passages came back blank")


if __name__ == "__main__":
    a = sys.argv
    main(limit=int(a[a.index("--limit") + 1]) if "--limit" in a else None,
         temp=float(a[a.index("--temp") + 1]) if "--temp" in a else 0.0,
         out=a[a.index("--out") + 1] if "--out" in a else "data/natural.jsonl")
