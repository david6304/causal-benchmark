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
model separately. The empty graph would therefore yield an empty document, but it
has an isolated node and so is dropped by the filter above rather than kept.

The commitment noise condition is described at NOISES below.
"""

import json
import os
import random

SEED = 0
SIZES = (3, 4)      # which atom sizes to build documents for
N_DOMAINS = 2       # how many domains to use, of those defined below
N_CONCEPTS = 15     # how many of each domain's concepts are eligible
PLAUSIBLE = False   # real-domain arm, parked (log.md, 2026-09-14)
DRAWS = 1           # concept sets per domain, nested across sizes

# Six of the 25 usable n=4 atoms, all with at least two free pairs so the
# commitment condition has somewhere to land. Chosen to spread edge count (2-4)
# and shortcut-pair count (0-3); n4_16 (4-chain) and n4_23 (diamond) are the two
# used in the earlier smoke tests, kept for continuity. Enumerating all 25 would
# quadruple generation for a pilot.
ATOMS_N4 = ("n4_03", "n4_08", "n4_12", "n4_16", "n4_23", "n4_25")

# Noise conditions. "clean" is the 2026-09-15 baseline. "commitment" adds one
# causal proposition about a NON-edge pair, asserted under a discourse operator
# that blocks author commitment -- here retraction, which is the single-document
# form of a cross-document contradiction (log.md, 2026-09-17). Ground truth is
# unchanged: the labelling rule is that only positive, author-committed, direct
# causal claims count as edges.
NOISES = ("clean", "commitment")

TEMPLATE = "{cause} causes {effect}."
RETRACTION = ("An earlier survey reported that {cause} causes {effect}; "
              "the present data do not support this.")

# Fixed per n, not per graph: scaling the budget with edge count would make
# document length a cue for structure, and length is the more usable shortcut.
# Sparser atoms therefore carry more padding, which is accepted for now.
# The budget is also held fixed across noise conditions, so the retracted claim
# displaces filler rather than lengthening the document -- otherwise length is
# confounded with the manipulation in the within-graph contrast.
WORDS = {3: 90, 4: 120}

GEN_PROMPT = """Setting: {label}

The following quantities are recorded:
{concepts}

Write about {budget} words of natural prose asserting exactly these causal \
relationships:
{edges}

Give each relationship exactly one sentence of its own. Make clear which quantity \
is the cause and which is the effect. Vary the phrasing.
{extra}
Every other sentence must describe a single quantity on its own. Nothing else in \
the passage may connect, compare or summarise two or more quantities.

