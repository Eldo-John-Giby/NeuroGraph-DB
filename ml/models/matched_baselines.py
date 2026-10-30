"""Controlled ablations of the deployed single-layer relation model.

All graph branches use the same 14 features, relation edges and hidden width.
These are new real-data baselines, not the older 32-feature MAT experiment.
"""
import torch
from torch import nn
from torch_geometric.nn import SAGEConv

from ml.models.roberta_relation_gnn import RobertaRelationGNN


class MatchedBaseline(nn.Module):
    def __init__(self, variant, text_dim=768, meta_dim=14, hidden_dim=128, dropout=0.2):
        super().__init__()
        if variant not in {"text_only", "graph_only", "concat"}:
            raise ValueError(variant)
        self.variant = variant
        if variant != "graph_only":
            self.text_encoder = nn.Sequential(nn.Linear(text_dim, hidden_dim), nn.LayerNorm(hidden_dim), nn.GELU())
        if variant != "text_only":
            self.meta_encoder = nn.Sequential(nn.Linear(meta_dim, hidden_dim), nn.LayerNorm(hidden_dim), nn.GELU())
            self.relation_convs = nn.ModuleDict({r: SAGEConv(hidden_dim, hidden_dim) for r in ("rur", "rsr", "rtr")})
            self.relation_logits = nn.Parameter(torch.zeros(3))
        width = hidden_dim * (2 if variant == "concat" else 1)
        self.norm = nn.LayerNorm(width)
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Sequential(nn.Linear(width, hidden_dim // 2), nn.GELU(), nn.Dropout(dropout), nn.Linear(hidden_dim // 2, 2))

    def forward(self, x_text, x_meta, edges):
        text = self.text_encoder(x_text) if self.variant != "graph_only" else None
        graph = None
        if self.variant != "text_only":
            seed = self.meta_encoder(x_meta)
            states = torch.stack([torch.relu(conv(seed, edges[r])) for r, conv in self.relation_convs.items()], dim=1)
            graph = (states * torch.softmax(self.relation_logits, dim=0)[None, :, None]).sum(dim=1)
        fused = torch.cat((text, graph), dim=1) if self.variant == "concat" else (text if text is not None else graph)
        return self.classifier(self.dropout(self.norm(fused)))


def build_matched_model(variant, **kwargs):
    return RobertaRelationGNN(**kwargs) if variant == "neurograph" else MatchedBaseline(variant, **kwargs)
