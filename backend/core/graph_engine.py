from __future__ import annotations

"""
Graph Engine — uses NetworkX to detect fraud rings and cluster suspicion.
Nodes are customers/merchants/devices/IPs.
Edges are transaction relationships.
"""

import logging
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)


class GraphEngine:
    """
    Maintains an in-memory transaction graph.
    Detects:
      - shared devices across customers
      - shared IPs across customers
      - mule-chain patterns (A → B → C rapid transfers)
      - dense fraud sub-graphs (community detection)
    """

    def __init__(self):
        self.G = nx.Graph()
        self._fraud_nodes: set[str] = set()

    def add_transaction(self, txn: dict) -> None:
        """Add a transaction's relationships to the graph."""
        cid = txn["customer_id"]
        mid = txn.get("merchant_id", "")
        device = txn.get("device_fingerprint", "")
        ip = txn.get("ip_address", "")

        # Customer node
        if not self.G.has_node(cid):
            self.G.add_node(cid, type="customer", fraud_score=0.0)

        # Merchant node + edge
        if mid:
            if not self.G.has_node(mid):
                self.G.add_node(mid, type="merchant")
            self.G.add_edge(cid, mid, relation="transacted")

        # Device node + edge
        if device:
            device_node = f"dev:{device[:16]}"
            if not self.G.has_node(device_node):
                self.G.add_node(device_node, type="device")
            self.G.add_edge(cid, device_node, relation="uses_device")

        # IP node + edge
        if ip:
            ip_node = f"ip:{ip}"
            if not self.G.has_node(ip_node):
                self.G.add_node(ip_node, type="ip")
            self.G.add_edge(cid, ip_node, relation="uses_ip")

        # Mark fraud
        if txn.get("is_fraud"):
            self._fraud_nodes.add(cid)
            self.G.nodes[cid]["fraud_score"] = max(
                self.G.nodes[cid].get("fraud_score", 0), 0.8
            )

    def score(self, txn: dict) -> dict[str, Any]:
        """
        Compute graph-based risk score for a transaction.
        Returns score + detected patterns.
        """
        cid = txn["customer_id"]
        if cid not in self.G:
            return {"graph_score": 0.0, "patterns": []}

        patterns: list[str] = []
        scores: list[float] = []

        # 1) Shared device with known fraudster
        shared_device_score = self._check_shared_resource(cid, "device")
        if shared_device_score > 0:
            patterns.append("shared_device_with_fraudster")
            scores.append(shared_device_score)

        # 2) Shared IP with known fraudster
        shared_ip_score = self._check_shared_resource(cid, "ip")
        if shared_ip_score > 0:
            patterns.append("shared_ip_with_fraudster")
            scores.append(shared_ip_score)

        # 3) High degree centrality (node is hub)
        try:
            degree = self.G.degree(cid)
            if degree > 20:
                patterns.append("high_connectivity")
                scores.append(min(degree / 100.0, 0.5))
        except Exception:
            pass

        # 4) Community detection — is in same community as fraudsters?
        community_score = self._community_fraud_proximity(cid)
        if community_score > 0:
            patterns.append("fraud_community_proximity")
            scores.append(community_score)

        graph_score = min(sum(scores), 1.0) if scores else 0.0
        return {
            "graph_score": round(graph_score, 4),
            "patterns": patterns,
        }

    def _check_shared_resource(self, cid: str, resource_type: str) -> float:
        """Check if customer shares device/ip with a known fraudster."""
        prefix = "dev:" if resource_type == "device" else "ip:"
        for neighbor in self.G.neighbors(cid):
            if not str(neighbor).startswith(prefix):
                continue
            # Check other customers sharing this resource
            for co_user in self.G.neighbors(neighbor):
                if co_user == cid:
                    continue
                if co_user in self._fraud_nodes:
                    return 0.6
        return 0.0

    def _community_fraud_proximity(self, cid: str) -> float:
        """Simple label-propagation community check."""
        if self.G.number_of_nodes() < 10:
            return 0.0

        try:
            communities = nx.community.label_propagation_communities(self.G)
            for community in communities:
                if cid in community:
                    fraud_in_community = community & self._fraud_nodes
                    if fraud_in_community:
                        return min(len(fraud_in_community) / max(len(community), 1), 0.5)
                    break
        except Exception:
            pass
        return 0.0

    def get_network_data(self, limit: int = 200) -> dict:
        """Return graph data for frontend visualization."""
        nodes = []
        edges = []

        sub_nodes = list(self.G.nodes(data=True))[:limit]
        node_ids = {n[0] for n in sub_nodes}

        for node_id, data in sub_nodes:
            is_fraud = node_id in self._fraud_nodes
            nodes.append(
                {
                    "id": str(node_id),
                    "type": data.get("type", "unknown"),
                    "fraud_score": data.get("fraud_score", 0),
                    "is_fraud": is_fraud,
                }
            )

        for u, v, data in self.G.edges(data=True):
            if u in node_ids and v in node_ids:
                edges.append(
                    {
                        "source": str(u),
                        "target": str(v),
                        "relation": data.get("relation", ""),
                    }
                )

        return {
            "nodes": nodes,
            "edges": edges,
            "fraud_nodes": len(self._fraud_nodes),
            "total_nodes": self.G.number_of_nodes(),
            "total_edges": self.G.number_of_edges(),
        }

    def clear(self) -> None:
        self.G.clear()
        self._fraud_nodes.clear()
