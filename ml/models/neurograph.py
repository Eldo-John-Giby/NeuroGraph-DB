"""
NeuroGraph-DB Main Multimodal Relation-Aware Model.
Cross-Attention Fusion between RoBERTa Semantic Query and GNN Structural Keys/Values.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Dict, Tuple, List
from .gnn_only import RelationGNNEncoder



class NeuroGraph(nn.Module):
    def __init__(
        self,
        sem_dim: int = 768,
        meta_dim: int = 32,
        d_model: int = 128,
        num_heads: int = 4,
        num_classes: int = 2,
        relations: Tuple[str, ...] = ("rur", "rsr", "rtr"),
        dropout: float = 0.2,
        use_sem_in_gnn: bool = False,
    ):
        super().__init__()
        self.d_model = d_model
        self.num_heads = num_heads
        self.relations = list(relations)

        # 1. Text Semantic Projection (Query)
        self.sem_proj = nn.Sequential(
            nn.Linear(sem_dim, d_model),
            nn.LayerNorm(d_model),
            nn.ReLU(),
            nn.Dropout(dropout),
        )

        # 2. Relation-aware GNN Encoder
        self.gnn_encoder = RelationGNNEncoder(
            in_dim=meta_dim,
            hidden_dim=d_model,
            out_dim=d_model,
            relations=relations,
            dropout=dropout,
            use_sem_in_gnn=use_sem_in_gnn,
            sem_dim=sem_dim,
        )

        # 3. Token projections for Keys/Values: [H_rur, H_rsr, H_rtr, H_fused]
        self.token_projs = nn.ModuleDict({
            rel: nn.Linear(d_model, d_model) for rel in self.relations
        })
        self.fused_token_proj = nn.Linear(d_model, d_model)

        # 4. Multi-Head Cross-Attention
        self.cross_attn = nn.MultiheadAttention(
            embed_dim=d_model,
            num_heads=num_heads,
            dropout=dropout,
            batch_first=True,
        )
        self.norm1 = nn.LayerNorm(d_model)

        # 5. Feed-Forward Network
        self.ffn = nn.Sequential(
            nn.Linear(d_model, 2 * d_model),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(2 * d_model, d_model),
        )
        self.norm2 = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

        # 6. Classification Head
        self.classifier = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(d_model // 2, num_classes)
        )

    def forward(
        self,
        x_sem: torch.Tensor,
        x_meta: torch.Tensor,
        edge_index_dict: Dict[str, torch.Tensor],
        return_attention: bool = False,
    ) -> torch.Tensor | Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass.
        x_sem: [N, sem_dim]
        x_meta: [N, meta_dim]
        edge_index_dict: Dict of edge indices

        Returns:
            logits: [N, num_classes]
            attention_weights (optional): [N, num_tokens] where tokens are [w_rur, w_rsr, w_rtr, w_fused]
        """
        # Query: [N, 1, d_model]
        h_query = self.sem_proj(x_sem).unsqueeze(1)

        # GNN structural embeddings: rel_embeddings (dict), H_fused [N, d_model]
        rel_embs, h_fused = self.gnn_encoder(x_meta=x_meta, edge_index_dict=edge_index_dict, x_sem=x_sem)

        # Build KV tokens: [H_rur, H_rsr, H_rtr, H_fused] -> [N, K, d_model]
        kv_tokens_list = [self.token_projs[rel](rel_embs[rel]) for rel in self.relations]
        kv_tokens_list.append(self.fused_token_proj(h_fused))

        kv_tokens = torch.stack(kv_tokens_list, dim=1)  # [N, num_tokens, d_model]

        # Cross-Attention
        # attn_weights shape: [N, 1, num_tokens] (averaged over heads)
        attn_out, attn_weights = self.cross_attn(
            query=h_query,
            key=kv_tokens,
            value=kv_tokens,
            need_weights=True,
            average_attn_weights=True,
        )

        # Residual + LayerNorm
        h_res = self.norm1(h_query + self.dropout(attn_out))

        # FFN + Residual + LayerNorm
        h_ffn = self.ffn(h_res)
        h_final = self.norm2(h_res + self.dropout(h_ffn)).squeeze(1)  # [N, d_model]

        # Classification
        logits = self.classifier(h_final)

        if return_attention:
            # Squeeze to [N, num_tokens], tokens order: [*relations, "fused"]
            weights = attn_weights.squeeze(1)  # [N, 4]
            return logits, weights
        return logits
