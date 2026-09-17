"""Phase 1: DAG sampling.

Follows iTAG (arXiv:2604.06902) Sec 3.2 / Table 3: ER edge sampling, then
injection of confounders, colliders and mediator chains. The paper names these
injection subroutines but never specifies them, so the versions here are ours.
Plain ER at n <= 5 almost never produces these shapes on its own.
"""

import json

import numpy as np


def _inject(A, order, rng, kind):
    """Force one motif onto a random triple, keeping the topological order.

    Taking the triple in topological order as (a, b, c), each motif is built by
    adding two edges and deleting the third. The deletion is what makes the
    motif unshielded, which is the case worth testing: an unshielded mediator
    asks the model to withhold the direct edge, an unshielded confounder or
    collider asks it not to link the two children/parents.
    """
    a, b, c = order[np.sort(rng.choice(len(order), 3, replace=False))]
    if kind == "mediator":  # a -> b -> c, no a -> c
        A[a, b] = A[b, c] = 1
        A[a, c] = 0
    elif kind == "confounder":  # a -> b, a -> c, no b -> c
        A[a, b] = A[a, c] = 1
        A[b, c] = 0
    elif kind == "collider":  # a -> c, b -> c, no a -> b
        A[a, c] = A[b, c] = 1
        A[a, b] = 0


def sample_dag(n, p, rng, max_parents=None, max_children=None,
               n_confounders=0, n_colliders=0, n_mediators=0):
    """Erdos-Renyi DAG plus motif injection. A[i, j] == 1 means i causes j.

    A random permutation fixes a topological order, so acyclicity is free and
    node index carries no information about position in the order.

    Injections can overwrite each other, and they ignore the degree caps, so
    the requested motif counts are a request rather than a guarantee. Use
    count_motifs on the result for what was actually realised.
    """
    order = rng.permutation(n)
    pairs = [(order[a], order[b]) for a in range(n) for b in range(a + 1, n)]
    A = np.zeros((n, n), dtype=int)
    for (i, j), keep in zip(pairs, rng.random(len(pairs)) < p):
        if not keep:
            continue
        if max_children is not None and A[i].sum() >= max_children:
            continue
        if max_parents is not None and A[:, j].sum() >= max_parents:
            continue
        A[i, j] = 1

    if n >= 3:
        kinds = (["confounder"] * n_confounders + ["collider"] * n_colliders
                 + ["mediator"] * n_mediators)
        for kind in rng.permutation(kinds):
            _inject(A, order, rng, kind)
    return A


def is_dag(A):
    """A DAG's adjacency matrix is nilpotent: no path can be longer than n."""
    return not np.linalg.matrix_power(A, len(A)).any()


def longest_path(A):
    depth = np.zeros(len(A), dtype=int)
    for _ in range(len(A)):
        for i, j in zip(*np.nonzero(A)):
            depth[j] = max(depth[j], depth[i] + 1)
    return int(depth.max())


def count_motifs(A):
    n = len(A)
    two_step = A @ A  # two_step[i, j] = number of i -> k -> j paths
    return {
        "n_edges": int(A.sum()),
        "density": round(float(A.sum() / (n * (n - 1) / 2)), 3),
        "forks": int((A.sum(1) >= 2).sum()),  # nodes with >= 2 children
        "colliders": int((A.sum(0) >= 2).sum()),  # nodes with >= 2 parents
        "mediator_paths": int(two_step.sum()),
        # i -> k -> j with no i -> j shortcut: where models tend to compress
        # an indirect path into a direct edge (iTAG App. C.3.3)
        "unshielded_mediators": int(two_step[A == 0].sum()),
        "longest_path": longest_path(A),
    }


if __name__ == "__main__":
    SEED = 0
    P = 0.3
    N_VALUES = [3, 4, 5]
    GRAPHS_PER_N = 3
    # iTAG Table 3: confounder ratio, collider ratio, mediator chain count.
    # Counts scale with n, so n = 3 usually gets no injection at all and the
    # small graphs are not fully determined by the motifs.
    GAMMA_RANGE = (0.0, 0.8)

    master = np.random.default_rng(SEED)
    records = []
    for n in N_VALUES:
        for k in range(GRAPHS_PER_N):
            # Reject graphs with an isolated node: at these n they dominate
            # and effectively shrink the graph. Worth revisiting later, an
            # isolated node is a real case (a concept the text mentions with
            # no causal relations) and models over-predicting edges onto it
            # would be informative.
            # TODO consider graphs with isolated nodes
            while True:
                seed = int(master.integers(2**32))
                rng = np.random.default_rng(seed)  # seed alone reproduces all
                gamma_c, gamma_v = rng.uniform(*GAMMA_RANGE, size=2)
                motifs = {
                    "n_confounders": int(gamma_c * n),
                    "n_colliders": int(gamma_v * n),
                    "n_mediators": int(rng.integers(n - 1)),  # Unif{0..n-2}
                }
                A = sample_dag(n, P, rng, **motifs)
                if (A.sum(0) + A.sum(1) > 0).all():
                    break
            assert is_dag(A)
            records.append(
                {
                    "graph_id": f"n{n}_{k}",
                    "n": n,
                    "p": P,
                    "seed": seed,
                    "requested": motifs,
                    "adjacency": A.tolist(),
                    "edges": [[int(i), int(j)] for i, j in zip(*np.nonzero(A))],
                    **count_motifs(A),
                }
            )

    with open("data/graphs.jsonl", "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    for r in records:
        arrows = " ".join(f"{i}->{j}" for i, j in r["edges"])
        print(
            f"{r['graph_id']:6s} edges={r['n_edges']:2d} "
            f"dens={r['density']:.2f} fork={r['forks']} coll={r['colliders']} "
            f"med={r['unshielded_mediators']} depth={r['longest_path']}  {arrows}"
        )
