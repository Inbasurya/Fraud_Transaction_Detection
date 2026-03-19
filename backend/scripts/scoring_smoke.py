import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from core.scoring import ScoringEngine

logging.basicConfig(level=logging.INFO, format='%(message)s')
logging.getLogger().setLevel(logging.INFO)

engine = ScoringEngine()

scenarios = [
    {
        'name': 'safe_grocery',
        'rule': 0.05,
        'ml': 0.07,
        'behavior': 0.05,
        'graph': 0.05,
        'shap': {'amount': -0.12, 'merchant_risk_score': -0.08, 'txn_count_1h': -0.05},
        'rules': [{'rule_id': 'SAFE', 'name': 'baseline_ok'}],
    },
    {
        'name': 'medium_new_device',
        'rule': 0.70,
        'ml': 0.55,
        'behavior': 0.55,
        'graph': 0.25,
        'shap': {'is_new_device': 0.24, 'amount': 0.18, 'amount_to_avg_ratio': 0.21},
        'rules': [{'rule_id': 'R009', 'name': 'new_device_high_value'}],
    },
    {
        'name': 'high_crypto_new_device',
        'rule': 1.60,
        'ml': 0.80,
        'behavior': 0.85,
        'graph': 0.60,
        'shap': {'merchant_risk_score': 0.55, 'amount_to_avg_ratio': 0.61, 'is_new_device': 0.47},
        'rules': [
            {'rule_id': 'R008', 'name': 'high_risk_merchant'},
            {'rule_id': 'R009', 'name': 'new_device_high_value'},
            {'rule_id': 'R010', 'name': 'amount_spike_vs_profile'},
        ],
    },
]

for case in scenarios:
    res = engine.score(
        rule_score=case['rule'],
        ml_score=case['ml'],
        behavioral_score=case['behavior'],
        graph_score=case['graph'],
        shap_values=case['shap'],
        triggered_rules=case['rules'],
    )
    print(f"SCENARIO {case['name']}: {res}\n")
