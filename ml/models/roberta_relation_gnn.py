"""Frozen-RoBERTa embedding fusion with relation-specific PyG GraphSAGE layers."""

from __future__ import annotations

from typing import Mapping

import torch
from torch import nn
from torch_geometric.nn import SAGEConv


class RobertaRelationGNN(nn.Module):
    """Classify known YelpChi nodes from text embeddings, metadata, and RUR/RSR/RTR.

    RoBERTa itself is run once in the preprocessing stage.  This model consumes
    its immutable 768-dimensional pooled embeddings, so graph training does not
    repeatedly re-tokenize 45k+ reviews and the served bundle is reproducible.
    """

    def __init__(self, text_dim: int = 768, meta_dim: int = 32, hidden_dim: int = 128, dropout: float = 0.2):
        super().__init__()
        self.relations = ("rur", "rsr", "rtr")
        self.text_encoder = nn.Sequential(nn.Linear(text_dim, hidden_dim), nn.LayerNorm(hidden_dim), nn.GELU())
        self.meta_encoder = nn.Sequential(nn.Linear(meta_dim, hidden_dim), nn.LayerNorm(hidden_dim), nn.GELU())
        self.relation_convs = nn.ModuleDict({name: SAGEConv(hidden_dim, hidden_dim) for name in self.relations})
        self.relation_keys = nn.ModuleDict({name: nn.Linear(hidden_dim, hidden_dim, bias=False) for name in self.relations})
        self.relation_values = nn.ModuleDict({name: nn.Linear(hidden_dim, hidden_dim, bias=False) for name in self.relations})
        self.gate = nn.Sequential(nn.Linear(hidden_dim * 2, hidden_dim), nn.Sigmoid())
        self.norm = nn.LayerNorm(hidden_dim)
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2), nn.GELU(), nn.Dropout(dropout), nn.Linear(hidden_dim // 2, 2)
        )

    def forward(
        self, x_text: torch.Tensor, x_meta: torch.Tensor, edges: Mapping[str, torch.Tensor], return_attention: bool = False
    ) -> torch.Tensor | tuple[torch.Tensor, torch.Tensor]:
        text = self.text_encoder(x_text)
        seed = self.meta_encoder(x_meta)
        relation_states = {name: torch.relu(self.relation_convs[name](seed, edges[name])) for name in self.relations}
        keys = torch.stack([self.relation_keys[name](relation_states[name]) for name in self.relations], dim=1)
        values = torch.stack([self.relation_values[name](relation_states[name]) for name in self.relations], dim=1)
        attention = torch.softmax((keys * text.unsqueeze(1)).sum(dim=-1) / (text.shape[-1] ** 0.5), dim=1)
        graph = (attention.unsqueeze(-1) * values).sum(dim=1)
        gate = self.gate(torch.cat((text, graph), dim=1))
        fused = self.norm(text + gate * self.dropout(graph))
        logits = self.classifier(self.dropout(fused))
        return (logits, attention) if return_attention else logits
