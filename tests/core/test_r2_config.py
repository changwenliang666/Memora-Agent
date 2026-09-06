from memora_agent.core.config import load_r2_config


def test_missing_r2_config_fields_are_none(monkeypatch) -> None:
    monkeypatch.setattr(
        "memora_agent.core.config.get_secret",
        lambda name: None,
    )

    config = load_r2_config()

    assert config.account_id is None
    assert config.access_key_id is None
    assert config.secret_access_key is None
    assert config.bucket_name is None
    assert config.key_prefix is None
    assert config.endpoint_url is None
    assert config.is_complete() is False


def test_blank_r2_env_values_are_none(monkeypatch) -> None:
    monkeypatch.setattr(
        "memora_agent.core.config.get_secret",
        lambda name: "   ",
    )

    config = load_r2_config()

    assert config.account_id is None
    assert config.is_complete() is False


def test_complete_r2_config_builds_endpoint(monkeypatch) -> None:
    values = {
        "R2_ACCOUNT_ID": "acct123",
        "R2_ACCESS_KEY_ID": "key",
        "R2_SECRET_ACCESS_KEY": "secret",
        "R2_BUCKET_NAME": "memora-files",
        "R2_KEY_PREFIX": "knowledge-base",
    }
    monkeypatch.setattr(
        "memora_agent.core.config.get_secret",
        lambda name: values.get(name),
    )

    config = load_r2_config()

    assert config.is_complete() is True
    assert config.key_prefix == "knowledge-base"
    assert config.endpoint_url == "https://acct123.r2.cloudflarestorage.com"
