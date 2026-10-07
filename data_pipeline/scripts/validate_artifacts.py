"""
Validates that exported artifacts strictly adhere to the contract.
"""

import os
import sys
import torch

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from ml.data import validate_graph_dict, load_clean_graph, get_artifacts_dir


def validate_all_artifacts() -> bool:
    artifacts_dir = get_artifacts_dir()
    print(f"Validating clean YelpChi graph artifacts in {artifacts_dir}...")
    clean_dict = load_clean_graph(artifacts_dir)
    validate_graph_dict(clean_dict, is_variant=False)
    print("Clean graph passed all contract assertions successfully!")
    return True


if __name__ == "__main__":
    validate_all_artifacts()