from prometheus_client import Counter, Histogram, Gauge

# Transactions
TRANSACTIONS_PROCESSED = Counter(
    "fraud_transactions_total",
    "Total number of transactions processed",
    ["status"] # 'safe', 'suspicious', 'fraudulent'
)

# Risk Scores
RISK_SCORE_GAUGE = Gauge(
    "fraud_latest_risk_score",
    "Latest computed risk score"
)

# Processing Time
PROCESSING_TIME = Histogram(
    "fraud_processing_seconds",
    "Time spent processing a transaction",
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

# ML vs Rule engine fallback
SCORING_ENGINE_USED = Counter(
    "fraud_scoring_engine_total",
    "Engine used to score transaction",
    ["engine"] # 'ml', 'rules'
)
