"""Multi-crop yield regressor: categorical embeddings + scaled year -> yield (z)."""
import torch
import torch.nn as nn


def _emb_dim(vocab: int) -> int:
    return min(50, (vocab + 1) // 2 + 1)


class YieldMLP(nn.Module):
    def __init__(self, vocab_sizes: dict, hidden=(128, 64)):
        super().__init__()
        self.cols = list(vocab_sizes.keys())
        self.embs = nn.ModuleDict({
            # +1 row for the unknown id (0)
            c: nn.Embedding(v + 1, _emb_dim(v)) for c, v in vocab_sizes.items()
        })
        in_dim = sum(_emb_dim(v) for v in vocab_sizes.values()) + 1  # +1 = year
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden[0]), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(hidden[0], hidden[1]), nn.ReLU(),
            nn.Linear(hidden[1], 1),
        )

    def forward(self, cats: dict, year: torch.Tensor) -> torch.Tensor:
        parts = [self.embs[c](cats[c]) for c in self.cols]
        x = torch.cat(parts + [year], dim=1)
        return self.net(x).squeeze(1)
