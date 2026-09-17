"""Documents from the atom graphs, in two styles.

`template` is one sentence per edge -- the ceiling condition, deliberately not
natural text. `natural` is LLM-written prose asserting the same edges, generated
from the prompt in GEN_PROMPT (see log.md, 2026-09-15). There is no API wired up
here, so this script writes the generation prompts to gen_prompts.jsonl and reads
the passages back from natural.jsonl ({"doc_id": ..., "text": ...}) when that file
exists. Natural records are simply absent until it does.

Atoms with an isolated node are excluded for now: every node must carry at least
one edge. That drops n3_empty and n3_one_edge. The reason is that in natural prose
an unmentioned concept is a free signal for "no edges", which makes those items
degenerate -- the template arm did not have that problem, but both arms are
filtered the same way so the two styles stay comparable.

Notes on the template style follow.

The simplest thing that could work, and deliberately not natural text. Its job
is to be the ceiling condition: ground truth is true by construction, so if a
model cannot recover these graphs then nothing further downstream is
interpretable. iTAG use their template baseline the same way (annotation
F1 = 1, detectability F1 = 0.98 -- obviously machine-written, kept as a sanity
check rather than a product).

Design. A draw is a set of max(SIZES) concepts from one domain's pool, and the
set used at size n is its first n, so the concept sets are nested across sizes.
Growing n then adds variables to a fixed set, and a drop in performance with n
cannot be confounded with the concepts having got harder.

Node-to-concept assignment is permuted per document. With nonce concepts these
are exchangeable, so the mapping cannot make any single item harder -- it only
matters across items, where randomising it stops one concept from being the
source in most documents. The cost is that chain / fork / collider are no
longer built on the same concept in the same skeleton position; if that
contrast ever becomes a headline number rather than a smoke test, canonicalise
those three atoms (atoms.py already holds the canonical forms in TEMPLATES) and
pin the mapping for that sub-analysis.

Concept nouns are nonce and the measure nouns (concentration, index, density,
...) are causally neutral, so nothing in the naming suggests a direction.
Isolated nodes are not mentioned in the text; the concept list is given to the
model separately. The empty graph therefore yields an empty document, which is
kept rather than dropped -- whether a model invents edges from nothing is worth
knowing.
"""

import json
import os
import random

SEED = 0
SIZES = (3,)        # which atom sizes to build documents for
N_DOMAINS = 2       # how many domains to use, of those defined below
N_CONCEPTS = 15     # how many of each domain's concepts are eligible
PLAUSIBLE = False   # real-domain arm, parked (log.md, 2026-09-14)
DRAWS = 2           # concept sets per domain, nested across sizes

TEMPLATE = "{cause} causes {effect}."

# Fixed per n, not per graph: scaling the budget with edge count would make
# document length a cue for structure, and length is the more usable shortcut.
# Sparser atoms therefore carry more padding, which is accepted for now.
WORDS = {3: 90, 4: 120}

GEN_PROMPT = """Setting: {label}

The following quantities are recorded:
{concepts}

Write about {budget} words of natural prose asserting exactly these causal \
relationships:
{edges}

Give each relationship exactly one sentence of its own. Make clear which quantity \
is the cause and which is the effect. Vary the phrasing.

Every other sentence must describe a single quantity on its own. Nothing else in \
the passage may connect, compare or summarise two or more quantities.

Output only the passage."""

# Real domains cannot use a pool: real concepts have a fixed true structure, so
# you cannot draw three at random and get whichever atom you wanted. Each atom
# gets a hand-picked triple with the node mapping fixed, listed as
# [node 0, node 1, node 2] against that atom's edges in atoms.jsonl. These are
# candidates pending the text-free prior screen, not settled ground truth.
REAL_DOMAINS = {
    "cardio": ("Cardiovascular and respiratory epidemiology", {
        # no direct relation between any pair
        "n3_empty": ["blood type", "eye colour", "handedness"],
        # 2 -> 1
        "n3_one_edge": ["eye colour", "resting heart rate",
                        "regular physical exercise"],
        # 2 -> 0, 2 -> 1
        "n3_fork": ["type 2 diabetes risk", "knee osteoarthritis risk",
                    "obesity"],
        # 1 -> 2 -> 0, mediation taken to be complete
        "n3_chain": ["stroke risk", "dietary salt intake", "blood pressure"],
        # 1 -> 0, 2 -> 0, the two causes unrelated to each other
        "n3_collider": ["lung cancer risk", "cigarette smoking",
                        "asbestos exposure"],
        # 2 -> 1 -> 0 with the 2 -> 0 shortcut genuinely present
        "n3_triangle": ["cardiovascular disease risk", "type 2 diabetes",
                        "obesity"],
    }),
    "agron": ("Field agronomy and crop production", {
        "n3_empty": ["seed variety", "soil clay content", "day length"],
        "n3_one_edge": ["market price of wheat", "soil moisture", "rainfall"],
        "n3_fork": ["soil moisture", "reservoir water level", "rainfall"],
        "n3_chain": ["crop yield", "nitrogen fertiliser application",
                     "leaf chlorophyll content"],
        "n3_collider": ["crop yield", "pest infestation level",
                        "hail damage"],
        "n3_triangle": ["crop yield", "soil moisture", "rainfall"],
    }),
}

