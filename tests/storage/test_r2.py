from memora_agent.core.config import R2Config
from memora_agent.storage.r2 import PRESIGN_EXPIRES_IN, R2ConfigError, R2Storage


class FakeS3Client:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict, int]] = []

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        self.calls.append((operation, Params, ExpiresIn))
        return "https://r2.example/upload"


def make_config() -> R2Config:
    return R2Config(
        account_id="acct123",
        access_key_id="key",
        secret_access_key="secret",
        bucket_name="memora-files",
    )


def test_presign_put_returns_url_key_and_expiry() -> None:
    client = FakeS3Client()
    storage = R2Storage(make_config(), client=client)

    result = storage.presign_put("notes.pdf", "application/pdf")

    assert result.upload_url == "https://r2.example/upload"
    assert result.object_key.endswith("/notes.pdf")
    assert result.expires_in == PRESIGN_EXPIRES_IN
    assert client.calls == [
        (
            "put_object",
            {
                "Bucket": "memora-files",
                "Key": result.object_key,
                "ContentType": "application/pdf",
            },
            PRESIGN_EXPIRES_IN,
        )
    ]


def test_presign_put_uses_key_prefix() -> None:
    client = FakeS3Client()
    config = make_config()
    config.key_prefix = "knowledge-base/"
    storage = R2Storage(config, client=client)

    result = storage.presign_put("notes.pdf", "application/pdf")

    assert result.object_key.startswith("knowledge-base/")
    assert result.object_key.endswith("/notes.pdf")
    assert client.calls[0][1]["Key"] == result.object_key


def test_presign_put_requires_complete_config() -> None:
    storage = R2Storage(R2Config(), client=FakeS3Client())

    try:
        storage.presign_put("notes.pdf", "application/pdf")
    except R2ConfigError as exc:
        assert "R2" in str(exc)
    else:
        raise AssertionError("expected R2ConfigError")
