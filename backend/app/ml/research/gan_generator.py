import torch
import torch.nn as nn
import pandas as pd

# Generator Network
class Generator(nn.Module):
    def __init__(self, input_dim, output_dim):
        super(Generator, self).__init__()
        self.model = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 256),
            nn.ReLU(),
            nn.Linear(256, output_dim),
            nn.Sigmoid(),
        )

    def forward(self, z):
        return self.model(z)

# Discriminator Network
class Discriminator(nn.Module):
    def __init__(self, input_dim):
        super(Discriminator, self).__init__()
        self.model = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        return self.model(x)

# Train GAN
def train_gan(fraud_data, epochs=100, batch_size=32, z_dim=16):
    generator = Generator(z_dim, fraud_data.shape[1])
    discriminator = Discriminator(fraud_data.shape[1])

    g_optimizer = torch.optim.Adam(generator.parameters(), lr=0.0002)
    d_optimizer = torch.optim.Adam(discriminator.parameters(), lr=0.0002)

    criterion = nn.BCELoss()

    for epoch in range(epochs):
        for _ in range(len(fraud_data) // batch_size):
            # Train Discriminator
            real_data = torch.tensor(fraud_data.sample(batch_size).values, dtype=torch.float32)
            z = torch.randn(batch_size, z_dim)
            fake_data = generator(z)

            real_labels = torch.ones(batch_size, 1)
            fake_labels = torch.zeros(batch_size, 1)

            d_loss_real = criterion(discriminator(real_data), real_labels)
            d_loss_fake = criterion(discriminator(fake_data.detach()), fake_labels)
            d_loss = d_loss_real + d_loss_fake

            d_optimizer.zero_grad()
            d_loss.backward()
            d_optimizer.step()

            # Train Generator
            g_loss = criterion(discriminator(fake_data), real_labels)

            g_optimizer.zero_grad()
            g_loss.backward()
            g_optimizer.step()

        print(f"Epoch {epoch+1}/{epochs}, D Loss: {d_loss.item():.4f}, G Loss: {g_loss.item():.4f}")

    # Generate synthetic data
    z = torch.randn(len(fraud_data), z_dim)
    synthetic_data = generator(z).detach().numpy()
    synthetic_df = pd.DataFrame(synthetic_data, columns=fraud_data.columns)
    synthetic_df.to_csv("data/synthetic_fraud_dataset.csv", index=False)
    print("Synthetic fraud dataset saved to data/synthetic_fraud_dataset.csv")