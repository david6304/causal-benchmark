"""Edge discovery: give a model the concepts and the document, score the graph.

Everything except the model call, so it can be checked offline. `--fake` swaps
in a synthetic prediction to exercise the whole path: `truth` gives SHD 0
everywhere, `empty` and `transpose` both give SHD = number of edges, and `bait`
takes every retracted claim at face value, which should drive injected-pair FP to
100%. `-k` sets the number of samples per item.

Scoring. SHD is defined pairwise: for each unordered pair {i, j} the relationship
is one of none / i->j / j->i, and SHD counts the pairs where prediction and truth
disagree. A reversed edge therefore costs 1, not 2.

The pilot's primary metric is instead **injected-pair FP** -- whether the model
asserts an edge on the one pair carrying a retracted claim. SHD and exact match
are whole-graph scores, so they dilute a single-pair manipulation by C(n,2). The
`bait` mode shows the size of that: a predictor that takes every bait still
reads exact-match 20/38 and mean SHD 0.474 over the corpus, against 18/18 on the
targeted metric.

TODO: add edge P/R/F1 and per-pair accuracy on shortcut_pairs.

The prompt departs from iTAG's discovery prompt in two ways. Theirs carries a
worked example (temperature / drownings / ice cream) which is a fork, one of the
six atoms, so it is dropped rather than priming the structure we measure. And
theirs asks for relationships "based on the text and common sense reasoning",
which invites exactly the priors we are trying to exclude.

The prompt below is the short form. A longer variant carrying two extra guards --
a directness clause ("a relationship holding only through another concept does
not count") and a closed-world clause ("use only the document, not outside
knowledge") -- was raced against it on the n=3 chain and on two n=4 atoms with
mediated pairs (`n4_16`, `n4_23`). Both recovered every graph exactly, so the
guards bought nothing and the short form was kept. One sample per cell on Haiku,
so this is a smoke test rather than a measurement.

That result does not show the guards are useless, only that no-noise fictional
items do not discriminate. The closed-world clause is inert here by construction:
there is no outside knowledge about zorbium to suppress. It should be re-raced
when the plausible arm exists, where over-extraction from priors is the failure
being looked for, and again once documents carry noise or run long.
"""

import json
import sys

PROMPT = """Concepts:
{concepts}

Document:
{text}

Reply with only JSON: {{"adjacency": A}}, a {n}x{n} array where A[i][j] = 1 if \
the document says concept i causes concept j."""


def build_prompt(r):
    concepts = "\n".join(f"{i}. {c}" for i, c in enumerate(r["concepts"]))
    return PROMPT.format(concepts=concepts, text=r["text"],
                         n=len(r["concepts"]))


def parse(raw, n):
    """Model text -> n x n adjacency, or None if it cannot be read.

    Parse failure is a result, not an error: small open models will fail to
    produce JSON some fraction of the time and that rate is worth reporting.
    """
    s = raw.strip()
    if "```" in s:                      # strip a markdown fence if present
        s = s.split("```")[1].removeprefix("json").strip()
    try:
        A = json.loads(s[s.index("{"):s.rindex("}") + 1])["adjacency"]
    except Exception:
        return None
    if len(A) != n or any(len(row) != n for row in A):
        return None
    if any(v not in (0, 1) for row in A for v in row):
        return None
    return A


def shd(pred, true):
    """Pairwise structural Hamming distance; a reversal costs 1."""
    n = len(true)
    return sum((pred[i][j], pred[j][i]) != (true[i][j], true[j][i])
               for i in range(n) for j in range(i + 1, n))


def injected_hit(pred, injected):
    """Did the model put an edge on the pair carrying the retracted claim?

    The pilot's primary metric, in preference to SHD or exact match. The
    manipulation touches exactly one pair, so a whole-graph score dilutes it by
    C(n,2) and stays near ceiling even when the model takes the bait. Counted
    over the unordered pair, since asserting the retracted claim reversed is
    still a false positive attributable to the manipulation.
    """
    if injected is None:
        return None
    i, j = injected
    return int(bool(pred[i][j] or pred[j][i]))


def predict(prompt, backend):
    """TODO: fill in once we know whether we are using an API or local weights.

    If local weights end up served with vLLM these collapse into one
    OpenAI-compatible call with a different base_url, so hold off building two
    paths until that is decided. Open models take temperature, so set it to 0.
    """
    if backend == "api":
        raise NotImplementedError("TODO: API backend")
    if backend == "local":
        raise NotImplementedError("TODO: local backend")
    raise ValueError(backend)


def fake(r, mode):
    """Synthetic responses, to check the plumbing without spending tokens."""
    A = r["adjacency"]
    n = len(A)
    if mode == "truth":
        B = A
    elif mode == "empty":
        B = [[0] * n for _ in range(n)]
    elif mode == "transpose":
        B = [[A[j][i] for j in range(n)] for i in range(n)]
    elif mode == "bait":                # truth, plus the retracted claim taken
        B = [row[:] for row in A]       # at face value: checks the metric fires
        if r["injected_pair"]:
            B[r["injected_pair"][0]][r["injected_pair"][1]] = 1
    else:
        raise ValueError(mode)
    return json.dumps({"adjacency": B})


def summarise(results, key):
    """Break the run down by one record field."""
    for value in sorted({x[key] for x in results}, key=str):
        rs = [x for x in results if x[key] == value]
        ok = [x for x in rs if x["pred"] is not None]
        hits = [x["injected_hit"] for x in rs if x["injected_hit"] is not None]
        line = (f"  {str(value):14s} n={len(rs):3d}  "
                f"exact {sum(x['shd'] == 0 for x in ok)}/{len(ok)}  "
                f"SHD {sum(x['shd'] for x in ok) / max(len(ok), 1):.3f}")
        if hits:
            line += f"  injected-pair FP {sum(hits)}/{len(hits)}"
        print(line)


if __name__ == "__main__":
    mode = sys.argv[sys.argv.index("--fake") + 1] if "--fake" in sys.argv else None
    backend = "local"                   # TODO: expose once decided
    # Repeats. One sample per item cannot separate a noise effect from sampling
    # noise, which is what the 2026-09-15 run could not do.
    k = int(sys.argv[sys.argv.index("-k") + 1]) if "-k" in sys.argv else 1

    records = [json.loads(line) for line in open("docs.jsonl")]

    results = []
    for r in records:
        prompt = build_prompt(r)
        for sample in range(k):
            raw = fake(r, mode) if mode else predict(prompt, backend)
            pred = parse(raw, len(r["adjacency"]))
            results.append({
                # doc_id alone is not a key once there are repeats and noise
                # conditions; the run is keyed by all three.
                "doc_id": r["doc_id"],
                "sample": sample,
                "condition": r["condition"],
                "noise": r["noise"],
                "style": r["style"],
                "graph_id": r["graph_id"],
                "n": len(r["adjacency"]),
                "injected_pair": r["injected_pair"],
                "injected_is_shortcut": r.get("injected_is_shortcut", False),
                "raw": raw,
                "pred": pred,
                "shd": None if pred is None else shd(pred, r["adjacency"]),
                "injected_hit": None if pred is None
                                else injected_hit(pred, r["injected_pair"]),
            })

    with open("results.jsonl", "w") as f:
        for x in results:
            f.write(json.dumps(x) + "\n")

    ok = [x for x in results if x["pred"] is not None]
    print(f"{len(results)} runs, {len(results) - len(ok)} parse failures")
    for key in ("style", "noise", "n"):
        print(f"\nby {key}:")
        summarise(results, key)
