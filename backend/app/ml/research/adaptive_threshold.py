import numpy as np

# Adaptive Thresholding
class AdaptiveThreshold:
    def __init__(self):
        self.thresholds = {"low": 0.3, "medium": 0.7, "high": 1.0}

    def calculate_dynamic_thresholds(self, scores):
        self.thresholds["low"] = np.percentile(scores, 30)
        self.thresholds["medium"] = np.percentile(scores, 70)
        self.thresholds["high"] = np.percentile(scores, 90)

    def classify_risk(self, score):
        if score < self.thresholds["low"]:
            return "LOW"
        elif score < self.thresholds["medium"]:
            return "MEDIUM"
        else:
            return "HIGH"

# Example usage
def example_adaptive_threshold():
    scores = np.random.rand(100)
    adaptive = AdaptiveThreshold()
    adaptive.calculate_dynamic_thresholds(scores)
    print(adaptive.thresholds)
    for score in scores[:10]:
        print(f"Score: {score:.2f}, Risk: {adaptive.classify_risk(score)}")