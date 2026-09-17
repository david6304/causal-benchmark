# Log

## 2026-09-08 — what the benchmark might be testing

Current thinking, not decided. Leaning towards a **diagnostic** benchmark rather than a
capability one, where the unit of evidence is a matched contrast rather than an item. The
worry with fictional-domain scores alone is that they give a level, which may not
distinguish reading from domain recognition.

One possible framing of the hypothesis, as an invariance: *a faithful extractor's output
depends only on which causal relations the text asserts.* That would suggest three shortcut
families, each a violation of one invariance:

| invariance | transformation | shortcut exposed |
| --- | --- | --- |
| semantic relabelling | plausible → fictional → anti-plausible concepts, graph fixed | parametric priors overriding context |
| structural | add/remove a real shortcut edge beside `i→k→j` | transitive closure, over-tidying |
| paraphrase | explicit cue words → implicit phrasing | lexical pattern-matching |

Anti-plausible (text contradicts real-world causality) looks like the higher-power condition,
if it works. The argument for including it: it may be hard to show isolation from memory
using only memory-free items, so it might be better to frame the goal as *measuring how much
of extraction is memory*. Worth testing whether this holds up.

If that framing survives, the headline metric would be a difference (prior-reliance index,
shortcut index) rather than F1, which would mean generating every graph in all conditions
with phrasing held constant.

Possible motivation: prior-driven extraction is invisible on real-domain benchmarks, where
prior and ground truth agree. It would bite when a document reports something novel — arguably
the main case where you'd run the extraction at all. Needs sanity-checking against how people
actually use these tools.

Parked for later: text-free control (concepts, no document) to bound how much of the
plausible-condition score is reading. Comprehension probe to separate confusion from
extraction failure. Real-document validation set for construct validity.

## 2026-09-14 — plausible / anti-plausible, parked

Template document generation works for the fictional arm (`documents.py`), so the next
move is to extend that and get something in front of a model. The real-domain arms are
parked. Notes on where the thinking got to, none of it settled.

**What the plausible arm might be for.** More angles than the one we started with:

- the prior-reliance difference (fictional vs plausible gap), which was the original motive;
- an *over-extraction* probe — in the plausible condition a model can add edges that are
  true in the world but not asserted in the text. That failure is invisible in the fictional
  arm because there is nothing to add from, and it looks closest to a real deployment
  failure. Possibly the most distinctive thing this arm buys;
- an external-validity bridge, since every existing causal-extraction benchmark is
  plausible-domain and our fictional numbers otherwise float free of that literature;
- deployment-realistic performance, on the argument that prior and text usually agree in
  practice, so plausible is the common case and fictional the adversarial one.

**Sourcing the real relationships.** Current view is that robustness does not come from
better sourcing but from *measuring* the prior instead of assuming it — the text-free
control already parked above, run per item and per model. Items where the prior turns out
weak would otherwise degenerate into the fictional condition and dilute the contrast without
showing it in the scores. If an LLM proposes the triples, the proposer should not also be
the judge; iTAG hit the same issue and keep the verifier backbone disjoint (App. B.4.2).
Avoiding the standard Bayesian-network repositories (ASIA, SACHS, ALARM) on the grounds
that those DAGs are memorised *as datasets*, which is a different construct from world
knowledge.

**Whether to copy iTAG's Phase 2 loop.** Leaning no. Their propose–verify–refine search
exists because they need ~12k concept assignments; we enumerate 6 atoms at n=3 and 31 at
n=4, so hand-writing is an afternoon. The stronger worry is construct validity rather than
cost: their acceptance criterion is an LLM's judgement of causal plausibility, and the
quantity we are trying to measure is an LLM's causal beliefs. Worth stealing the
counterfactual verification prompt as a one-pass screen over hand-written assignments,
not as a loop.

**If it scales past n=4**, the alternative to their search is to invert the design — write
one true DAG per domain over ~12 variables and take induced subgraphs. Every structure is
then true by construction with no search, at the cost of not choosing the structures. The
domain DAG could be designed so the atoms we care about appear as induced subgraphs.