Output only the passage."""

# Inserted into GEN_PROMPT for the commitment condition. It has to carve itself
# out of the "nothing else may connect two quantities" rule below it, which is
# the rule doing most of the work in the clean prompt (log.md, 2026-09-15).
RETRACT_CLAUSE = """
Then add exactly one sentence reporting that an earlier survey found that \
{cause} causes {effect}, and that the present data do not support this. That is \
the only sentence besides the ones above that may mention two quantities together.
"""

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


def document(edges, concepts, rng, injected=None):
    """One sentence per edge, in a random order so position leaks nothing.

    The retracted claim goes last rather than in the shuffle, so its position is
    fixed and any effect is not diluted across positions. Whether position
    matters is a separate question and not one this pilot asks.
    """
    order = list(edges)
    rng.shuffle(order)
    sentences = [TEMPLATE.format(cause=concepts[i], effect=concepts[j])
                 for i, j in order]
    if injected is not None:
        sentences.append(RETRACTION.format(cause=concepts[injected[0]],
                                           effect=concepts[injected[1]]))
    sentences = [s[0].upper() + s[1:] for s in sentences]
    return " ".join(sentences), order


def free_pair(adjacency, rng):
    """An ordered pair with no edge either way, or None if the graph is full.

    This is where a commitment item can put its retracted claim: asserting it
    over a pair that already carries an edge would change the ground truth
    rather than add a distractor. The n=3 triangle has no such pair, which is
    the whole argument for adding n=4 (log.md, 2026-09-17).
    """
    n = len(adjacency)
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)
             if not adjacency[i][j] and not adjacency[j][i]]
    if not pairs:
        return None
    i, j = rng.choice(pairs)
    return (i, j) if rng.random() < 0.5 else (j, i)   # direction is arbitrary


def generation_prompt(edges, concepts, label, n, rng, injected=None):
    """Prompt for one natural-style document, and the edge order it lists.

    The edge list is shuffled so its order is not topological -- otherwise the
    listing itself is a cue. The model reorders anyway (log.md, 2026-09-15), so
    the returned order is what was asked for, not what came back.

    `injected` is the ordered non-edge pair for the commitment condition, or
    None for a clean document.
    """
    order = list(edges)
    rng.shuffle(order)
    extra = "" if injected is None else RETRACT_CLAUSE.format(
        cause=concepts[injected[0]], effect=concepts[injected[1]])
    return GEN_PROMPT.format(
        label=label,
        concepts="\n".join(f"- {c}" for c in concepts),
        budget=WORDS[n],
        edges="\n".join(f"- {concepts[i]} causes {concepts[j]}"
                         for i, j in order),
        extra=extra,
    ), order


if __name__ == "__main__":
    rng = random.Random(SEED)

    atoms = [json.loads(line) for line in open("atoms.jsonl")]
    atoms = [a for a in atoms if a["isolated"] == 0]     # see module docstring
    atoms = [a for a in atoms if a["n"] != 4 or a["graph_id"] in ATOMS_N4]
    domains = list(DOMAINS.items())[:N_DOMAINS]

    records = []
    for key, (label, pool) in domains:
        for d in range(DRAWS):
            base = rng.sample(pool[:N_CONCEPTS], max(SIZES))
            for n in SIZES:
                for a in (g for g in atoms if g["n"] == n):
                    # Seeded per item rather than off the shared stream, so that
                    # adding a noise condition or a graph size does not shift
                    # every later document's concepts. The move to n=4 already
                    # changed `base` (drawn at max(SIZES)), so the 2026-09-15
                    # natural corpus is invalidated and regenerates regardless.
                    irng = random.Random(f"{SEED}|{key}|{d}|{a['graph_id']}")
                    # Drawn once per item so the noise conditions are matched on
                    # concepts, node mapping and injected pair, and the contrast
                    # is within-item.
                    concepts = irng.sample(base[:n], n)  # node i -> concepts[i]
                    injected = free_pair(a["adjacency"], irng)
                    for noise in NOISES:
                        if noise == "commitment" and injected is None:
                            continue        # nowhere to put it, e.g. n3_triangle
                        inj = injected if noise == "commitment" else None
                        text, order = document(a["edges"], concepts, irng, inj)
                        records.append({
                            "doc_id": f"{a['graph_id']}__{key}_d{d}__{noise}",
                            "graph_id": a["graph_id"],
                            "domain": key,
                            "domain_label": label,
                            "draw": d,
                            "condition": "fictional",
                            "noise": noise,
                            "injected_pair": inj,
                            # Whether the retracted claim landed on a pair that
                            # is already mediated, e.g. i -> k -> j. Then the
                            # item stacks commitment on the transitivity
                            # shortcut and the two pressures are confounded. At
                            # n=3 the chain has only one free pair and it is
                            # always the mediated one, so this cannot be avoided
                            # there -- recorded so the analysis can split on it.
                            # shortcut_pairs entries are [i, j, present]; a pair
                            # with present=1 carries an edge and so is never
                            # free, hence only i, j are compared.
                            "injected_is_shortcut": inj is not None and sorted(
                                inj) in [sorted(p[:2])
                                         for p in a["shortcut_pairs"]],
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
                "noise": "clean",          # parked arm, noise not built for it
                "injected_pair": None,
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
                                          r["domain_label"], n, rng,
                                          r["injected_pair"])
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
        for noise in NOISES:
            print(f"  {noise:11s} "
                  f"{sum(1 for r in rs if r['noise'] == noise):3d}")
    print(f"\n{len(prompts)} generation prompts -> gen_prompts.jsonl")
    missing = [p["doc_id"] for p in prompts if p["doc_id"] not in natural]
    if missing:
        print(f"{len(missing)} passages still to generate")
