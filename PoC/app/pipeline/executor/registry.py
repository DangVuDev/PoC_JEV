"""ProviderRegistry: service_platform -> ProviderConfig (BA mục 5.1)."""

from __future__ import annotations

from typing import Any

from ...config import ProviderConfig, Settings
from ...errors import ErrorCode, PipelineError
from ...observability import log_event


class ProviderRegistry:
    def __init__(self, settings: Settings):
        self._providers = dict(settings.providers)
        for config in self._providers.values():
            if config.disabled_reason and config.disabled_reason != "không có trong DECISION_ENABLED_PROVIDERS":
                log_event("registry.provider_disabled", provider=config.name, reason=config.disabled_reason)

    def resolve(self, name: str) -> ProviderConfig:
        key = name.strip().lower()
        config = self._providers.get(key)
        if config is None:
            raise PipelineError(
                ErrorCode.UNKNOWN_PROVIDER,
                f"service_platform '{name}' không được hỗ trợ. Các giá trị hợp lệ: {', '.join(sorted(self._providers))}",
            )
        if not config.enabled:
            raise PipelineError(ErrorCode.PROVIDER_NOT_CONFIGURED, f"provider '{key}' chưa sẵn sàng: {config.disabled_reason}")
        return config

    def describe(self) -> list[dict[str, Any]]:
        """Thông tin công khai cho GET /api/v1/providers. Không bao giờ chứa API key thật."""
        return [
            {
                "name": c.name,
                "enabled": c.enabled,
                "disabled_reason": c.disabled_reason,
                "verified": c.verified,
                "adapter": c.adapter,
                "default_model": c.default_model or None,
                "endpoint": c.endpoint or None,
                "api_key": c.api_key_masked or None,
                "min_interval_s": c.min_interval_s,
                "max_retries": c.max_retries,
            }
            for c in self._providers.values()
        ]
