import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

import yaml


@dataclass
class ScrapeConfig:
    include_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)
    context_lines: int = 0
    pages: List[int] = field(default_factory=list)
    fields: Union[Dict[str, str], List[Dict[str, Any]]] = field(default_factory=dict)
    output_path: Optional[str] = None


def load_config(config_path: str) -> ScrapeConfig:
    with open(config_path, "r", encoding="utf-8") as f:
        if config_path.lower().endswith((".yml", ".yaml")):
            data = yaml.safe_load(f) or {}
        elif config_path.lower().endswith(".json"):
            data = json.load(f)
        else:
            # Try YAML first, then JSON
            try:
                f.seek(0)
                data = yaml.safe_load(f) or {}
            except Exception:
                f.seek(0)
                data = json.load(f)

    cfg = ScrapeConfig()
    cfg.include_patterns = list(data.get("include_patterns", []) or [])
    cfg.exclude_patterns = list(data.get("exclude_patterns", []) or [])
    cfg.context_lines = int(data.get("context_lines", 0) or 0)
    cfg.pages = list(data.get("pages", []) or [])
    cfg.fields = data.get("fields", {}) or {}
    cfg.output_path = data.get("output_path")
    return cfg
