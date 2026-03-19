from river import stream, linear_model, metrics

# Online Learning Model
class OnlineFraudModel:
    def __init__(self):
        self.model = linear_model.LogisticRegression()
        self.metric = metrics.Accuracy()

    def update_model(self, x, y):
        self.model.learn_one(x, y)
        self.metric.update(y, self.model.predict_one(x))

    def predict_online(self, x):
        return self.model.predict_proba_one(x)

# Example usage
def example_online_learning():
    data = stream.iter_pandas(
        {
            "amount": [100, 200, 300],
            "hour": [12, 14, 16],
            "fraud": [0, 1, 0],
        },
        target="fraud",
    )

    online_model = OnlineFraudModel()

    for x, y in data:
        online_model.update_model(x, y)
        print(f"Prediction: {online_model.predict_online(x)}, True Label: {y}")