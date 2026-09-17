"""Atom graphs: every DAG on n nodes, up to isomorphism.

Exhaustive rather than hand-picked, so there is nothing to defend about the
selection. At n = 3 there are 6 and at n = 4 there are 31.

The four connected ones at n = 3 are exactly Pearl's junction trichotomy
(chain, fork, collider) plus the transitive triangle. The first three share a
skeleton, so they differ only in orientation, and all four are asked the same
question about the pair (X, Z) with ground truth 0, 0, 0, 1: mediated,
confounded, marginally independent, direct. Any fixed policy on that pair caps
at 75%.

Node indices here are whatever the enumeration produced. Permute them when
building families downstream, so index carries no information.
"""

import itertools
import json

import networkx as nx
import numpy as np

# n = 3 shapes worth having a name for; everything else gets an index
TEMPLATES = {
    "empty": [],
    "one_edge": [(0, 1)],
    "chain": [(0, 1), (1, 2)],
    "fork": [(1, 0), (1, 2)],
    "collider": [(0, 1), (2, 1)],
    "triangle": [(0, 1), (1, 2), (0, 2)],
}


def to_nx(A):
    G = nx.DiGraph()
    G.add_nodes_from(range(len(A)))
    G.add_edges_from(zip(*np.nonzero(np.asarray(A))))
    return G


def name_of(A):
    if len(A) != 3:
        return None
    G = to_nx(A)
    for name, edges in TEMPLATES.items():
        H = nx.DiGraph()
        H.add_nodes_from(range(3))
        H.add_edges_from(edges)
        if nx.is_isomorphic(G, H):
            return name
    return None


def enumerate_dags(n):
    """One representative per isomorphism class, in a deterministic order."""
    off = [(i, j) for i in range(n) for j in range(n) if i != j]
    reps = []
    for bits in itertools.product([0, 1], repeat=len(off)):
        A = np.zeros((n, n), dtype=int)
        for (i, j), b in zip(off, bits):
            A[i, j] = b
        G = to_nx(A)
        if not nx.is_directed_acyclic_graph(G):
            continue
        if not any(nx.is_isomorphic(G, to_nx(R)) for R in reps):
            reps.append(A)
    return reps


def shortcut_pairs(A):
    """Pairs (i, j) joined by a directed path of length >= 2, with a_ij.

    These are the pairs the transitivity shortcut acts on: the model has to
    assert i -> j where a_ij == 1 and withhold it where a_ij == 0. In the
    n = 3 atoms this picks out (X, Z) in the chain and the triangle.
    """
    A = np.asarray(A)
    n = len(A)
    indirect = sum(np.linalg.matrix_power(A, k) for k in range(2, n + 1))
    return [[i, j, int(A[i, j])] for i in range(n) for j in range(n)
            if i != j and indirect[i, j] > 0]


def describe(A, n, idx):
    A = np.asarray(A)
    G = to_nx(A)
    name = name_of(A)
    return {
        "graph_id": f"n{n}_{name}" if name else f"n{n}_{idx:02d}",
        "name": name,
        "n": n,
        "adjacency": A.tolist(),
        "edges": [[int(i), int(j)] for i, j in zip(*np.nonzero(A))],
        "n_edges": int(A.sum()),
        "connected": bool(nx.is_weakly_connected(G)),
        "isolated": int(((A.sum(0) + A.sum(1)) == 0).sum()),
        "shortcut_pairs": shortcut_pairs(A),
    }


if __name__ == "__main__":
    records = [describe(A, n, i)
               for n in (3, 4)
               for i, A in enumerate(enumerate_dags(n))]

    with open("data/atoms.jsonl", "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    for n in (3, 4):
        rs = [r for r in records if r["n"] == n]
        print(f"n={n}: {len(rs)} DAGs "
              f"({sum(r['connected'] for r in rs)} connected, "
              f"{sum(r['isolated'] > 0 for r in rs)} with an isolated node)")
    for r in records:
        if r["name"]:
            arrows = " ".join(f"{i}->{j}" for i, j in r["edges"]) or "(none)"
            print(f"  {r['graph_id']:14s} {arrows:20s} "
                  f"shortcut_pairs={r['shortcut_pairs']}")
