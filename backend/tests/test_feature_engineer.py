import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from core.feature_engineer import FeatureEngineer
from datetime import datetime

@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.zadd = AsyncMock()
    redis.zremrangebyscore = AsyncMock()
    redis.smembers = AsyncMock(return_value=[b"DEV-123"])
    redis.lrange = AsyncMock(return_value=[b"Mumbai", b"Mumbai", b"Delhi"])
    redis.get = AsyncMock(return_value=b"1500.0")
    
    class MockPipeline:
        def __init__(self):
            self.results = [1, 1, 3, b"1500.0", 1]
            
        def __getattr__(self, name):
            # For any missing Redis method, return a method that returns self (chaining)
            def method(*args, **kwargs):
                if name == "get":
                    return b"1500.0"
                return self
            return method
            
        async def execute(self): return self.results
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc_val, exc_tb): pass
        
    pipeline_instance = MockPipeline()
    redis.pipeline = MagicMock(return_value=pipeline_instance)
    return redis

@pytest.fixture
def feature_engineer(mock_redis):
    return FeatureEngineer(mock_redis)

@pytest.mark.asyncio
async def test_compute_features_basic(feature_engineer):
    txn = {
        "id": "TXN-BASIC-123",
        "customer_id": "CUS-123",
        "merchant": "Amazon",
        "merchant_category": "retail",
        "city": "Mumbai",
        "amount": 500.0,
        "is_new_device": True,
        "device": "DEV-456",
        "timestamp": datetime.now().isoformat()
    }
    
    features = await feature_engineer.compute_features(txn)
    
    assert "amount" in features
    assert "amount_to_avg_ratio" in features
    assert "txn_count_1h" in features
    assert "txn_count_24h" in features
    assert "merchant_risk_score" in features
    
    # Verify expected values based on mock
    assert features["amount"] == 500.0
    assert features["is_new_device"] == 1
    assert features["txn_count_1h"] == 1
    
    # amount_to_avg_ratio = 500.0 / 1500.0 = 0.3333...
    assert abs(features["amount_to_avg_ratio"] - 0.333) < 0.01

@pytest.mark.asyncio
async def test_compute_features_missing_fields(feature_engineer):
    txn = {
        "id": "TXN-MISSING-123",
        "customer_id": "CUS-123",
        "amount": 500.0,
    }
    
    features = await feature_engineer.compute_features(txn)
    
    assert "merchant_risk_score" in features
    assert "geo_risk_score" in features
    assert features["is_new_device"] == 1 # Mock says DEV-123 is known, missing device is new
