"""Graph-based fraud detection using NetworkX.

Detects:
  - Shared device fraud rings (multiple users on same device)
  - Multiple accounts linked to same merchant with high risk
  - Coordinated fraud clusters (connected components of suspicious activity)
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

import networkx as nx
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.transaction_model import Transaction
from app.models.fraud_prediction_model import FraudPrediction

logger = logging.getLogger(__name__)


def _build_graph(db: Session, limit: int = 2000) -> nx.Graph:
    """Build a transaction graph from recent transactions.

    Nodes: user IDs, merchants, devices, locations
    Edges: transactions linking them
    """
    G = nx.Graph()

    rows = (
        db.query(
            Transaction.user_id,
            Transaction.merchant,
            Transaction.device_type,
            Transaction.location,
            Transaction.amount,
            Transaction.transaction_id,
            FraudPrediction.risk_score,
            FraudPrediction.risk_category,
        )
        .outerjoin(FraudPrediction, FraudPrediction.transaction_id == Transaction.id)
        .order_by(Transaction.timestamp.desc())
        .limit(limit)
        .all()
    )

    for user_id, merchant, device, location, amount, tx_id, risk, cat in rows:
        u_node = f"user_{user_id}"
        m_node = f"merchant_{merchant}" if merchant else None
        d_node = f"device_{device}" if device else None
        l_node = f"location_{location}" if location else None

        risk = risk or 0.0
        cat = cat or "SAFE"

        # Add user node
        if not G.has_node(u_node):
            G.add_node(u_node, type="user", label=f"U{user_id}", risk=0.0, tx_count=0)
        G.nodes[u_node]["tx_count"] += 1
        G.nodes[u_node]["risk"] = max(G.nodes[u_node]["risk"], risk)

        # Add merchant node and edge
        if m_node:
            if not G.has_node(m_node):
                G.add_node(m_node, type="merchant", label=merchant, risk=0.0, tx_count=0)
            G.nodes[m_node]["tx_count"] += 1
            G.nodes[m_node]["risk"] = max(G.nodes[m_node]["risk"], risk)
            if G.has_edge(u_node, m_node):
                G[u_node][m_node]["weight"] += 1
            else:
                G.add_edge(u_node, m_node, weight=1, relation="transacts_at")

        # Add device node and edge
        if d_node:
            if not G.has_node(d_node):
                G.add_node(d_node, type="device", label=device, risk=0.0, tx_count=0)
            G.nodes[d_node]["tx_count"] += 1
            G.nodes[d_node]["risk"] = max(G.nodes[d_node]["risk"], risk)
            if G.has_edge(u_node, d_node):
                G[u_node][d_node]["weight"] += 1
            else:
                G.add_edge(u_node, d_node, weight=1, relation="uses_device")

        # Add location node and edge
        if l_node:
            if not G.has_node(l_node):
                G.add_node(l_node, type="location", label=location, risk=0.0, tx_count=0)
            G.nodes[l_node]["tx_count"] += 1
            if G.has_edge(u_node, l_node):
                G[u_node][l_node]["weight"] += 1
            else:
                G.add_edge(u_node, l_node, weight=1, relation="transacts_from")

    return G


def detect_fraud_clusters(db: Session, min_risk: float = 0.4) -> list[dict[str, Any]]:
    """Detect fraud clusters — connected components where avg risk exceeds threshold."""
    G = _build_graph(db)

    clusters = []
    for component in nx.connected_components(G):
        subgraph = G.subgraph(component)
        user_nodes = [n for n in subgraph.nodes if G.nodes[n].get("type") == "user"]
        if not user_nodes:
            continue

        risks = [G.nodes[n].get("risk", 0) for n in user_nodes]
        avg_risk = sum(risks) / len(risks) if risks else 0

        if avg_risk >= min_risk and len(user_nodes) >= 2:
            clusters.append({
                "cluster_id": len(clusters) + 1,
                "users": [G.nodes[n]["label"] for n in user_nodes],
                "size": len(component),
                "user_count": len(user_nodes),
                "avg_risk": round(avg_risk, 4),
                "max_risk": round(max(risks), 4),
                "shared_devices": [
                    G.nodes[n]["label"]
                    for n in subgraph.nodes
                    if G.nodes[n].get("type") == "device"
                ],
                "shared_merchants": [
                    G.nodes[n]["label"]
                    for n in subgraph.nodes
                    if G.nodes[n].get("type") == "merchant"
                ],
            })

    clusters.sort(key=lambda c: c["avg_risk"], reverse=True)
    return clusters


def detect_device_rings(db: Session) -> list[dict[str, Any]]:
    """Find devices shared by multiple users — potential fraud rings."""
    G = _build_graph(db)
    rings = []

    device_nodes = [n for n in G.nodes if G.nodes[n].get("type") == "device"]
    for d_node in device_nodes:
        users = [
            nbr for nbr in G.neighbors(d_node) if G.nodes[nbr].get("type") == "user"
        ]
        if len(users) >= 2:
            user_risks = [G.nodes[u].get("risk", 0) for u in users]
            rings.append({
                "device": G.nodes[d_node]["label"],
                "users": [G.nodes[u]["label"] for u in users],
                "user_count": len(users),
                "avg_risk": round(sum(user_risks) / len(user_risks), 4),
                "max_risk": round(max(user_risks), 4),
            })

    rings.sort(key=lambda r: r["avg_risk"], reverse=True)
    return rings


def get_graph_data(db: Session, limit: int = 500) -> dict[str, Any]:
    """Return graph data (nodes + edges) for frontend force-graph visualization."""
    G = _build_graph(db, limit=limit)

    nodes = []
    for n, data in G.nodes(data=True):
        nodes.append({
            "id": n,
            "label": data.get("label", n),
            "type": data.get("type", "unknown"),
            "risk": round(data.get("risk", 0), 4),
            "tx_count": data.get("tx_count", 0),
        })

    edges = []
    for u, v, data in G.edges(data=True):
        edges.append({
            "source": u,
            "target": v,
            "weight": data.get("weight", 1),
            "relation": data.get("relation", ""),
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }
