from typing import Dict

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models


IMG_HEIGHT = 256
IMG_WIDTH = 1024
ENCODER_DIM = 512
HIDDEN_DIM = 512
DECODER_DIM = 512
EMBED_DIM = 256

PAD_TOKEN = "<pad>"
SOS_TOKEN = "<sos>"
EOS_TOKEN = "<eos>"
UNK_TOKEN = "<unk>"


class ResNetEncoder(nn.Module):
    def __init__(self, encoder_dim: int = ENCODER_DIM, hidden_dim: int = HIDDEN_DIM):
        super().__init__()
        self.gray_to_rgb = nn.Conv2d(1, 3, kernel_size=1, bias=False)
        nn.init.constant_(self.gray_to_rgb.weight, 1.0 / 3.0)

        resnet = models.resnet50(weights=None)

        self.layer0 = nn.Sequential(resnet.conv1, resnet.bn1, resnet.relu, resnet.maxpool)
        self.layer1 = resnet.layer1
        self.layer2 = resnet.layer2
        self.layer3 = resnet.layer3
        self.layer4 = resnet.layer4

        self.height_pool = nn.AdaptiveAvgPool2d((1, None))

        self.proj = nn.Sequential(
            nn.Conv1d(2048, encoder_dim, kernel_size=1),
            nn.BatchNorm1d(encoder_dim),
            nn.GELU(),
        )

        self.bilstm = nn.LSTM(
            input_size=encoder_dim,
            hidden_size=hidden_dim,
            num_layers=2,
            batch_first=True,
            bidirectional=True,
            dropout=0.1,
        )

        self.output_dim = hidden_dim * 2

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.gray_to_rgb(x)
        x = self.layer0(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)
        x = self.height_pool(x)
        x = x.squeeze(2)
        x = self.proj(x)
        x = x.permute(0, 2, 1)
        x, _ = self.bilstm(x)
        return x


class BahdanauAttention(nn.Module):
    def __init__(self, encoder_dim: int, decoder_dim: int, attn_dim: int = 256):
        super().__init__()
        self.W_enc = nn.Linear(encoder_dim, attn_dim, bias=False)
        self.W_dec = nn.Linear(decoder_dim, attn_dim, bias=False)
        self.W_coverage = nn.Linear(1, attn_dim, bias=False)
        self.v = nn.Linear(attn_dim, 1, bias=False)
        self.tanh = nn.Tanh()

    def forward(self, encoder_out: torch.Tensor, hidden: torch.Tensor, coverage: torch.Tensor = None):
        if coverage is None:
            coverage = torch.zeros(encoder_out.size(0), encoder_out.size(1), device=encoder_out.device)
        energy = self.tanh(
            self.W_enc(encoder_out)
            + self.W_dec(hidden).unsqueeze(1)
            + self.W_coverage(coverage.unsqueeze(-1))
        )
        score = self.v(energy).squeeze(-1)
        alpha = F.softmax(score, dim=-1)
        context = (encoder_out * alpha.unsqueeze(-1)).sum(dim=1)
        new_coverage = coverage + alpha
        return context, alpha, new_coverage


class AttentionDecoder(nn.Module):
    def __init__(self, vocab_size: int, encoder_dim: int, decoder_dim: int = DECODER_DIM,
                 embed_dim: int = EMBED_DIM, pad_idx: int = 0, dropout: float = 0.1):
        super().__init__()
        self.decoder_dim = decoder_dim
        self.vocab_size = vocab_size

        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=pad_idx)
        self.dropout = nn.Dropout(dropout)
        self.attention = BahdanauAttention(encoder_dim, decoder_dim, attn_dim=256)
        self.lstm_cell = nn.LSTMCell(embed_dim + encoder_dim, decoder_dim)
        self.fc_out = nn.Sequential(
            nn.Linear(decoder_dim + encoder_dim, decoder_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(decoder_dim, vocab_size),
        )
        self.init_h = nn.Linear(encoder_dim, decoder_dim)
        self.init_c = nn.Linear(encoder_dim, decoder_dim)

    def _init_hidden(self, encoder_out: torch.Tensor):
        mean_enc = encoder_out.mean(dim=1)
        h = torch.tanh(self.init_h(mean_enc))
        c = torch.tanh(self.init_c(mean_enc))
        return h, c

    def forward(self, encoder_out: torch.Tensor, targets: torch.Tensor, tf_ratio: float = 1.0,
                return_coverage_loss: bool = False):
        B, max_len = targets.size()
        outputs = torch.zeros(B, max_len, self.vocab_size, device=encoder_out.device)
        coverage = torch.zeros(B, encoder_out.size(1), device=encoder_out.device)
        cov_loss = torch.tensor(0.0, device=encoder_out.device)

        h, c = self._init_hidden(encoder_out)
        input_char = targets[:, 0]

        for t in range(1, max_len):
            emb = self.dropout(self.embedding(input_char))
            context, alpha, coverage_new = self.attention(encoder_out, h, coverage)
            cov_loss = cov_loss + torch.min(alpha, coverage).sum(dim=1).mean()
            coverage = coverage_new
            lstm_in = torch.cat([emb, context], dim=1)
            h, c = self.lstm_cell(lstm_in, (h, c))
            out_in = torch.cat([h, context], dim=1)
            logits = self.fc_out(out_in)
            outputs[:, t] = logits
            use_gt = torch.rand(1).item() < tf_ratio
            input_char = targets[:, t] if use_gt else logits.argmax(1)

        cov_loss = cov_loss / (max_len - 1)
        if return_coverage_loss:
            return outputs, cov_loss
        return outputs


class OCRModel(nn.Module):
    def __init__(self, vocab_size: int, pad_idx: int, encoder_dim: int = ENCODER_DIM,
                 hidden_dim: int = HIDDEN_DIM, decoder_dim: int = DECODER_DIM, embed_dim: int = EMBED_DIM):
        super().__init__()
        self.encoder = ResNetEncoder(encoder_dim=encoder_dim, hidden_dim=hidden_dim)
        sequence_dim = hidden_dim * 2
        self.decoder = AttentionDecoder(
            vocab_size=vocab_size,
            encoder_dim=sequence_dim,
            decoder_dim=decoder_dim,
            embed_dim=embed_dim,
            pad_idx=pad_idx,
        )

    def forward(self, images: torch.Tensor, targets: torch.Tensor, tf_ratio: float = 1.0,
                return_coverage_loss: bool = False):
        enc_out = self.encoder(images)
        return self.decoder(enc_out, targets, tf_ratio=tf_ratio, return_coverage_loss=return_coverage_loss)


def _infer_vocab_size_from_state(state_dict: Dict) -> int:
    key = "decoder.embedding.weight"
    if key in state_dict:
        return state_dict[key].shape[0]
    raise KeyError(f"Key '{key}' not found in state dict.")
