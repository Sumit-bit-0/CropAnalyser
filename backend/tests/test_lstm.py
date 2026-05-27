import torch
from models.lstm import PriceLSTM
from config import LSTM_SEQUENCE_LEN, LSTM_FORECAST_LEN

def test_model_output_shape():
    model = PriceLSTM(input_size=2, hidden_size=64, num_layers=2, forecast_len=LSTM_FORECAST_LEN)
    x = torch.randn(8, LSTM_SEQUENCE_LEN, 2)  # batch=8, seq=12, features=2
    out = model(x)
    assert out.shape == (8, LSTM_FORECAST_LEN, 2)

def test_model_is_nn_module():
    from torch import nn
    model = PriceLSTM(input_size=2, hidden_size=64, num_layers=2, forecast_len=LSTM_FORECAST_LEN)
    assert isinstance(model, nn.Module)