**Two things already hit.** Real domains break the pool-and-draw machinery: real concepts
have a fixed true structure, so each atom needs a hand-picked triple with the node mapping
fixed. Two draft domains are in `documents.py` (cardio, agron) as candidates only. And
anti-plausible still needs a decision that is not just renaming — reversing the whole graph
is detectable, rewiring to a different atom is not obviously better.

**A deliberate divergence to keep visible.** iTAG treat non-edges as soft evidence with
graded penalties because they are hard to falsify from short narratives. We are going the
other way, closed-world in the eval prompt with non-edges scored hard, because the
transitivity shortcut is one of the target invariances. That makes our items stricter than
theirs, and the chain items — where complete mediation is an assumption — are where it bites.

## 2026-09-15 — natural-text generation prompt, locked for now

Baseline documents are now LLM-written prose rather than one-sentence-per-edge
templates. The template arm stays as the ceiling condition. Prompt below, arrived
at over six iterations against n=3 chain / fork / collider and two n=4 atoms
(`n4_16`, a 4-chain; `n4_23`, a diamond), all generated with Haiku.

```
The following quantities are measured in a field survey of the Tavrin Basin:
- <concept 0>
- <concept 1>
- ...

Write about <budget> words of natural prose asserting exactly these causal
relationships:
- <cause> causes <effect>
- ...

Give each relationship exactly one sentence of its own. Make clear which quantity
is the cause and which is the effect. Vary the phrasing.

Every other sentence must describe a single quantity on its own. Nothing else in
the passage may connect, compare or summarise two or more quantities.

Output only the passage.
```

Budget is fixed per n, not per graph: 90 words at n=3, ~120 at n=4. Sparser atoms
therefore carry more padding, which is accepted deliberately — scaling the budget
with edge count would make document length a cue for structure, and length is the
more usable shortcut. This will not survive the move to larger graphs, where a
10-edge and a 100-edge graph cannot share a length; the current thinking is that
those become multiple documents per graph instead.

**What each instruction is for.** The last one carries most of the load. Earlier
drafts enumerated prohibitions — no summary sentence, no independence claims, no
transitive statements, no parallelism markers — and a single positive constraint
turned out to rule out all of them at once. A six-rule version performed worse
than this three-instruction one.

**Failure modes seen along the way**, in case they recur:

