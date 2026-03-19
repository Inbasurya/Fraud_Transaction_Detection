"""Fraud graph API — D3-compatible graph endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.graph_detection.fraud_graph_engine import fraud_graph_engine

router = APIRouter()


@router.get(
    "/{customer_id}",
    summary="Get 2-hop neighborhood for a customer as D3 JSON",
)
def get_customer_graph(
    customer_id: str,
    hops: int = Query(2, ge=1, le=3),
):
    """Return the n-hop neighborhood of a customer as D3-compatible
    JSON with nodes and links arrays."""
    return fraud_graph_engine.get_neighborhood(customer_id, hops=hops)


@router.get(
    "/",
    summary="Get full fraud graph data",
)
def get_fraud_graph(
    limit: int = Query(500, ge=10, le=5000),
):
    """Return full graph as D3-compatible JSON (capped at limit nodes)."""
    return fraud_graph_engine.get_full_graph_data(limit=limit)


@router.get(
    "/clusters/list",
    summary="Get fraud clusters",
)
def get_fraud_clusters():
    """Return clusters containing fraud-flagged nodes."""
    fraud_graph_engine.detect_communities()
    return fraud_graph_engine.get_fraud_clusters()


@router.get(
    "/stats/summary",
    summary="Graph statistics",
)
def get_graph_stats():
    """Return graph statistics: node count, edge count, community count."""
    return fraud_graph_engine.stats()
