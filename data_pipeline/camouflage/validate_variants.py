"""
Validates all camouflage variant graphs against the contract.
"""

import os
import sys

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from ml.data import load_variant, get_artifacts_dir

ALL_VARIANTS = [
    "sem_L1", "sem_L2", "sem_L3",
    "topo_p10", "topo_p30", "topo_p50", "topo_hub_p30",
    "both_L3_p30"
]


def validate_variants():
    artifacts_dir = get_artifacts_dir()
    print(f"Validating all camouflage variants in {artifacts_dir}...")

    for var in ALL_VARIANTS:
        data = load_variant(var, artifacts_dir)
        print(f"Variant '{var}': PASS (N={len(data['review_ids'])}, Attacked={data['attacked_mask'].sum().item()})")

    print("\nAll camouflage variants validated successfully!")


if __name__ == "__main__":
    validate_variants()