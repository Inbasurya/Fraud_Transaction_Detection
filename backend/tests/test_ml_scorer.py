import pytest
from core.ml_scorer import MLScorer

@pytest.fixture
def scorer():
    return MLScorer()

@pytest.mark.asyncio
async def test_score_rule_based_fallback(scorer):
    # Ensure ML is not loaded for this test
    scorer.model_loaded = False
    
    features = {
        "amount_vs_avg": 5.0,
        "velocity_1h": 10,
        "is_new_device": 1,
        "amount": 50000,
        "geo_risk": 0.5,
        "merchant_risk": 0.5,
        "device_trust": 0.5,
        "time_of_day_risk": 0.5,
        "velocity_24h": 20,
        "avg_txn_value_24h": 1000,
        "velocity_7d": 50,
        "avg_txn_value_7d": 1200,
        "dist_to_home": 500,
        "txn_count_1h": 10,
        "txn_count_same_merchant_1h": 2,
        "txn_count_same_merchant_24h": 5,
        "txn_count_same_city_1h": 1,
        "amount_to_avg_ratio": 6.0,
        "is_weekend": 0,
        "cross_border": 1,
        "days_since_account_open": 100,
        "previous_declines_24h": 2,
        "is_high_risk_category": 1
    }
    
    result = await scorer.score(features)
    
    assert "risk_score" in result
    assert "risk_level" in result
    assert "action" in result
    
    assert result["risk_score"] > 80
    assert result["risk_level"] == "fraudulent"
    assert "R001" in result["triggered_rules"]

@pytest.mark.asyncio
async def test_score_safe_transaction(scorer):
    scorer.model_loaded = False
    
    features = {
        "amount_vs_avg": 1.0,
        "velocity_1h": 1,
        "is_new_device": 0,
        "amount": 50,
        "geo_risk": 0.1,
        "merchant_risk": 0.1,
        "device_trust": 0.9,
        "time_of_day_risk": 0.1,
        "velocity_24h": 2,
        "avg_txn_value_24h": 55,
        "velocity_7d": 10,
        "avg_txn_value_7d": 50,
        "dist_to_home": 5,
        "txn_count_same_merchant_1h": 0,
        "txn_count_same_merchant_24h": 1,
        "txn_count_same_city_1h": 1,
        "amount_vs_merchant_avg": 1.0,
        "is_weekend": 0,
        "cross_border": 0,
        "days_since_account_open": 1000,
        "previous_declines_24h": 0,
        "is_high_risk_category": 0
    }
    
    result = await scorer.score(features)
    
    assert result["risk_score"] < 40
    assert result["risk_level"] == "safe"
    assert result["action"] == "approve"
