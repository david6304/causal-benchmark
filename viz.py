"""Draw sampled DAGs.

    from viz import draw_dag, plot_grid
    draw_dag(A, labels=concepts)          # one graph
    plot_grid(records)                    # a jsonl's worth

    python viz.py [data/atoms.jsonl] [figures/atoms.png]
"""

import json
import sys

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np


def to_graph(A, labels=None):
    A = np.asarray(A)
    G = nx.DiGraph()
    G.add_nodes_from(range(len(A)))
    G.add_edges_from(zip(*np.nonzero(A)))
    if labels is not None:
        # concept names are noun phrases; break them so they fit in the node
        nx.relabel_nodes(G, {i: l.replace(" ", "\n")
                             for i, l in enumerate(labels)}, copy=False)
    return G


def _blocked(pos, u, v, tol=0.15):
    """Does any other node sit on the straight line from u to v?"""
    a, b = np.array(pos[u]), np.array(pos[v])
    d = b - a
    for w, c in pos.items():
        if w in (u, v):
            continue
        t = (np.array(c) - a) @ d / (d @ d)
        if 0 < t < 1 and np.linalg.norm(a + t * d - c) < tol:
            return True
    return False


def draw_dag(A, ax=None, title=None, labels=None):
    """Layered top-to-bottom: a node sits below every one of its causes."""
    G = to_graph(A, labels)
    if ax is None:
        _, ax = plt.subplots(figsize=(4, 4))

    layer = dict.fromkeys(G, 0)
    for v in nx.topological_sort(G):
        for w in G.successors(v):
            layer[w] = max(layer[w], layer[v] + 1)
    nx.set_node_attributes(G, layer, "layer")
    pos = nx.multipartite_layout(G, subset_key="layer", align="horizontal")
    pos = {v: (x, -y) for v, (x, y) in pos.items()}

    size = 900 if labels is None else 2200
    nx.draw_networkx_nodes(G, pos, ax=ax, node_size=size,
                           node_color="#cfe3f7", edgecolors="#3b6ea5")
    nx.draw_networkx_labels(G, pos, ax=ax,
                            font_size=12 if labels is None else 7)
    for u, v in G.edges():
        # straight by default; bow only round a node the edge would pass over,
        # otherwise the edge is drawn on top of the path it bypasses
        rad = 0.1 * (layer[v] - layer[u]) if _blocked(pos, u, v) else 0.0
        nx.draw_networkx_edges(
            G, pos, edgelist=[(u, v)], ax=ax, node_size=size, arrowsize=18,
            width=1.5, connectionstyle=f"arc3,rad={rad}",
        )
    xs = [x for x, _ in pos.values()]
    ys = [y for _, y in pos.values()]
    ax.set_xlim(min(xs) - 0.6, max(xs) + 0.6)
    ax.set_ylim(min(ys) - 0.4, max(ys) + 0.4)
    if title:
        ax.set_title(title, fontsize=10)
    ax.axis("off")
    return ax


def summarise(r):
    """Title line from whatever fields the record happens to carry."""
    keys = ["forks", "colliders", "unshielded_mediators", "longest_path"]
    bits = [f"{k.split('_')[0][:4]}={r[k]}" for k in keys if k in r]
    return f"{r.get('doc_id', r['graph_id'])}  " + " ".join(bits)


def plot_grid(records, path="graphs.png", ncols=3):
    nrows = -(-len(records) // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.7 * ncols, 3.7 * nrows),
                             squeeze=False)
    for ax in axes.flat:
        ax.axis("off")
    for r, ax in zip(records, axes.flat):
        draw_dag(r["adjacency"], ax=ax, title=summarise(r),
                 labels=r.get("concepts"))
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    return path


def load(path="data/atoms.jsonl"):
    return [json.loads(line) for line in open(path)]


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "data/atoms.jsonl"
    out = sys.argv[2] if len(sys.argv) > 2 else "graphs.png"
    print(plot_grid(load(src), out))
