import asyncio
import sys
import os
from unittest.mock import MagicMock, patch

# Ensure we can import 'app' and 'backend'
sys.path.append(os.getcwd())

# Mock dependencies BEFORE importing hybrid_engine to avoid import errors
# mocking SQLAlchemy session
mock_db = MagicMock()

# Mock App dependencies
with patch('app.core.features.build_features') as mock_feats, \
     patch('app.ml_models.kaggle_fraud_model.kaggle_model') as mock_kaggle, \
     patch('app.services.rule_engine.evaluate_rules') as mock_rules, \
     patch('app.behavior_models.account_profiler.score_behavior') as mock_behavior, \
     patch('app.analytics.fraud_network_service.transaction_cluster_risk') as mock_graph, \
     patch('backend.core.device_scorer.get_device_score') as mock_device:

    # Setup Mocks
    mock_feats.return_value = {
        "amount": 500.0,
        "device_change_flag": 1,
        "is_new_device": 1
    }
    
    mock_kaggle.predict_scores.return_value = {"ensemble_probability": 0.85}
    mock_kaggle.shap_explanation.return_value = {
        "top_features": [{"feature": "amount", "value": 0.5}],
        "reasons": ["High amount"]
    }
    
    async def async_rules(*args, **kwargs):
        return (0.5, ["Rule 1: Velocity"])
    mock_rules.side_effect = async_rules
    
    mock_behavior.return_value = {
        "behavior_score": 0.6,
        "profile": {"ema_spend_deviation_ratio": 2.5}
    }
    
    mock_graph.return_value = 0.2
    
    # Mock async device scorer
    async def async_device_score(*args, **kwargs):
        return 75.0
    mock_device.side_effect = async_device_score

    # Now import the target module
    from app.fraud_engine.hybrid_engine import score_transaction

    # Create dummy transaction object
    class Transaction:
        timestamp = "2023-10-27T10:00:00"
        amount = 500.0
        user_id = 123
        device_id = "dev_123"
        device_type = "mobile"
        
    tx = Transaction()

    # Run the scoring
    async def run_test():
        print("Running score_transaction...")
        result = await score_transaction(mock_db, tx)
        
        print("\n--- TEST RESULTS ---")
        print(f"Risk Score: {result['risk_score']}")
        print(f"Action: {result['action']}")
        print(f"Confidence Score: {result['explainability'].get('confidence_score')}")
        print(f"Device Risk Score: {result['device_risk_score']}")
        print(f"Explainability: {result['explainability']}")
        
        # Validation
        assert 'confidence_score' in result['explainability'], "Missing confidence_score"
        assert 'device_risk_score' in result, "Missing device_risk_score"
        assert result['device_risk_score'] == 0.75, f"Expected 0.75 device risk, got {result['device_risk_score']}"
        assert result['risk_score'] > 0, "Risk score should be positive"
        
        print("\n✅ VERIFICATION SUCCESSFUL: New scoring logic is active.")

    asyncio.run(run_test())
