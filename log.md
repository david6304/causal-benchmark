# Log

## 2026-09-17 — commitment pilot design

Implemented, not yet run against a model. Design in the 2026-09-17 entries on
the noise taxonomy and on n=3.

**Corpus.** 38 template documents: n=3 (all 4 usable atoms) and n=4 (6 atoms), two
domains, one draw each. 20 clean, 18 commitment. The n=3 triangle has no free pair
so it appears in the clean condition only -- `documents.py` skips it rather than
faking somewhere to put the claim.

`ATOMS_N4` is a hand-picked six of the 25 usable n=4 atoms, all with at least two
free pairs, spread over edge count 2-4 and shortcut-pair count 0-3. `n4_16` and
`n4_23` are kept from the earlier smoke tests. Enumerating all 25 would quadruple
generation for a pilot.

**The manipulation.** One causal proposition about a non-edge pair, asserted under
retraction: "An earlier survey reported that X causes Y; the present data do not
support this." Ground truth is unchanged. The labelling rule is that only positive,
author-committed, direct causal claims count as edges. The word budget is held
fixed across conditions so the retracted claim displaces filler rather than
lengthening the document -- otherwise length is confounded with the manipulation.

**Primary metric: injected-pair FP**, whether the model asserts an edge on the one
pair carrying the retracted claim, counted over the unordered pair. SHD and exact
match dilute a single-pair manipulation by C(n,2). The new `--fake bait` mode
quantifies that: a predictor that takes every bait still reads exact-match 20/38
and mean SHD 0.474 corpus-wide, against 18/18 on the targeted metric. That is the
argument for not repeating the 2026-09-15 mistake of reading a whole-graph score.

**A confound now recorded rather than avoided.** The retracted claim sometimes
lands on a pair that is already mediated (i -> k -> j), stacking commitment on the
transitivity shortcut. At n=3 the chain has exactly one free pair and it is always
the mediated one, so this cannot be avoided there. 5 of the 18 commitment items are
affected; `injected_is_shortcut` is recorded per item so the analysis can split on
it. Whether it should instead be controlled is an open question, better answered
once we know if either pressure does anything.

**Repeats are now possible**, which they were not on 2026-09-15 -- that run was
one sample per item and so could not separate a noise effect from sampling noise.

**The 2026-09-15 faithfulness check does not carry over.** Moving to n=4 changed
the concept draws, so all 38 natural passages are regenerated and their
faithfulness has to be read again rather than inherited. The thing to watch this
time is whether the retracted claim is written as a retraction at all, rather
than flattened into a plain assertion or dropped -- if it is flattened the item
silently becomes a different graph.

## 2026-09-17 — the longer-term shape, and the route from the pilot

The eventual target, as currently framed: a corpus of real heterogeneous documents
(literature, books, blogs, reports), from which a model extracts causal
relationships without letting its prior knowledge override what the documents say.
Everything below is a direction, not a decided design.

**What that setting contains beyond single-document extraction.** Contradictions
between documents; documents of differing reliability; and cases where the model's
prior is *correct* and the document is wrong -- a typo, a transcription error, a
document simply mistaken about something well established. One concrete application
discussed earlier is reducing a Markov equivalence class after running a discovery
algorithm, where the documents supply orientation evidence the data cannot.

**The consequence for our metrics.** If the prior is sometimes right then "less
prior reliance is better" is wrong, and the prior-reliance index from the 2026-09-08
entry is not a pure bug measure. The quantity of interest becomes something closer
to *calibrated deference*:

| | document asserts X->Y | document asserts not-(X->Y), or is silent |
| --- | --- | --- |
| prior says X->Y | agreement, uninformative | does the prior override the text? |
| prior says no edge | **the deployment case**: novel finding, must follow the text | agreement |

The bottom-left cell is the one that matters for "extract from the literature
without the prior overriding". The top-right is where a prior can legitimately help.
Two implications if this framing survives: the plausible arm has to be unparked,
since fictional concepts give only one column; and a binary adjacency may be the
wrong output, because "assert the edge but flag it as contradicting strong prior
knowledge" is a better behaviour than silently picking a side. Parked pending
discussion with Sangyeok.

**Why the commitment pilot is on the path rather than a detour.** A claim asserted
and then retracted inside one document is the single-document form of a
cross-document contradiction. It needs the same discourse machinery in the
generator and the same labelling rule in the eval, but none of the aggregation
scoring or source-reliability modelling. So the pilot buys the linguistic
infrastructure for the multi-document trust arm at single-document cost.

