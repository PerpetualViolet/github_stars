from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import yaml


@dataclass
class ProjectConfig:
    project_root: Path
    config_path: Path
    categories_path: Path
    raw_output: Path
    normalized_output: Path
    classification_dir: Path
    audit_dir: Path
    github_user: str
    github_token_env: str
    llm_api_key_env: str
    llm_provider: str
    llm_base_url: str
    llm_endpoint: str
    llm_model: str
    llm_structured_output: str
    llm_temperature: float
    browser_debug_port: int
    browser_engine: str

    @property
    def github_token(self) -> str | None:
        return os.getenv(self.github_token_env)

    @property
    def llm_api_key(self) -> str | None:
        return os.getenv(self.llm_api_key_env)

    @property
    def categories(self) -> list[dict]:
        if not self.categories_path.exists():
            return []
        payload = yaml.safe_load(self.categories_path.read_text(encoding="utf-8")) or {}
        return payload.get("categories", [])

    @property
    def category_names(self) -> list[str]:
        return [item["name"] for item in self.categories if item.get("name")]


def load_config(config_path: str | Path) -> ProjectConfig:
    config_file = Path(config_path).resolve()
    project_root = config_file.parent.parent
    payload = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}

    data_cfg = payload.get("data", {})
    github_cfg = payload.get("github", {})
    llm_cfg = payload.get("llm", {})
    classification_cfg = payload.get("classification", {})
    browser_cfg = payload.get("browser", {})

    return ProjectConfig(
        project_root=project_root,
        config_path=config_file,
        categories_path=project_root / classification_cfg.get("categories_file", "config/categories.example.yaml"),
        raw_output=project_root / data_cfg.get("raw_output", "data/raw/stars.json"),
        normalized_output=project_root / data_cfg.get("normalized_output", "data/normalized/stars.normalized.json"),
        classification_dir=project_root / data_cfg.get("classification_dir", "data/classification"),
        audit_dir=project_root / data_cfg.get("audit_dir", "data/audit"),
        github_user=github_cfg.get("user", ""),
        github_token_env=github_cfg.get("token_env", "GITHUB_TOKEN"),
        llm_api_key_env=llm_cfg.get("api_key_env", "OPENAI_API_KEY"),
        llm_provider=llm_cfg.get("provider", "openai_compatible"),
        llm_base_url=llm_cfg.get("base_url", "https://api.openai.com/v1"),
        llm_endpoint=llm_cfg.get("endpoint", "chat_completions"),
        llm_model=llm_cfg.get("model", "gpt-5"),
        llm_structured_output=llm_cfg.get("structured_output", "json_object"),
        llm_temperature=float(llm_cfg.get("temperature", 0.1)),
        browser_debug_port=int(browser_cfg.get("debug_port", 9222)),
        browser_engine=browser_cfg.get("engine", "chrome"),
    )
