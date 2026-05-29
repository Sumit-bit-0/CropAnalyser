import torch.nn as nn


class CropMLP(nn.Module):
    """Small MLP: soil/climate features -> crop class logits."""

    def __init__(self, in_features: int, n_classes: int, hidden=(64, 32)):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_features, hidden[0]), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(hidden[0], hidden[1]), nn.ReLU(),
            nn.Linear(hidden[1], n_classes),
        )

    def forward(self, x):
        return self.net(x)
