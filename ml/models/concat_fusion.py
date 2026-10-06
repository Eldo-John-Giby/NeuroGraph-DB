"""
Concatenation Fusion Baseline Model (Baseline B).
Naive fusion: concat(H_sem_proj, H_struc_fused) -> MLP.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Dict, Tuple
from .gnn_only import RelationGNNEncoder



class ConcatFusion(nn.Module):
    def __init__(
        self,
        sem_dim: int = 768,
        meta_dim: int = 32,
        d_model: int = 128,
        num_classes: int = 2,
        relations: Tuple[str, ...] = ("rur", "rsr", "rtr"),
        dropout: float = 0.2,
        use_sem_in_gnn: bool = False,
    ):
        super().__init__()
        self.sem_proj = nn.Sequential(
            nn.Linear(sem_dim, d_model),
            nn.LayerNorm(d_model),
            nn.ReLU(),
            nn.Dropout(dropout)
        )
        self.gnn_encoder = RelationGNNEncoder(
            in_dim=meta_dim,
            hidden_dim=d_model,
            out_dim=d_model,
            relations=relations,
            dropout=dropout,
            use_sem_in_gnn=use_sem_in_gnn,
            sem_dim=sem_dim,
        )
        # Concat text (d_model) + structure fused (d_model) = 2 * d_model
        self.classifier = nn.Sequential(
            nn.Linear(2 * d_model, d_model),
            nn.LayerNorm(d_model),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(d_model, num_classes)
        )

    def forward(
        self,
        x_sem: torch.Tensor,
        x_meta: torch.Tensor,
        edge_index_dict: Dict[str, torch.Tensor],
        return_attention: bool = False,
    ) -> torch.Tensor | Tuple[torch.Tensor, Optional[torch.Tensor]]:
        h_sem = self.sem_proj(x_sem)
        _, h_struc_fused = self.gnn_encoder(x_meta=x_meta, edge_index_dict=edge_index_dict, x_sem=x_sem)
        h_fused = torch.cat([h_sem, h_struc_fused], dim=-1)
        logits = self.classifier(h_fused)
        if return_attention:
            return logits, None
        return logits
