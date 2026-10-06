"""
NeuroGraph-DB Models Package.
"""

from ml.models.text_only import TextOnlyMLP
from ml.models.gnn_only import GNNOnly, RelationGNNEncoder
from ml.models.concat_fusion import ConcatFusion
from ml.models.neurograph import NeuroGraph

MODEL_REGISTRY = {
    "text_only": TextOnlyMLP,
    "gnn_only": GNNOnly,
    "concat": ConcatFusion,
    "neurograph": NeuroGraph,
}


def build_model(
    model_name: str,
    sem_dim: int = 768,
    meta_dim: int = 32,
    d_model: int = 128,
    dropout: float = 0.2,
    num_heads: int = 4,
    use_sem_in_gnn: bool = False,
    relations: tuple[str, ...] = ("rur", "rsr", "rtr"),
    **kwargs
):
    model_name = model_name.lower()
    if model_name not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model name '{model_name}'. Available: {list(MODEL_REGISTRY.keys())}")

    if model_name == "text_only":
        return TextOnlyMLP(in_dim=sem_dim, hidden_dim=d_model, dropout=dropout)
    elif model_name == "gnn_only":
        return GNNOnly(
            meta_dim=meta_dim,
            hidden_dim=d_model,
            out_dim=d_model,
            relations=relations,
            dropout=dropout,
            use_sem_in_gnn=use_sem_in_gnn,
        )
    elif model_name == "concat":
        return ConcatFusion(
            sem_dim=sem_dim,
            meta_dim=meta_dim,
            d_model=d_model,
            relations=relations,
            dropout=dropout,
            use_sem_in_gnn=use_sem_in_gnn,
        )
    elif model_name == "neurograph":
        return NeuroGraph(
            sem_dim=sem_dim,
            meta_dim=meta_dim,
            d_model=d_model,
            num_heads=num_heads,
            relations=relations,
            dropout=dropout,
            use_sem_in_gnn=use_sem_in_gnn,
        )
