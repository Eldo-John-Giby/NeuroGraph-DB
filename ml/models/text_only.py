"""
Text-Only Baseline Model (Baseline A).
MLP operating purely on RoBERTa text embeddings (x_sem).
"""

import torch
import torch.nn as nn
from typing import Optional, Dict, Any, Tuple


class TextOnlyMLP(nn.Module):
    def __init__(
        self,
        in_dim: int = 768,
        hidden_dim: int = 128,
        num_classes: int = 2,
        dropout: float = 0.2,
        num_layers: int = 2,
    ):
        super().__init__()
        layers = []
        curr_dim = in_dim
        for i in range(num_layers - 1):
            layers.extend([
                nn.Linear(curr_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
            ])
            curr_dim = hidden_dim
        layers.append(nn.Linear(curr_dim, num_classes))
        self.net = nn.Sequential(*layers)

    def forward(
        self,
        x_sem: torch.Tensor,
        x_meta: Optional[torch.Tensor] = None,
        edge_index_dict: Optional[Dict[str, torch.Tensor]] = None,
        return_attention: bool = False,
    ) -> torch.Tensor | Tuple[torch.Tensor, Optional[torch.Tensor]]:
        logits = self.net(x_sem)
        if return_attention:
            return logits, None
        return logits
