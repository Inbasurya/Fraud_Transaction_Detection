"""Graph-based fraud detection using NetworkX.

Builds a transaction graph where:
  - Nodes = accounts (users/customers)
  - Edges = shared device or shared merchant connections

Detects:
  - Fraud clusters via community detection
  - High centrality nodes (suspicious connectors)
  - Fraud rings (coordinated multi-account patterns)

Outputs: graph_risk_score (0–1)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Optional

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    nx = None
    NETWORKX_AVAILABLE = False

from sqlalchemy.orm import Session

from app.models.transaction_model import Transaction

logger = logging.getLogger(__name__)


class FraudGraph:
    """NetworkX-based fraud ring and cluster detector."""

    def __init__(self):
        self.graph: Optional[nx.Graph] = None
        self._communities: list[set] = []
        self._centrality: dict[str, float] = {}

    # ── Graph construction ────────────────────────────────────

    def build_graph(self, db: Session, limit: int = 5000) -> nx.Graph:
        """Build a graph from recent transactions.

        Nodes: account IDs
        Edges: two accounts share a device_type or merchant
        """
        txs = (
            db.query(Transaction)
            .order_by(Transaction.timestamp.desc())
            .limit(limit)
            .all()
        )

        G = nx.Graph()

        # Group by device_type and merchant
        device_users: dict[str, set[str]] = defaultdict(set)
        merchant_users: dict[str, set[str]] = defaultdict(set)

        for tx in txs:
            uid = str(tx.user_id)
            G.add_node(uid, type="account")

            if tx.device_type:
                device_users[tx.device_type].add(uid)
            if tx.merchant:
                merchant_users[tx.merchant].add(uid)

        # Create edges for shared devices
        for device, users in device_users.items():
            user_list = list(users)
            for i in range(len(user_list)):
                for j in range(i + 1, len(user_list)):
                    if G.has_edge(user_list[i], user_list[j]):
                        G[user_list[i]][user_list[j]]["weight"] += 1
                        G[user_list[i]][user_list[j]]["shared_devices"].add(device)
                    else:
                        G.add_edge(
                            user_list[i], user_list[j],
                            weight=1,
                            shared_devices={device},
                            shared_merchants=set(),
                        )

        # Create edges for shared merchants
        for merchant, users in merchant_users.items():
            user_list = list(users)
            for i in range(len(user_list)):
                for j in range(i + 1, len(user_list)):
                    if G.has_edge(user_list[i], user_list[j]):
                        G[user_list[i]][user_list[j]]["weight"] += 1
                        G[user_list[i]][user_list[j]]["shared_merchants"].add(merchant)
                    else:
                        G.add_edge(
                            user_list[i], user_list[j],
                            weight=1,
                            shared_devices=set(),
                            shared_merchants={merchant},
                        )

        self.graph = G
        logger.info("Fraud graph built: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges())
        return G

    # ── Community detection ───────────────────────────────────

    def detect_communities(self) -> list[set]:
        """Detect fraud clusters using greedy modularity."""
        if self.graph is None or self.graph.number_of_nodes() < 2:
            return []

        try:
            from networkx.algorithms.community import greedy_modularity_communities
            communities = list(greedy_modularity_communities(self.graph))
        except Exception:
            # Fallback to connected components
            communities = [set(c) for c in nx.connected_components(self.graph)]

        # Filter to suspicious clusters (3+ members)
        self._communities = [c for c in communities if len(c) >= 3]
        logger.info("Detected %d suspicious clusters", len(self._communities))
        return self._communities

    # ── Centrality analysis ───────────────────────────────────

    def compute_centrality(self) -> dict[str, float]:
        """Compute betweenness centrality to find connector nodes."""
        if self.graph is None or self.graph.number_of_nodes() < 2:
            return {}

        self._centrality = nx.betweenness_centrality(self.graph, weight="weight")
        return self._centrality

    def get_high_centrality_nodes(self, threshold: float = 0.1) -> list[dict]:
        """Return nodes with centrality above threshold."""
        if not self._centrality:
            self.compute_centrality()

        return [
            {"account_id": node, "centrality": round(score, 4)}
            for node, score in sorted(self._centrality.items(), key=lambda x: -x[1])
            if score >= threshold
        ]

    # ── Risk scoring ──────────────────────────────────────────

    def compute_graph_risk_score(self, user_id: int) -> float:
        """Compute graph-based risk score for a specific user.

        Factors:
          - Membership in a suspicious cluster
          - Betweenness centrality (connector score)
          - Degree centrality (number of connections)
        """
        uid = str(user_id)

        if self.graph is None or uid not in self.graph:
            return 0.0

        score = 0.0

        # Cluster membership score
        for community in self._communities:
            if uid in community:
                cluster_size = len(community)
                score += min(0.3, cluster_size * 0.05)
                break

        # Betweenness centrality contribution
        if not self._centrality:
            self.compute_centrality()
        centrality = self._centrality.get(uid, 0.0)
        score += min(0.35, centrality * 3.0)

        # Degree centrality (connections)
        if self.graph.number_of_nodes() > 1:
            degree = self.graph.degree(uid)
            max_possible = self.graph.number_of_nodes() - 1
            degree_ratio = degree / max_possible if max_possible > 0 else 0
            score += min(0.35, degree_ratio * 2.0)

        return round(min(score, 1.0), 4)

    # ── Graph data for visualization ──────────────────────────

    def get_graph_data(self) -> dict:
        """Return serializable graph data for frontend visualization."""
        if self.graph is None:
            return {"nodes": [], "edges": [], "clusters": []}

        nodes = []
        for node in self.graph.nodes():
            centrality = self._centrality.get(node, 0.0) if self._centrality else 0.0
            cluster_id = -1
            for idx, community in enumerate(self._communities):
                if node in community:
                    cluster_id = idx
                    break
            nodes.append({
                "id": node,
                "type": "account",
                "centrality": round(centrality, 4),
                "degree": self.graph.degree(node),
                "cluster_id": cluster_id,
            })

        edges = []
        for u, v, data in self.graph.edges(data=True):
            edges.append({
                "source": u,
                "target": v,
                "weight": data.get("weight", 1),
                "shared_devices": list(data.get("shared_devices", set())),
                "shared_merchants": list(data.get("shared_merchants", set())),
            })

        clusters = [
            {"cluster_id": idx, "members": list(c), "size": len(c)}
            for idx, c in enumerate(self._communities)
        ]

        return {"nodes": nodes, "edges": edges, "clusters": clusters}


# Module-level singleton
fraud_graph = FraudGraph()
