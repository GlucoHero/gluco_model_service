import torch
import torch.nn as nn

class DSW_embedding(nn.Module):
    def __init__(self, seg_len, d_model):
        super(DSW_embedding, self).__init__()
        self.seg_len = seg_len
        self.linear = nn.Linear(seg_len, d_model)

    def forward(self, x):
        batch, hl, vars = x.shape
        x = x.reshape(batch, hl // self.seg_len, self.seg_len, vars)
        x = x.permute(0, 1, 3, 2)
        x = self.linear(x)
        return x

class TwoStageAttention(nn.Module):
    def __init__(self, n_heads, d_model, dropout=0.1):
        super(TwoStageAttention, self).__init__()
        self.time_attn = nn.MultiheadAttention(d_model, n_heads, dropout=dropout, batch_first=True)
        self.var_attn = nn.MultiheadAttention(d_model, n_heads, dropout=dropout, batch_first=True)
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        b, s, v, d = x.shape
        x_time = x.permute(0, 2, 1, 3).reshape(b * v, s, d)
        out_time, _ = self.time_attn(x_time, x_time, x_time)
        x = x + self.dropout(out_time.reshape(b, v, s, d).permute(0, 2, 1, 3))
        x = self.norm1(x)
        x_var = x.reshape(b * s, v, d)
        out_var, _ = self.var_attn(x_var, x_var, x_var)
        x = x + self.dropout(out_var.reshape(b, s, v, d))
        x = self.norm2(x)
        return x

class Crossformer(nn.Module):
    def __init__(self, hl, ph, in_channels, d_model=64, n_heads=4, e_layers=3, dropout=0.1):
        super(Crossformer, self).__init__()
        self.seg_len = 24
        self.enc_value_embedding = DSW_embedding(self.seg_len, d_model)
        self.encoder_layers = nn.ModuleList([
            TwoStageAttention(n_heads, d_model, dropout) for _ in range(e_layers)
        ])
        self.projection = nn.Linear(d_model * (hl // self.seg_len) * in_channels, ph)

    def forward(self, x):
        x = self.enc_value_embedding(x)
        for layer in self.encoder_layers:
            x = layer(x)
        x = x.reshape(x.shape[0], -1)
        x = self.projection(x)
        return x
