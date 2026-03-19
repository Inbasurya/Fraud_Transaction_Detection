"""Enhanced Graph-Based Fraud Detection Engine.

Features:
- Nodes: customers, devices, IP addresses, merchants
- Edges: shared device, shared IP, same merchant, money transfer
- Real-time graph updates stored in Redis
- Louvain community detection for fraud cluster identification
- Per-transaction graph risk features:
  - degree_centrality
  - is_in_fraud_cluster
  - fraud_neighbor_ratio
  - avg_cluster_risk
- D3-compatible graph export for frontend visualization
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import networkx as nx

from app.config import settings

logger = logging.getLogger(__name__)


class FraudGraphEngine:
    """NetworkX-based fraud graph with real-time updates and community detection."""

    def __init__(self) -> None:
        self.graph = nx.Graph()
        self._communities: list[set] = []
        self._fraud_nodes: set[str] = set()
        self._node_risk: dict[str, float] = {}
        self._last_community_update: float = 0.0
        self._redis = None

    def _get_redis(self):
        if self._redis is not None:
            return self._redis
        try:
            import redis
            self._redis = redis.Redis.from_url(
                settings.REDIS_URL, decode_responses=True, socket_timeout=2,
            )
            self._redis.ping()
            return self._redis
        except Exception:
            return None

    def add_transaction(
        self,
        customer_id: str,
        merchant: str,
        device_type: str | None = None,
        ip_address: str | None = None,
        amount: float = 0.0,
        is_fraud: bool = False,
        risk_score: float = 0.0,
    ) -> None:
        """Add a transaction to the graph, creating nodes and edges."""
        # Customer node
        cust_node = f"cust:{customer_id}"
        if not self.graph.has_node(cust_node):
            self.graph.add_node(cust_node, type="customer", risk=0.0, tx_volume=0.0)
        self.graph.nodes[cust_node]["tx_volume"] = (
            self.graph.nodes[cust_node].get("tx_volume", 0) + amount
        )
        self.graph.nodes[cust_node]["risk"] = max(
            self.graph.nodes[cust_node].get("risk", 0), risk_score,
        )
        self._node_risk[cust_node] = self.graph.nodes[cust_node]["risk"]

        if is_fraud:
            self._fraud_nodes.add(cust_node)

        # Merchant node
        if merchant:
            merch_node = f"merch:{merchant}"
            if not self.graph.has_node(merch_node):
                self.graph.add_node(merch_node, type="merchant", risk=0.0, tx_volume=0.0)
            self.graph.nodes[merch_node]["tx_volume"] = (
                self.graph.nodes[merch_node].get("tx_volume", 0) + amount
            )
            self.graph.add_edge(cust_node, merch_node, type="transaction", weight=amount)

        # Device node
        if device_type:
            dev_node = f"dev:{device_type}"
            if not self.graph.has_node(dev_node):
                self.graph.add_node(dev_node, type="device", risk=0.0)
            self.graph.add_edge(cust_node, dev_node, type="shared_device")

        # IP node
        if ip_address:
            ip_node = f"ip:{ip_address}"
            if not self.graph.has_node(ip_node):
                self.graph.add_node(ip_node, type="ip", risk=0.0)
            self.graph.add_edge(cust_node, ip_node, type="shared_ip")

        # Cache in Redis
        self._cache_edge(cust_node, merchant, device_type, ip_address)

    def _cache_edge(self, cust_node: str, merchant: str | None, device: str | None, ip: str | None) -> None:
        r = self._get_redis()
        if r is None:
            return
        try:
            pipe = r.pipeline(transaction=False)
            if merchant:
                pipe.sadd(f"graph:edges:{cust_node}", f"merch:{merchant}")
            if device:
                pipe.sadd(f"graph:edges:{cust_node}", f"dev:{device}")
            if ip:
                pipe.sadd(f"graph:edges:{cust_node}", f"ip:{ip}")
            pipe.expire(f"graph:edges:{cust_node}", 86400)
            pipe.execute()
        except Exception:
            pass

    def detect_communities(self) -> list[set]:
        """Run Louvain community detection on the graph."""
        if self.graph.number_of_nodes() < 3:
            return []
        try:
            from networkx.algorithms.community import greedy_modularity_communities
            communities = list(greedy_modularity_communities(self.graph))
            # Filter to clusters with >= 3 members
            self._communities = [c for c in communities if len(c) >= 3]
            self._last_community_update = time.time()
            return self._communities
        except Exception as exc:
            logger.error("Community detection failed: %s", exc)
            return []

    def compute_graph_features(self, customer_id: str) -> dict[str, Any]:
        """Compute graph-based features for a customer."""
        cust_node = f"cust:{customer_id}"

        if not self.graph.has_node(cust_node):
            return {
                "degree_centrality": 0.0,
                "is_in_fraud_cluster": False,
                "fraud_neighbor_ratio": 0.0,
                "avg_cluster_risk": 0.0,
                "graph_risk_score": 0.0,
            }

        # Degree centrality
        n = self.graph.number_of_nodes()
        degree = self.graph.degree(cust_node)
        degree_centrality = degree / max(n - 1, 1)

        # Betweenness centrality (expensive, use cached or approximate)
        try:
            betweenness = nx.betweenness_centrality(self.graph, k=min(100, n))
            betweenness_score = betweenness.get(cust_node, 0.0)
        except Exception:
            betweenness_score = 0.0

        # Fraud neighbor ratio
        neighbors = list(self.graph.neighbors(cust_node))
        fraud_neighbors = sum(1 for n in neighbors if n in self._fraud_nodes)
        fraud_neighbor_ratio = fraud_neighbors / max(len(neighbors), 1)

        # Is in fraud cluster
        is_in_fraud_cluster = False
        cluster_risk = 0.0
        for community in self._communities:
            if cust_node in community:
                fraud_in_cluster = sum(1 for n in community if n in self._fraud_nodes)
                if fraud_in_cluster >= 2:
                    is_in_fraud_cluster = True
                # Average risk of 2-hop neighborhood
                two_hop = set()
                for neighbor in neighbors:
                    two_hop.update(self.graph.neighbors(neighbor))
                two_hop.discard(cust_node)
                if two_hop:
                    cluster_risk = sum(
                        self._node_risk.get(n, 0.0) for n in two_hop
                    ) / len(two_hop)
                break

        # Composite graph risk score
        graph_risk = min(
            degree_centrality * 0.2
            + betweenness_score * 0.25
            + fraud_neighbor_ratio * 0.35
            + (0.3 if is_in_fraud_cluster else 0.0)
            + cluster_risk * 0.2,
            1.0,
        )

        return {
            "degree_centrality": round(degree_centrality, 4),
            "betweenness_centrality": round(betweenness_score, 4),
            "is_in_fraud_cluster": is_in_fraud_cluster,
            "fraud_neighbor_ratio": round(fraud_neighbor_ratio, 4),
            "avg_cluster_risk": round(cluster_risk, 4),
            "graph_risk_score": round(graph_risk, 4),
        }

    def get_neighborhood(self, customer_id: str, hops: int = 2) -> dict[str, Any]:
        """Return 2-hop neighborhood as D3-compatible JSON (nodes + links)."""
        cust_node = f"cust:{customer_id}"
        if not self.graph.has_node(cust_node):
            return {"nodes": [], "links": []}

        # Collect nodes within n hops
        visited = {cust_node}
        current_layer = {cust_node}
        for _ in range(hops):
            next_layer = set()
            for node in current_layer:
                for neighbor in self.graph.neighbors(node):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_layer.add(neighbor)
            current_layer = next_layer

        # Build D3 output
        nodes = []
        for node_id in visited:
            data = self.graph.nodes.get(node_id, {})
            nodes.append({
                "id": node_id,
                "type": data.get("type", "unknown"),
                "risk": data.get("risk", 0.0),
                "tx_volume": data.get("tx_volume", 0.0),
                "is_fraud": node_id in self._fraud_nodes,
                "is_center": node_id == cust_node,
            })

        links = []
        subgraph = self.graph.subgraph(visited)
        for u, v, data in subgraph.edges(data=True):
            links.append({
                "source": u,
                "target": v,
                "type": data.get("type", "unknown"),
                "weight": data.get("weight", 1.0),
            })

        return {"nodes": nodes, "links": links}

    def get_full_graph_data(self, limit: int = 500) -> dict[str, Any]:
        """Return full graph as D3-compatible JSON (capped at limit nodes)."""
        all_nodes = list(self.graph.nodes(data=True))[:limit]
        node_ids = {n[0] for n in all_nodes}

        nodes = []
        for node_id, data in all_nodes:
            nodes.append({
                "id": node_id,
                "type": data.get("type", "unknown"),
                "risk": data.get("risk", 0.0),
                "tx_volume": data.get("tx_volume", 0.0),
                "is_fraud": node_id in self._fraud_nodes,
            })

        links = []
        for u, v, data in self.graph.edges(data=True):
            if u in node_ids and v in node_ids:
                links.append({
                    "source": u,
                    "target": v,
                    "type": data.get("type", "unknown"),
                })

        return {
            "nodes": nodes,
            "links": links,
            "communities": [
                {"members": list(c), "size": len(c)}
                for c in self._communities[:20]
            ],
        }

    def get_fraud_clusters(self) -> list[dict[str, Any]]:
        """Get clusters that contain fraud nodes."""
        clusters = []
        for i, community in enumerate(self._communities):
            fraud_count = sum(1 for n in community if n in self._fraud_nodes)
            avg_risk = (
                sum(self._node_risk.get(n, 0) for n in community) / len(community)
                if community
                else 0
            )
            if fraud_count > 0 or avg_risk > 0.3:
                clusters.append({
                    "cluster_id": i,
                    "size": len(community),
                    "fraud_count": fraud_count,
                    "avg_risk": round(avg_risk, 4),
                    "members": list(community)[:20],
                })
        return clusters

    def stats(self) -> dict[str, Any]:
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "communities": len(self._communities),
            "fraud_nodes": len(self._fraud_nodes),
            "last_community_update": self._last_community_update,
        }


# Singleton
fraud_graph_engine = FraudGraphEngine()
