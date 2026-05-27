import torch
import torch.nn as nn


class PriceLSTM(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, num_layers: int, forecast_len: int):
        super().__init__()
        self.forecast_len = forecast_len
        self.input_size = input_size
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.2)
        self.fc = nn.Linear(hidden_size, input_size * forecast_len)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq_len, input_size)
        out, _ = self.lstm(x)
        last = out[:, -1, :]                        # (batch, hidden_size)
        pred = self.fc(last)                         # (batch, input_size * forecast_len)
        return pred.view(-1, self.forecast_len, self.input_size)
