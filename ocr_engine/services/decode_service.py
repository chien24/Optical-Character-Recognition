from __future__ import annotations

from typing import Dict, List

import torch


@torch.no_grad()
def greedy_decode(
    model,
    images: torch.Tensor,
    sos_idx: int,
    eos_idx: int,
    max_len: int = 1500,
) -> torch.Tensor:
    model.eval()
    device = images.device

    enc_out = model.encoder(images)
    B, T, _ = enc_out.size()

    h, c = model.decoder._init_hidden(enc_out)
    coverage = torch.zeros(B, T, device=device)
    input_char = torch.full((B,), sos_idx, dtype=torch.long, device=device)

    preds = []
    finished = torch.zeros(B, dtype=torch.bool, device=device)
    repeat_count = torch.zeros(B, dtype=torch.long, device=device)
    prev_char = torch.full((B,), -1, dtype=torch.long, device=device)

    for _ in range(max_len):
        emb = model.decoder.dropout(model.decoder.embedding(input_char))
        context, _, coverage = model.decoder.attention(enc_out, h, coverage)
        lstm_in = torch.cat([emb, context], dim=1)
        h, c = model.decoder.lstm_cell(lstm_in, (h, c))
        out_in = torch.cat([h, context], dim=1)
        logits = model.decoder.fc_out(out_in)
        input_char = logits.argmax(1)
        input_char[finished] = eos_idx
        preds.append(input_char.clone())

        repeat_count = torch.where(input_char == prev_char, repeat_count + 1, torch.zeros_like(repeat_count))
        prev_char = input_char.clone()
        finished = finished | (input_char == eos_idx) | (repeat_count >= 20)
        if finished.all():
            break

    return torch.stack(preds, dim=1)


def indices_to_string(indices: List[int], idx_to_char: Dict[int, str], eos_idx: int, pad_idx: int, sos_idx: int) -> str:
    result = []
    for idx in indices:
        if idx == eos_idx:
            break
        if idx in (pad_idx, sos_idx):
            continue
        result.append(idx_to_char.get(idx, ""))
    return "".join(result)
