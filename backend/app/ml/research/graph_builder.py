import networkx as nx
from collections import Counter
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def build_transaction_graph(transactions):
    """
    Build a graph from transaction data.

    Args:
        transactions: List of transaction records (dicts).

    Returns:
        A NetworkX graph.
    """
    logger.info("Building transaction graph...")
    G = nx.DiGraph()

    for txn in transactions:
        user_id = txn['user_id']
        txn_id = txn['transaction_id']
        merchant = txn['merchant']
        device = txn['device_type']
        location = txn['location']

        # Add nodes
        G.add_node(user_id, node_type="user")
        G.add_node(txn_id, node_type="transaction")
        G.add_node(merchant, node_type="merchant")
        G.add_node(device, node_type="device")
        G.add_node(location, node_type="location")

        # Add edges
        G.add_edge(user_id, txn_id)
        G.add_edge(txn_id, merchant)
        G.add_edge(txn_id, device)
        G.add_edge(txn_id, location)

    logger.info("Transaction graph built successfully.")
    return G

def compute_user_graph_features(G):
    """
    Compute graph metrics for each user.

    Args:
        G: A NetworkX graph.

    Returns:
        Dictionary mapping user_id to graph features.
    """
    logger.info("Computing user graph features...")
    user_nodes = [n for n, attr in G.nodes(data=True) if attr['node_type'] == 'user']

    degree_centrality = nx.degree_centrality(G)
    betweenness_centrality = nx.betweenness_centrality(G)
    clustering_coefficient = nx.clustering(G.to_undirected())

    user_features = {}
    for user in user_nodes:
        user_features[user] = {
            "degree_centrality": degree_centrality.get(user, 0),
            "betweenness_centrality": betweenness_centrality.get(user, 0),
            "clustering_coefficient": clustering_coefficient.get(user, 0),
        }

    logger.info("User graph features computed successfully.")
    return user_features

def detect_suspicious_patterns(G):
    """
    Detect suspicious patterns in the graph.

    Args:
        G: A NetworkX graph.

    Returns:
        List of suspicious nodes.
    """
    logger.info("Detecting suspicious patterns...")
    suspicious_nodes = []

    # Highly connected merchants
    merchant_nodes = [n for n, attr in G.nodes(data=True) if attr['node_type'] == 'merchant']
    for merchant in merchant_nodes:
        if G.in_degree(merchant) > 10:  # Example threshold
            suspicious_nodes.append(merchant)

    # Devices used by many users
    device_nodes = [n for n, attr in G.nodes(data=True) if attr['node_type'] == 'device']
    for device in device_nodes:
        if G.in_degree(device) > 5:  # Example threshold
            suspicious_nodes.append(device)

    # Users transacting from many locations
    user_nodes = [n for n, attr in G.nodes(data=True) if attr['node_type'] == 'user']
    for user in user_nodes:
        locations = [nbr for nbr in G.successors(user) if G.nodes[nbr]['node_type'] == 'location']
        if len(set(locations)) > 3:  # Example threshold
            suspicious_nodes.append(user)

    logger.info("Suspicious patterns detected successfully.")
    return suspicious_nodes

def analyze_transactions(transactions):
    """
    Analyze transactions to build a graph, compute user features, and detect suspicious nodes.

    Args:
        transactions: List of transaction records (dicts).

    Returns:
        Dictionary with graph, user features, and suspicious nodes.
    """
    G = build_transaction_graph(transactions)
    user_graph_features = compute_user_graph_features(G)
    suspicious_nodes = detect_suspicious_patterns(G)

    return {
        "graph": G,
        "user_graph_features": user_graph_features,
        "suspicious_nodes": suspicious_nodes
    }