DOMAINS = {
    "tavrin": ("Tavrin Basin field survey", [
        "zorbium concentration", "kelvic index", "marnite density",
        "drovan count", "sarrel rate", "quenite level", "birrow score",
        "thessil fraction", "veskin load", "omral reading", "pariden ratio",
        "lunnet gradient", "cavren tally", "halven share", "nerrick quotient",
    ]),
    "ostral": ("Ostral Reach hydrology survey", [
        "brallock concentration", "sylth index", "tovrek density",
        "mirran count", "ashlen rate", "crellis level", "dunmar score",
        "paverin fraction", "rethis load", "yoshan reading", "calbrin ratio",
        "tenvar gradient", "vandrel tally", "ossen share", "pellune quotient",
    ]),
}


def document(edges, concepts, rng):
    """One sentence per edge, in a random order so position leaks nothing."""
    order = list(edges)
    rng.shuffle(order)
    sentences = [TEMPLATE.format(cause=concepts[i], effect=concepts[j])
                 for i, j in order]
    sentences = [s[0].upper() + s[1:] for s in sentences]
    return " ".join(sentences), order


def generation_prompt(edges, concepts, label, n, rng):
    """Prompt for one natural-style document, and the edge order it lists.

    The edge list is shuffled so its order is not topological -- otherwise the
    listing itself is a cue. The model reorders anyway (log.md, 2026-09-15), so
    the returned order is what was asked for, not what came back.
    """
    order = list(edges)
    rng.shuffle(order)
    return GEN_PROMPT.format(
        label=label,
        concepts="\n".join(f"- {c}" for c in concepts),
        budget=WORDS[n],
        edges="\n".join(f"- {concepts[i]} causes {concepts[j]}"
                         for i, j in order),
    ), order


if __name__ == "__main__":
    rng = random.Random(SEED)

    atoms = [json.loads(line) for line in open("atoms.jsonl")]
    atoms = [a for a in atoms if a["isolated"] == 0]     # see module docstring
    domains = list(DOMAINS.items())[:N_DOMAINS]

    records = []
    for key, (label, pool) in domains:
        for d in range(DRAWS):
            base = rng.sample(pool[:N_CONCEPTS], max(SIZES))
            for n in SIZES:
                for a in (g for g in atoms if g["n"] == n):
                    concepts = rng.sample(base[:n], n)   # node i -> concepts[i]
                    text, order = document(a["edges"], concepts, rng)
                    records.append({
                        "doc_id": f"{a['graph_id']}__{key}_d{d}",
                        "graph_id": a["graph_id"],
                        "domain": key,
                        "domain_label": label,
                        "draw": d,
                        "condition": "fictional",
                        "style": "template",
                        "concepts": concepts,
                        "adjacency": a["adjacency"],
                        "edges": a["edges"],
                        "sentence_order": order,
                        "text": text,
                        "seed": SEED,
                    })

    for key, (label, by_graph) in (list(REAL_DOMAINS.items())[:N_DOMAINS]
                                  if PLAUSIBLE else []):
        for a in (g for g in atoms if g["graph_id"] in by_graph):
            concepts = by_graph[a["graph_id"]]     # mapping fixed, not permuted
            text, order = document(a["edges"], concepts, rng)
            records.append({
                "doc_id": f"{a['graph_id']}__{key}_d0",
                "graph_id": a["graph_id"],
                "domain": key,
                "domain_label": label,
                "draw": 0,
                "condition": "plausible",
                "style": "template",
                "concepts": concepts,
                "adjacency": a["adjacency"],
                "edges": a["edges"],
                "sentence_order": order,
                "text": text,
                "seed": SEED,
            })

    # Natural counterparts: same graph, same concepts, same node mapping, so the
    # two styles are matched and the template arm is the ceiling for its pair.
    natural = {}
    if os.path.exists("natural.jsonl"):
        natural = {r["doc_id"]: r["text"]
                   for r in map(json.loads, open("natural.jsonl"))}

    prompts = []
    for r in list(records):
        doc_id = r["doc_id"] + "__nat"
        n = len(r["concepts"])
        prompt, order = generation_prompt(r["edges"], r["concepts"],
                                          r["domain_label"], n, rng)
        prompts.append({"doc_id": doc_id, "n": n, "prompt": prompt})
        if doc_id in natural:
            records.append({**r, "doc_id": doc_id, "style": "natural",
                            "sentence_order": None,   # not known, model reorders
                            "listed_order": order,
                            "text": natural[doc_id]})

    with open("gen_prompts.jsonl", "w") as f:
        for p in prompts:
            f.write(json.dumps(p) + "\n")

    with open("docs.jsonl", "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    for style in ("template", "natural"):
        rs = [r for r in records if r["style"] == style]
        print(f"\n=== {style}: {len(rs)} documents ===")
        for r in rs:
            print(f"{r['doc_id']:34s} {r['text'][:70] or '(empty)'}")
    print(f"\n{len(prompts)} generation prompts -> gen_prompts.jsonl")
    if not natural:
        print("natural.jsonl absent, so no natural documents were built")