**Rough route, in order, none of it committed.** Commitment at n=3 and n=4 (the
pilot) -> the other two noise families, stacked as NoisyCausal do -> unpark the
plausible arm and measure the prior per item with the text-free control ->
contradiction across documents with a trust signal -> ecological calibration
against a small annotated real-document sample, so the synthetic mixture is
weighted by observed frequency rather than by whatever avoids ceiling.

**On defending the benchmark.** The strongest attack is that this measures
obedience to LLM-authored prose over nonce symbols, and that synthetic robustness
need not predict real extraction. Two cheap moves that help, both current thinking:
describe the output as an **asserted direct-claim graph** rather than a discovered
causal DAG, so a closed-world zero means "not positively asserted" rather than "no
relationship exists"; and lean on guaranteed recoverability, which is precisely
what ReCITE lacks. The heavier validation work -- real-document test set, matched
authentic counterfactuals, predictive criterion validity, prospective transfer --
is noted and deliberately not scheduled.

## 2026-09-17 — n=3 is structurally too easy, with numbers

`evaluate.py` scores pairwise: each unordered pair is one categorical state
(none / i->j / j->i), so SHD_max = C(n,2). The number of pairs available to carry a
false-positive edge is therefore C(n,2) - m, not n(n-1) - m.

Counted over the usable atoms:

```
n=3:  4 usable of 6 classes.  free pairs: 1 atom with 0, 3 atoms with 1
n=4: 25 usable of 31 classes.  free pairs: 1 with 0, 6 with 1, 9 with 2, 8 with 3, 1 with 4
```

So the n=3 triangle has **no** pair on which an over-extraction error can land, and
the other three have exactly one. Any noise family aimed at false positives is
being measured at its weakest possible point. This is the argument for adding n=4
to the pilot, and it is structural rather than a guess about difficulty.

Caveat worth respecting: do not vary n and noise only together, or graph size,
density and context length are confounded with the manipulation. Keep matched
clean/noisy pairs at each n. Also report edge density, since false-positive
opportunity depends on C(n,2) - m rather than on n alone.

## 2026-09-17 — noise taxonomy, and epistemic commitment as the first factor

Reviewed our candidate noise axes against NoisyCausal (Xu & Fu, ACL 2026,
`related-papers/noisy_causal.pdf`) and against a critical read from Codex. Current
position, not settled.

**NoisyCausal transfers less than hoped.** Their task is causal reasoning QA over a
sampled SCM, so four of their six noise types (value perturbation, partial masking,
causal swap, question perturbation) act on *observations* -- variable assignments
the model is given. We give the model no data, only assertions, so those have no
analogue. Irrelevant variable injection and latent confounders are the two that map
across. Worth keeping as precedent: graphs 3-7 nodes, and a composition ablation
(1 noise type 73.5% -> 2 types 67.3% -> all 6 58.0%) suggesting noise types should
stack rather than form a single severity ladder.

