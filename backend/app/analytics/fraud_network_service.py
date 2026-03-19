"""Graph-based fraud network analysis with community detection."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import md5
from time import monotonic
from typing import Any

import networkx as nx
from sqlalchemy.orm import Session

from app.models.transaction_model import Transaction
from app.models.fraud_prediction_model import FraudPrediction


@dataclass
class _Cache:
    ts: float
    payload: dict[str, Any]


_NETWORK_CACHE: _Cache | None = None


def _synthetic_ip(user_id: Any, location: Any, device: Any) -> str:
    token = f"{user_id}|{location}|{device}".encode("utf-8")
    h = md5(token).hexdigest()
    return f"10.{int(h[0:2], 16)}.{int(h[2:4], 16)}.{int(h[4:6], 16)}"


def _tx_ip(tx: Transaction) -> str:
    tx_ip = getattr(tx, "ip_address", None)
    if tx_ip:
        return str(tx_ip)
    return _synthetic_ip(tx.user_id, tx.location or "UNK", tx.device_type or "UNK")


def _build_graph(db: Session, limit: int = 2000) -> nx.Graph:
    g = nx.Graph()
    rows = (
        db.query(Transaction, FraudPrediction.risk_score, FraudPrediction.risk_category)
        .outerjoin(FraudPrediction, FraudPrediction.transaction_id == Transaction.id)
        .order_by(Transaction.timestamp.desc())
        .limit(limit)
        .all()
    )
    for tx, risk_score, risk_category in rows:
        risk = float(risk_score or 0.0)
        category = risk_category or "SAFE"

        account_node = f"account_{tx.user_id}"
        merchant_node = f"merchant_{tx.merchant or 'Unknown'}"
        device_node = f"device_{tx.device_type or 'Unknown'}"
        ip_node = f"ip_{_tx_ip(tx)}"

        for node_id, node_type, label in (
            (account_node, "account", f"A{tx.user_id}"),
            (merchant_node, "merchant", tx.merchant or "Unknown"),
            (device_node, "device", tx.device_type or "Unknown"),
            (ip_node, "ip", _tx_ip(tx)),
        ):
            if not g.has_node(node_id):
                g.add_node(node_id, type=node_type, label=label, max_risk=risk, tx_count=0)
            g.nodes[node_id]["tx_count"] += 1
            g.nodes[node_id]["max_risk"] = max(float(g.nodes[node_id]["max_risk"]), risk)

        for target, relation in (
            (merchant_node, "transacts_with"),
            (device_node, "uses_device"),
            (ip_node, "uses_ip"),
        ):
            edge_key = (account_node, target)
            if g.has_edge(*edge_key):
                g[edge_key[0]][edge_key[1]]["weight"] += 1
                g[edge_key[0]][edge_key[1]]["max_risk"] = max(
                    float(g[edge_key[0]][edge_key[1]]["max_risk"]),
                    risk,
                )
            else:
                g.add_edge(
                    edge_key[0],
                    edge_key[1],
                    relation=relation,
                    transaction_id=tx.transaction_id,
                    amount=float(tx.amount or 0),
                    risk=float(risk),
                    max_risk=float(risk),
                    risk_category=category,
                    weight=1,
                )
    return g


def _communities(g: nx.Graph) -> list[set[str]]:
    if g.number_of_nodes() == 0:
        return []
    # Louvain community detection (fallback to greedy modularity when unavailable).
    try:
        communities = nx.algorithms.community.louvain_communities(g, seed=42)
    except Exception:
        communities = nx.algorithms.community.greedy_modularity_communities(g)
    return [set(c) for c in communities]


def fraud_network_payload(db: Session, limit: int = 2000, use_cache: bool = True) -> dict[str, Any]:
    global _NETWORK_CACHE
    now = monotonic()
    if use_cache and _NETWORK_CACHE and (now - _NETWORK_CACHE.ts) < 8:
        return _NETWORK_CACHE.payload

    g = _build_graph(db, limit=limit)
    communities = _communities(g)
    cluster_by_node: dict[str, int] = {}
    for idx, members in enumerate(communities):
        for node in members:
            cluster_by_node[node] = idx

    cluster_risk: dict[int, float] = {}
    for idx, members in enumerate(communities):
        risk_vals = [float(g.nodes[m].get("max_risk", 0.0)) for m in members]
        cluster_risk[idx] = float(sum(risk_vals) / len(risk_vals)) if risk_vals else 0.0

    degree_centrality = nx.degree_centrality(g) if g.number_of_nodes() else {}
    betweenness_centrality = nx.betweenness_centrality(g) if g.number_of_nodes() else {}
    fraud_rings = []
    for idx, members in enumerate(communities):
        accounts = sorted(node for node in members if str(node).startswith("account_"))
        shared_devices = sorted(node for node in members if str(node).startswith("device_"))
        shared_merchants = sorted(node for node in members if str(node).startswith("merchant_"))
        if len(accounts) < 2:
            continue
        shared_artifacts = len(shared_devices) + len(shared_merchants)
        if shared_artifacts == 0:
            continue
        avg_centrality = 0.0
        if members:
            avg_centrality = float(sum(degree_centrality.get(node, 0.0) for node in members) / len(members))
        ring_score = min(
            1.0,
            (0.55 * cluster_risk.get(idx, 0.0))
            + (0.25 * min(shared_artifacts / 4.0, 1.0))
            + (0.20 * min(avg_centrality * 4.0, 1.0)),
        )
        fraud_rings.append({
            "cluster_id": idx,
            "accounts": accounts,
            "shared_devices": shared_devices,
            "shared_merchants": shared_merchants,
            "cluster_risk": round(float(cluster_risk.get(idx, 0.0)), 4),
            "graph_risk_score": round(float(ring_score), 4),
        })
    fraud_rings.sort(key=lambda item: item["graph_risk_score"], reverse=True)

    nodes = []
    for node_id, attrs in g.nodes(data=True):
        cluster = cluster_by_node.get(node_id, -1)
        nodes.append({
            "id": node_id,
            "label": attrs.get("label", node_id),
            "type": attrs.get("type", "unknown"),
            "risk": round(float(attrs.get("max_risk", 0.0)), 4),
            "tx_count": int(attrs.get("tx_count", 0)),
            "cluster_label": cluster,
            "cluster_risk": round(float(cluster_risk.get(cluster, 0.0)), 4),
            "degree_centrality": round(float(degree_centrality.get(node_id, 0.0)), 6),
            "betweenness_centrality": round(float(betweenness_centrality.get(node_id, 0.0)), 6),
        })

    edges = []
    for source, target, attrs in g.edges(data=True):
        edges.append({
            "source": source,
            "target": target,
            "relation": attrs.get("relation", "linked"),
            "weight": int(attrs.get("weight", 1)),
            "risk": round(float(attrs.get("max_risk", attrs.get("risk", 0.0))), 4),
        })

    payload = {
        "nodes": nodes,
        "edges": edges,
        "community_count": len(communities),
        "cluster_labels": {n["id"]: n["cluster_label"] for n in nodes},
        "fraud_rings": fraud_rings[:20],
        "graph_metrics": {
            "node_count": g.number_of_nodes(),
            "edge_count": g.number_of_edges(),
            "community_count": len(communities),
            "high_risk_ring_count": sum(1 for ring in fraud_rings if ring["graph_risk_score"] >= 0.65),
        },
    }
    _NETWORK_CACHE = _Cache(ts=now, payload=payload)
    return payload


def transaction_cluster_risk(db: Session, tx: Transaction, limit: int = 2000) -> float:
    payload = fraud_network_payload(db, limit=limit, use_cache=True)
    account_node = f"account_{tx.user_id}"
    node = next((n for n in payload["nodes"] if n["id"] == account_node), None)
    if not node:
        return 0.0
    cluster_id = node.get("cluster_label", -1)
    fraud_ring = next((ring for ring in payload.get("fraud_rings", []) if ring.get("cluster_id") == cluster_id), None)
    cluster_score = float(node.get("cluster_risk", 0.0))
    ring_score = float(fraud_ring.get("graph_risk_score", 0.0)) if fraud_ring else 0.0
    centrality_score = min(float(node.get("degree_centrality", 0.0)) * 4.0, 1.0)
    return float(min(1.0, (0.6 * cluster_score) + (0.3 * ring_score) + (0.1 * centrality_score)))
