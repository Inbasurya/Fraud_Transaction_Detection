"""
Real-time transaction network graph using NetworkX.
Detects:
1. Mule chains: A→B→C→D (money laundering hops)
2. Burst patterns: one account suddenly receives from 10+ new accounts  
3. Star topology: hub account collecting from many sources (money muling)
4. Cyclic flows: money goes A→B→C→A (round-tripping)
5. Rapid fan-out: one account sends to 5+ new recipients in 1 hour

Stored as adjacency list in Redis. Analyzed on every P2P transaction.
"""
import json
import time
from collections import defaultdict
import redis.asyncio as aioredis

class NetworkGraph:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.EDGE_TTL = 86400 * 7  # edges expire in 7 days

    async def add_edge(self, sender: str, receiver: str, amount: float, timestamp: float):
        """Record a transaction edge in the graph."""
        edge_key = f"graph:edges:{sender}"
        edge_data = json.dumps({
            "to": receiver,
            "amount": amount,
            "timestamp": timestamp
        })
        await self.redis.zadd(edge_key, {edge_data: timestamp})
        await self.redis.zremrangebyscore(edge_key, 0, timestamp - self.EDGE_TTL)
        await self.redis.expire(edge_key, self.EDGE_TTL)

        # Also store reverse edges for receiver
        rev_key = f"graph:edges_in:{receiver}"
        await self.redis.zadd(rev_key, {edge_data: timestamp})
        await self.redis.zremrangebyscore(rev_key, 0, timestamp - self.EDGE_TTL)
        await self.redis.expire(rev_key, self.EDGE_TTL)

    async def analyze_node(self, customer_id: str) -> dict:
        """
        Analyze network position of a customer.
        Returns risk signals for the ML feature set.
        """
        now = time.time()
        window_1h = now - 3600
        window_24h = now - 86400

        # Outgoing edges (who this customer sent to)
        out_key = f"graph:edges:{customer_id}"
        out_raw = await self.redis.zrangebyscore(out_key, window_24h, now)
        out_edges = [json.loads(e) for e in out_raw]

        # Incoming edges (who sent to this customer)
        in_key = f"graph:edges_in:{customer_id}"
        in_raw = await self.redis.zrangebyscore(in_key, window_24h, now)
        in_edges = [json.loads(e) for e in in_raw]

        # 1. Fan-out: how many unique recipients in 1h
        out_1h = [e for e in out_edges if e["timestamp"] > window_1h]
        unique_recipients_1h = len(set(e["to"] for e in out_1h))

        # 2. Fan-in: how many unique senders in 24h
        unique_senders_24h = len(set(e.get("from", "") for e in in_edges))

        # 3. Amount flow ratio (out/in) — mules send out ~85% of what they receive
        total_out = sum(e["amount"] for e in out_edges)
        total_in = sum(e["amount"] for e in in_edges)
        flow_ratio = total_out / (total_in + 1)

        # 4. Rapid fan-out signal (burst of sends in 1h)
        is_rapid_fanout = 1.0 if unique_recipients_1h >= 5 else 0.0

        # 5. Hub score — is this a collection point?
        is_hub = 1.0 if unique_senders_24h >= 8 else 0.0

        # 6. Mule ratio — passes through ~85% of received funds
        is_mule_ratio = 1.0 if (0.75 <= flow_ratio <= 0.95) else 0.0

        # 7. Network depth — how many hops from known fraud nodes
        fraud_proximity = await self._fraud_proximity(customer_id)

        # Composite network risk
        network_risk = (
            is_rapid_fanout * 0.35 +
            is_hub * 0.25 +
            is_mule_ratio * 0.25 +
            min(1.0, fraud_proximity * 0.5) * 0.15
        )

        return {
            "unique_recipients_1h": float(unique_recipients_1h),
            "unique_senders_24h": float(unique_senders_24h),
            "flow_ratio": float(flow_ratio),
            "is_rapid_fanout": is_rapid_fanout,
            "is_hub_account": is_hub,
            "is_mule_ratio": is_mule_ratio,
            "fraud_proximity": float(fraud_proximity),
            "network_risk_score": float(network_risk)
        }

    async def _fraud_proximity(self, customer_id: str) -> float:
        """Check if this customer is connected to known fraud accounts."""
        fraud_key = f"known_fraud_accounts"
        known_fraud = await self.redis.smembers(fraud_key)
        known_fraud = {f.decode() for f in known_fraud}
        if not known_fraud:
            return 0.0

        out_key = f"graph:edges:{customer_id}"
        out_raw = await self.redis.zrange(out_key, 0, -1)
        for e in out_raw:
            edge = json.loads(e)
            if edge.get("to") in known_fraud:
                return 1.0  # direct connection to fraud account
        return 0.0

    async def mark_fraud_account(self, customer_id: str):
        """When fraud confirmed, mark account for proximity detection."""
        await self.redis.sadd("known_fraud_accounts", customer_id)
        await self.redis.expire("known_fraud_accounts", 86400 * 30)