**The type we had missed: epistemic commitment.** Real documents constantly mention
a causal proposition without endorsing it -- negation ("we found no evidence that
X affects Y"), hypothesis ("X could adversely affect Y"), investigation ("we tested
whether X drives Y"), and retraction ("initially suspected, subsequently ruled
out"). Each contains the concept pair *and* an explicit causal cue while licensing
no edge, which makes it a sharper false-positive probe than the comparative and
co-occurrence rungs we had listed.

This needs a labelling rule stated up front, otherwise the items are not labelable:
**ground truth = positive, author-committed, direct causal claims.**

Supporting evidence: **BioRelFact** (Gabryszak et al., LREC 2026,
<https://aclanthology.org/2026.lrec-1.602/>), 1,767 expert-annotated biomedical
sentences over nine relation types and five levels of epistemic commitment. Across
eight LLMs, commitment classification is consistently the harder half of the same
task -- best model GPT-OSS-20B scores F1 77.3 on the relation but 65.3 on
commitment; GPT-4o 75.9 / 60.2. That is sentence-level and biomedical, so it is
suggestive rather than a direct prediction for us, but it is the closest thing to
evidence that commitment is separable from relation extraction and harder. No PDF
held locally yet.

**Revised working taxonomy**, three families rather than the seven rungs in the
2026-09-15 entry:

1. **Commitment** -- negation, hypothesis, investigation, retraction. Subsumes the
   "assert then withdraw" device from the 09-15 false-edge discussion as one
   subtype.
2. **Non-causal relational distractors** -- association, prediction, temporal
   order. Merges the old rungs 1 and 2.
3. **Realisation** -- coordination density (several edges per sentence),
   cross-sentence evidence with anaphora and aliasing, controlled paraphrase.

Dropped or held for now, with reasons: *mediation phrasing* ("X affects Z through
Y") asserts a total effect and does not cleanly say whether X->Z is a direct edge,
so it confounds extraction with our graph semantics; *hedging as a severity level*
is a labelling problem, not a level; *generic filler dilution* is a long-context
test more than an extraction test, and distractor **confusability** probably
matters more than word count; *multi-document* stays held, since it entangles
cross-document concept identity as a second construct.

Note that "one edge per sentence" in the current generation prompt is the most
artificial thing about our documents and is family 3's job to relax. It is also
the first thing a reviewer will attack.

**Why the injected-false-edge idea needed reframing.** In a fictional domain an
unqualified assertion of X->Y simply *is* ground truth -- it is a different graph,
not noise. It only becomes noise under a discourse operator that blocks positive
commitment, which is what family 1 provides. Source-reliability framing ("an
unverified report claims...") was considered and set aside as source evaluation
rather than extraction, though it returns in the 2026-09-17 entry on the
longer-term shape.

## 2026-09-17 — ReCITE read: the recoverability problem

Sangyeok's worry about ReCITE (Saklad et al., arXiv 2505.18931, `related-papers/recite.pdf`)
looks well founded, and the paper carries its own evidence for it. Not confirmed
independently, but enough that we should stop treating their headline number as a
difficulty target.

- Explicitness per node averages **0.877**, on a scale where a node is explicit,
  implicit, or **absent**. So roughly one node in eight does not appear in the
  source text at all, and edges into those nodes cannot be recovered by reading.
- §4.2: "while 85-90% of generated edges have some textual support, only 17-33%
  match ground-truth edges." They read this as models producing plausible but
  incorrect relations. The competing reading -- that the ground-truth graph is
  underdetermined by the text -- is equally consistent with it and they do not
  rule it out.
- The only recoverability check is a single expert case study (App. N). Nothing
  systematic.
- Scale and form: 25.0 +- 15.8 nodes (range 5-140), 37.4 +- 24.3 edges, ~40k
  characters of text. 90.4% of the graphs contain feedback cycles, since they are
  causal loop diagrams rather than DAGs. Scoring is LLM-as-judge (DeepSeek v3.2)
  with semantic-similarity and abstraction-level matching.

So the best-model F1 of 0.535 confounds model failure with task impossibility and
should not be quoted as a target. What it does establish is that real-text
extraction is somewhere far below our clean fictional ceiling, and their
explicitness analysis (F1 roughly halves from the most to the least explicit bin)
says where the difficulty lives.

**Reading this as an opportunity rather than a criticism.** Our items are
recoverable by construction, which is exactly what ReCITE cannot claim. If that
holds up it is a contribution worth stating explicitly rather than assuming.
Worth Sangyeok writing down what he actually checked.

One useful design detail to steal: their name-assisted ablation (ground-truth node
names supplied, Table 4) moves F1 only 0.535 -> 0.551 for the best model. That is
their evidence that the bottleneck is relation extraction rather than entity
recognition, and it is the same argument we would need if anyone objects that
supplying the concept list makes our task artificial.

## 2026-09-15 — noise as the next direction

Agreed direction, but the ladder itself is not designed yet. The motivation is the
saturation reported the same day: with the clean arm at ceiling there is nothing to difference
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
should not have been built -- the real-domain arms are parked and this entry
overstates the corpus. `documents.py` now has `PLAUSIBLE = False` gating the
`REAL_DOMAINS` block, and the corpus is 16 fictional documents per style: two
domains, two draws, four atoms. The 8 plausible passages remain in
`natural.jsonl`, unused, in case that arm is unparked.

The naming-drift confound noted above is specific to the plausible arm, since
nonce concepts have no synonyms to drift to, so it does not apply to the current
fictional-only corpus. It would return if the plausible arm is revived.

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

**Matching** (same day). Each natural document is matched to its template
counterpart on graph, concepts and node mapping, so the template arm is the
ceiling for its own pair rather than for the corpus average. Dropping atoms with
an isolated node takes the template corpus from 36 documents to 24.

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
control parked in the 2026-09-08 entry, run per item and per model. Items where the prior turns out
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
