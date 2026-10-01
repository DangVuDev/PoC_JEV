"""Đọc cấu hình từ .env và biến môi trường (BA mục 5.2).

Biến môi trường của tiến trình luôn thắng giá trị trong file .env. Cấu hình sai của
một provider chỉ làm provider đó bị tắt, không làm server dừng.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

POC_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = POC_ROOT / ".env"

ADAPTER_KINDS = ("jev_native", "noul_decomposition")
STATE_FORMATS = ("string", "object")

_BUILTIN_DEFAULTS: dict[str, dict] = {
    "laya": {
        "endpoint": "http://127.0.0.1:8000/v1/systemone",
        "default_model": "multilingual",
        "adapter": "jev_native",
        "state_format": "string",
        "auth_required": False,
        "verified": True,
        "timeout_s": 60.0,
        "min_interval_s": 0.0,
        "max_retries": 2,
        "max_questions": 64,
    },
    "openrouter": {
        "endpoint": "https://openrouter.ai/api/alpha/decisions",
        "default_model": "respan/span-01-lite:free",
        "adapter": "noul_decomposition",
        "state_format": "string",
        "auth_required": True,
        "verified": True,
        "timeout_s": 60.0,
        "min_interval_s": 1.0,
        "max_retries": 5,
        "max_questions": 64,
    },
    "typesafe": {
        "endpoint": "",
        "default_model": "jev-1.13",
        "adapter": "jev_native",
        "state_format": "string",
        "auth_required": True,
        "verified": False,
        "timeout_s": 60.0,
        "min_interval_s": 0.5,
        "max_retries": 3,
        "max_questions": 64,
    },
    "vercelgateway": {
        "endpoint": "",
        "default_model": "",
        "adapter": "jev_native",
        "state_format": "string",
        "auth_required": True,
        "verified": False,
        "timeout_s": 60.0,
        "min_interval_s": 0.5,
        "max_retries": 3,
        "max_questions": 64,
    },
}

# Provider không có sẵn nhưng được khai báo trong DECISION_ENABLED_PROVIDERS.
_GENERIC_DEFAULTS: dict = {
    "endpoint": "",
    "default_model": "",
    "adapter": "jev_native",
    "state_format": "string",
    "auth_required": True,
    "verified": False,
    "timeout_s": 60.0,
    "min_interval_s": 0.5,
    "max_retries": 3,
    "max_questions": 64,
}


def mask_secret(secret: str) -> str:
    if not secret:
        return ""
    if len(secret) <= 10:
        return "****"
    return f"{secret[:6]}****{secret[-3:]}"


def env_prefix(provider_name: str) -> str:
    return "DECISION_" + re.sub(r"[^A-Za-z0-9]", "_", provider_name).upper() + "_"


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    endpoint: str
    api_key: str
    default_model: str
    adapter: str
    state_format: str
    auth_required: bool
    verified: bool
    timeout_s: float
    min_interval_s: float
    max_retries: int
    max_questions: int
    enabled: bool
    disabled_reason: str | None

    @property
    def api_key_masked(self) -> str:
        return mask_secret(self.api_key)

    def __repr__(self) -> str:  # tránh lộ key khi object bị in ra log
        return f"ProviderConfig(name={self.name!r}, enabled={self.enabled}, adapter={self.adapter!r})"


@dataclass(frozen=True)
class Settings:
    providers: Mapping[str, ProviderConfig]

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        enabled = _split_names(env.get("DECISION_ENABLED_PROVIDERS", "laya,openrouter"))
        names = list(dict.fromkeys([*_BUILTIN_DEFAULTS, *enabled]))
        return cls(providers={name: _build_provider(name, env, name in enabled) for name in names})


def parse_env_file(path: Path) -> dict[str, str]:
    """Đọc file .env tối giản: KEY=VALUE, bỏ dòng '#', hỗ trợ nháy và comment ' #' cuối dòng."""
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].rstrip()
        values[key] = value
    return values


def load_settings(env_file: Path | None = None) -> Settings:
    path = env_file or Path(os.environ.get("DECISION_ENV_FILE", DEFAULT_ENV_FILE))
    file_values = parse_env_file(path) if path.exists() else {}
    return Settings.from_env({**file_values, **os.environ})


def _split_names(raw: str) -> list[str]:
    return [n.strip().lower() for n in raw.split(",") if n.strip()]


def _parse_number(raw: str, cast, default):
    raw = (raw or "").strip()
    if not raw:
        return default
    try:
        return cast(raw)
    except ValueError:
        return None


def _parse_bool(raw: str, default: bool) -> bool | None:
    raw = (raw or "").strip().lower()
    if not raw:
        return default
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return None


def _build_provider(name: str, env: Mapping[str, str], listed: bool) -> ProviderConfig:
    defaults = _BUILTIN_DEFAULTS.get(name, _GENERIC_DEFAULTS)
    prefix = env_prefix(name)

    def get(key: str) -> str:
        return (env.get(prefix + key) or "").strip()

    problems: list[str] = []

    def number(key: str, cast, minimum):
        value = _parse_number(get(key), cast, defaults[key.lower()])
        if value is None or value < minimum:
            problems.append(f"{prefix}{key} không hợp lệ")
            return defaults[key.lower()]
        return value

    adapter = get("ADAPTER") or defaults["adapter"]
    if adapter not in ADAPTER_KINDS:
        problems.append(f"{prefix}ADAPTER phải là một trong {ADAPTER_KINDS}")
    state_format = get("STATE_FORMAT") or defaults["state_format"]
    if state_format not in STATE_FORMATS:
        problems.append(f"{prefix}STATE_FORMAT phải là một trong {STATE_FORMATS}")
    auth_required = _parse_bool(get("AUTH_REQUIRED"), defaults["auth_required"])
    if auth_required is None:
        problems.append(f"{prefix}AUTH_REQUIRED không hợp lệ")
        auth_required = defaults["auth_required"]

    endpoint = get("ENDPOINT") or defaults["endpoint"]
    api_key = get("API_KEY")
    config = dict(
        name=name,
        endpoint=endpoint,
        api_key=api_key,
        default_model=get("DEFAULT_MODEL") or defaults["default_model"],
        adapter=adapter,
        state_format=state_format,
        auth_required=auth_required,
        verified=defaults["verified"],
        timeout_s=number("TIMEOUT_S", float, 0.001),
        min_interval_s=number("MIN_INTERVAL_S", float, 0.0),
        max_retries=number("MAX_RETRIES", int, 0),
        max_questions=number("MAX_QUESTIONS", int, 1),
    )

    if not listed:
        reason = "không có trong DECISION_ENABLED_PROVIDERS"
    elif not endpoint:
        reason = f"thiếu {prefix}ENDPOINT"
    elif auth_required and not api_key:
        reason = f"thiếu {prefix}API_KEY"
    elif problems:
        reason = "; ".join(problems)
    else:
        reason = None
    return ProviderConfig(**config, enabled=reason is None, disabled_reason=reason)