- *restatement*: each edge asserted, then re-asserted as an elaboration;
- *meta-summary*: a closing sentence characterising the relationships as a set
  ("multiple drivers of zorbium", "the interconnected nature of the measured
  quantities"). Reappeared once at the 150-word budget;
- *non-edge assertion*: the collider document stating its two parents "varied
  independently" — an unrequested claim about a non-edge, present only in that
  atom, which would have made colliders spuriously easy;
- *syntactic collapse*: with no filler at all, each atom got its own grammatical
  template (chain → relative-clause chaining, fork → shared subject, collider →
  shared object in the passive), so structure was recoverable from syntax alone.
  This is why the baseline is not the minimal possible document: some causally
  inert filler is what lets surface form vary independently of structure;
- *covariation drift*: "zorbium rises with marnite density" asserts no direction.

**Unresolved.** Concept names are not always used verbatim ("the abundance of
drovan elements" for "drovan count", "Zorbium" for "zorbium concentration"), which
matters because the eval prompt supplies a concept list; a clause fixing this was
discussed but not added. Filler occasionally attributes a quantity to causes
outside the concept set, which is inert under closed-world scoring over the listed
concepts but sits awkwardly against the complete-mediation assumption for chains.

**Surface order, parked.** Whether an edge sentence names the cause or the effect
first is currently uncontrolled. The idea is to make it a manipulated factor by
writing the edge list in the prompt in the intended surface order, giving a
within-item bias contrast. A first test suggests instruction alone will not
control it: both n=3 chain documents came out with the identical pattern
(sentence 1 cause-first, sentence 2 effect-first) regardless of which order was
requested, and the n=4 chain reordered a reverse-topological edge list into
topological order. The collider complied 2/2, so compliance looks
structure-dependent. Compliance is mechanically checkable — which concept string
appears first in each edge sentence — so generate-check-regenerate is the obvious
route, with per-sentence generation as a fallback for cells that will not comply.

## 2026-09-15 — discovery prompt shortened

`evaluate.py` now carries a short discovery prompt: concepts, document, and the
JSON output spec, with no directness or closed-world clause. A longer variant with
both guards was raced against it on the three documents containing mediated pairs
(n=3 chain, `n4_16` 4-chain with three shortcut pairs, `n4_23` diamond with two
mediated paths). Both recovered every graph exactly, SHD 0 in all six cells, with
no transitive edges invented. One sample per cell through Haiku, no seed or
temperature control, so treat it as a smoke test.

Taking the short form for now. The guards are not thereby shown to be useless —
these items do not discriminate, and the closed-world clause is inert by
construction in a fictional no-noise setting since there is no outside knowledge
about zorbium to suppress. Worth re-racing once documents carry noise, run longer,
or split across multiple documents, and in the plausible arm where over-extraction
from priors is the failure we are looking for.

Also dropped the worked example from the output spec. It was a fixed 3x3 array, so
wrong-shaped at n=4, and it carried a 1 at [0][1], which primes an edge from the
first concept to the second. The shape is now stated as n x n with no example.

**Haiku is at ceiling on the no-noise fictional baseline** at n=3 and n=4. If that
holds up with repeats, these items cannot rank models and the baseline's job is
validation rather than measurement — the same role iTAG give their template
condition. Any ranking signal would have to come from the noise ladder or the
semantic conditions.

It is also weak evidence that the generation prompt works, in that the intended
graph is recoverable from the documents it produces. Keeping that as a reported
statistic rather than an acceptance filter, for the circularity reason: filtering
documents on whether a strong model recovers them caps item difficulty at the
verifier's ability.

**Wiring** (same day). `documents.py` now emits a `style` field. Template records
are built as before; natural records are built from `natural.jsonl` if it exists,
matched to their template counterpart on graph, concepts and node mapping, so the
template arm is the ceiling for its own pair rather than for the corpus average.
With no API wired up the script writes the generation prompts to
`gen_prompts.jsonl` and merges the passages back later. Dropping atoms with an
isolated node takes the template corpus from 36 documents to 24.

## 2026-09-15 — 24 natural documents generated, faithfulness read

All 24 n=3 natural documents generated with Haiku and read by hand against their
target edge sets. `docs.jsonl` now holds 48 records, 24 template and 24 natural,
matched pairwise. Word counts 71-100, median 89 against a 90 budget.

**Faithfulness.** Every document asserts all of its target edges, and no document
asserts a mediated pair as a direct edge -- clean across all four chains and all
four triangles, which are where transitivity would bite. One document failed on
the first attempt and was regenerated: the Ostral collider wrote "rethis load
increases substantially with rising pellune quotient", which is covariation with
no direction asserted. That is the failure the earlier six-rule prompt banned
explicitly and the short prompt does not, so roughly 1 in 24 at this sample size.
Not obviously worth a rule yet; worth watching whether the rate rises with noise.

**A confound to watch: naming drift is worse in the plausible arm.** Real concepts
have synonyms and the generator uses them -- "cerebrovascular event" for stroke
risk, "sodium consumption" for dietary salt intake, "precipitation" for rainfall,
"the amount of nitrogen supplied" for nitrogen fertiliser application, "reservoir
levels" for reservoir water level. Nonce concepts have no synonyms, so the
fictional arm barely drifts at all. Since the eval prompt supplies a concept list
and asks for an adjacency over it, the plausible arm is lexically harder for
reasons that have nothing to do with priors. Any fictional-vs-plausible difference
would then be part naming, part priors, and the prior-reliance index would be
biased. Two candidate fixes: instruct verbatim naming in the generation prompt, or
measure the drift per document and use it as a covariate. The first is simpler and
was already on the list from the n=4 runs.

**Out-of-set quantities appear in filler.** Several documents attribute a listed
quantity to something outside the concept set -- knee osteoarthritis risk to
"advancing age", ossen share correlated with "subsurface groundwater processes",
and one whole filler sentence about evaporation rates. Inert under closed-world
scoring over the listed concepts, and arguably realistic, but the documents are
not strictly about only their three quantities. Worth a decision before the noise
ladder, since "irrelevant material" is one of the noise levels and it is currently
leaking into the baseline uncontrolled.

**Correction, same day.** The 24 above included 8 real-domain documents, which
should not have been built -- the real-domain arms are parked and the entry above
overstates the corpus. `documents.py` now has `PLAUSIBLE = False` gating the
`REAL_DOMAINS` block, and the corpus is 16 fictional documents per style: two
domains, two draws, four atoms. The 8 plausible passages remain in
`natural.jsonl`, unused, in case that arm is unparked.

The naming-drift confound noted above is specific to the plausible arm, since
nonce concepts have no synonyms to drift to, so it does not apply to the current
fictional-only corpus. It would return if the plausible arm is revived.

## 2026-09-15 — Haiku on the natural arm: saturated

16 fictional natural documents at n=3, one sample each, short discovery prompt.

```
exact match 16/16    mean SHD 0.000    parse failures 0
  n3_chain     4/4      n3_fork      4/4
  n3_collider  4/4      n3_triangle  4/4
```

No transitive edge invented on any of the four chains, and the four triangles --
where the shortcut edge is genuinely present -- were recovered too, so the model
is not simply defaulting to transitive closure or to its absence.

**The no-noise fictional baseline is saturated for Haiku at n=3.** Taking it at
face value, 16/16 puts a two-sided 95% lower bound on per-item accuracy at roughly
0.79, so "at ceiling" is the right reading even allowing for the small sample.
Caveats: one sample per item, run through subagents rather than a seeded API call,
so no temperature control and no repeats.

What follows if it holds. These items cannot rank models, and every headline
quantity in the design is a difference of scores -- prior-reliance index, shortcut
index -- which is identically zero when both arms sit at ceiling. So a null result
here would be indistinguishable from a saturated one. Signal has to come from the
noise ladder or the semantic conditions, not from the clean baseline, whose job is
validation. The generation prompt is validated in the weak sense that the intended
graph is recoverable; keeping that as a reported statistic, not an acceptance
filter.

Ranked next steps, not settled: repeats to put an interval on the ceiling; the
orientation eval (skeleton given, directions asked), which is a prompt change on
these same documents and is the MEC-resolution framing; then the paraphrase axis
as the first noise rung.

## 2026-09-15 — noise as the next direction

Agreed direction, but the ladder itself is not designed yet. The motivation is the
saturation above: with the clean arm at ceiling there is nothing to difference
against, so noise is what has to create variance before any of the diagnostic
contrasts can be measured.

Candidate axes, roughly in order of how cheap they are and how directly they serve
the stated question. None settled.

- **Paraphrase / implicitness.** Explicit cue words ("causes", "drives") giving way
  to implicit phrasing. Already listed as one of the three invariances in the
  2026-09-08 entry, and it is a single change to the generation prompt, so it is
  the obvious first rung. It also keeps the corpus small enough to hand-check
  faithfulness, which the heavier axes will not.
- **Surrounding irrelevant material.** Extending the document with content that
  asserts nothing about the listed concepts. Note this is already leaking into the
  baseline uncontrolled -- several documents attribute a concept to something
  outside the concept set, or spend a sentence on a fourth quantity entirely. That
  wants to become a manipulated level rather than an accident.
- **Associational statements about non-edges.** Text that says two concepts move
  together without asserting causation. This is the sharpest probe of the
  closed-world scoring choice, since a faithful extractor should report no edge,
  and it is the failure mode the generator produced spontaneously once ("rethis
  load increases substantially with rising pellune quotient"). Likely the highest
  information per item, and the one most likely to break ceiling.
- **Distribution across multiple documents.** Edges split over several passages so
  no single document contains the graph. This is also the answer to the document
  length problem at larger n, so the two probably want designing together rather
  than as separate axes.

Open question carried over from benchmark-considerations.txt: what noise levels
real documents actually sit at, so we know which rungs matter. Still no good idea
for estimating that, and it may need a small real-document sample to calibrate
against rather than an argument.

One practical note before any of this runs. `preds.jsonl` currently holds a single
run keyed only by doc_id, so repeats or a second condition would overwrite it. It
needs a run or condition identifier before the first noise comparison, not after.
