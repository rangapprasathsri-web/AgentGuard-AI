import os
from typing import Any, Dict, Optional
import yaml


def load_department_config(department: str, config_path: str = "config/departments.yaml") -> Dict[str, Any]:
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file {config_path} not found")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    deps = data.get("departments", {})
    if department not in deps:
        raise ValueError(f"Unknown department '{department}'. Available: {list(deps.keys())}")

    return deps[department]
