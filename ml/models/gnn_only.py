"""
Relation-Aware GNN Baseline Model.
Uses 2-layer SAGEConv per relation (RUR, RSR, RTR), keeps per-relation outputs separate,
and computes a learned relation-weighted sum fused embedding H_fused.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv
from typing import Optional, Dict, Tuple, List


class RelationGNNEncoder(nn.Module):
    def __init__(
        self,
        in_dim: int = 32,
        hidden_dim: int = 128,
        out_dim: int = 128,
        relations: Tuple[str, ...] = ("rur", "rsr", "rtr"),
        dropout: float = 0.2,
        use_sem_in_gnn: bool = False,
        sem_dim: int = 768,
    ):
        super().__init__()
        self.relations = list(relations)
        self.dropout = dropout
        self.use_sem_in_gnn = use_sem_in_gnn

        if use_sem_in_gnn:
            self.sem_proj = nn.Linear(sem_dim, in_dim)
            total_in = in_dim * 2
        else:
            self.sem_proj = None
            total_in = in_dim

        self.input_proj = nn.Linear(total_in, hidden_dim)

        # 2-layer SAGEConv per relation
        self.conv1_dict = nn.ModuleDict({
            rel: SAGEConv(hidden_dim, hidden_dim) for rel in self.relations
        })
        self.conv2_dict = nn.ModuleDict({
            rel: SAGEConv(hidden_dim, out_dim) for rel in self.relations
        })
        self.norms1 = nn.ModuleDict({
            rel: nn.LayerNorm(hidden_dim) for rel in self.relations
        })
        self.norms2 = nn.ModuleDict({
            rel: nn.LayerNorm(out_dim) for rel in self.relations
        })

        # Learned relation importance weights for fused representation
        self.rel_attn_logits = nn.Parameter(torch.zeros(len(self.relations)))

    def forward(
        self,
        x_meta: torch.Tensor,
        edge_index_dict: Dict[str, torch.Tensor],
        x_sem: Optional[torch.Tensor] = None,
    ) -> Tuple[Dict[str, torch.Tensor], torch.Tensor]:
        """
        Returns:
            rel_embeddings: Dict[rel_name, Tensor[N, out_dim]]
            H_fused: Tensor[N, out_dim]
        """
        if self.use_sem_in_gnn and x_sem is not None:
            sem_emb = F.relu(self.sem_proj(x_sem))
            x_in = torch.cat([x_meta, sem_emb], dim=-1)
        else:
            x_in = x_meta

        h0 = F.relu(self.input_proj(x_in))
        h0 = F.dropout(h0, p=self.dropout, training=self.training)

        rel_embeddings = {}
        for rel in self.relations:
            if rel in edge_index_dict and edge_index_dict[rel].numel() > 0:
                ei = edge_index_dict[rel]
                h1 = self.conv1_dict[rel](h0, ei)
                h1 = self.norms1[rel](h1)
                h1 = F.relu(h1)
                h1 = F.dropout(h1, p=self.dropout, training=self.training)

                h2 = self.conv2_dict[rel](h1, ei)
                h2 = self.norms2[rel](h2)
                h2 = F.relu(h2)
            else:
                # If relation is absent / ablated, return zeros
                h2 = torch.zeros((h0.shape[0], self.conv2_dict[self.relations[0]].out_channels),
                                 dtype=h0.dtype, device=h0.device)
            rel_embeddings[rel] = h2

        # Compute learned softmax weights across available relations
        weights = F.softmax(self.rel_attn_logits, dim=0)  # [R]
        stacked = torch.stack([rel_embeddings[rel] for rel in self.relations], dim=1)  # [N, R, D]
        H_fused = (stacked * weights.view(1, -1, 1)).sum(dim=1)  # [N, D]

        return rel_embeddings, H_fused


class GNNOnly(nn.Module):
    def __init__(
        self,
        meta_dim: int = 32,
        hidden_dim: int = 128,
        out_dim: int = 128,
        num_classes: int = 2,
        relations: Tuple[str, ...] = ("rur", "rsr", "rtr"),
        dropout: float = 0.2,
        use_sem_in_gnn: bool = False,
    ):
        super().__init__()
        self.encoder = RelationGNNEncoder(
            in_dim=meta_dim,
            hidden_dim=hidden_dim,
            out_dim=out_dim,
            relations=relations,
            dropout=dropout,
            use_sem_in_gnn=use_sem_in_gnn,
        )
        self.classifier = nn.Sequential(
            nn.Linear(out_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, num_classes)
        )

    def forward(
        self,
        x_meta: torch.Tensor,
        edge_index_dict: Dict[str, torch.Tensor],
        x_sem: Optional[torch.Tensor] = None,
        return_attention: bool = False,
    ) -> torch.Tensor | Tuple[torch.Tensor, Optional[torch.Tensor]]:
        _, H_fused = self.encoder(x_meta=x_meta, edge_index_dict=edge_index_dict, x_sem=x_sem)
        logits = self.classifier(H_fused)
        if return_attention:
            return logits, None
        return logits
