from app.config import Settings, mask_secret, parse_env_file
from tests.conftest import BASE_ENV


def test_parse_env_file_handles_quotes_comments_and_export(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n"
        "DECISION_A=plain # inline comment\n"
        'DECISION_B="quoted # not a comment"\n'
        "export DECISION_C=exported\n"
        "INVALID_LINE\n",
        encoding="utf-8",
    )
    values = parse_env_file(env)
    assert values == {"DECISION_A": "plain", "DECISION_B": "quoted # not a comment", "DECISION_C": "exported"}


def test_provider_enabled_only_when_listed_and_configured():
    settings = Settings.from_env(BASE_ENV)
    assert settings.providers["laya"].enabled
    assert settings.providers["openrouter"].enabled
    assert settings.providers["typesafe"].disabled_reason == "không có trong DECISION_ENABLED_PROVIDERS"


def test_listed_provider_missing_key_is_disabled_not_fatal():
    settings = Settings.from_env({**BASE_ENV, "DECISION_OPENROUTER_API_KEY": ""})
    assert not settings.providers["openrouter"].enabled
    assert "API_KEY" in settings.providers["openrouter"].disabled_reason
    assert settings.providers["laya"].enabled


def test_listed_provider_missing_endpoint_is_disabled():
    settings = Settings.from_env({**BASE_ENV, "DECISION_ENABLED_PROVIDERS": "laya,typesafe", "DECISION_TYPESAFE_API_KEY": "k" * 20})
    assert "ENDPOINT" in settings.providers["typesafe"].disabled_reason


def test_invalid_numeric_config_disables_provider():
    settings = Settings.from_env({**BASE_ENV, "DECISION_OPENROUTER_TIMEOUT_S": "abc"})
    assert not settings.providers["openrouter"].enabled
    assert "TIMEOUT_S" in settings.providers["openrouter"].disabled_reason


def test_custom_jev_provider_is_config_only():
    settings = Settings.from_env({
        **BASE_ENV,
        "DECISION_ENABLED_PROVIDERS": "laya,my-gateway",
        "DECISION_MY_GATEWAY_ENDPOINT": "https://gw.test/decide",
        "DECISION_MY_GATEWAY_API_KEY": "secret-key-123456",
        "DECISION_MY_GATEWAY_DEFAULT_MODEL": "jev-x",
    })
    gateway = settings.providers["my-gateway"]
    assert gateway.enabled
    assert gateway.adapter == "jev_native"
    assert not gateway.verified


def test_unknown_adapter_disables_provider():
    settings = Settings.from_env({**BASE_ENV, "DECISION_LAYA_ADAPTER": "magic"})
    assert not settings.providers["laya"].enabled


def test_mask_secret_and_repr_never_expose_key():
    key = "sk-or-v1-8619a18279c032efe168bd"
    assert key not in mask_secret(key)
    settings = Settings.from_env({**BASE_ENV, "DECISION_OPENROUTER_API_KEY": key})
    assert key not in repr(settings.providers["openrouter"])
