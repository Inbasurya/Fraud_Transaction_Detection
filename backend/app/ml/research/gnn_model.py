import torch
from torch_geometric.nn import GCNConv, GraphSAGE
from torch_geometric.data import Data
import pandas as pd

# Graph Neural Network Model
class GNNFraudDetector(torch.nn.Module):
    def __init__(self, input_dim, hidden_dim, output_dim, model_type="gcn"):
        super(GNNFraudDetector, self).__init__()
        if model_type == "gcn":
            self.conv1 = GCNConv(input_dim, hidden_dim)
            self.conv2 = GCNConv(hidden_dim, output_dim)
        elif model_type == "sage":
            self.conv1 = GraphSAGE(input_dim, hidden_dim)
            self.conv2 = GraphSAGE(hidden_dim, output_dim)
        else:
            raise ValueError("Unsupported model type")

    def forward(self, x, edge_index):
        x = self.conv1(x, edge_index).relu()
        x = self.conv2(x, edge_index)
        return x

# Function to train the GNN model
def train_gnn_model(graph_data, model_type="gcn", epochs=100, lr=0.01):
    model = GNNFraudDetector(
        input_dim=graph_data.num_node_features,
        hidden_dim=64,
        output_dim=2,
        model_type=model_type,
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = torch.nn.CrossEntropyLoss()

    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        out = model(graph_data.x, graph_data.edge_index)
        loss = criterion(out, graph_data.y)
        loss.backward()
        optimizer.step()
        print(f"Epoch {epoch+1}/{epochs}, Loss: {loss.item():.4f}")

    torch.save(model.state_dict(), "ml/models/gnn_model.pt")
    print("Model saved to ml/models/gnn_model.pt")

# Example usage
def build_and_train_gnn():
    # Placeholder for graph data loading
    graph_data = Data(
        x=torch.rand(100, 16),  # 100 nodes, 16 features each
        edge_index=torch.randint(0, 100, (2, 500)),  # 500 edges
        y=torch.randint(0, 2, (100,)),  # Binary labels
    )
    train_gnn_model(graph_data, model_type="gcn")