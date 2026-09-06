from uuid import uuid4

import boto3

from memora_agent.core.config import R2Config

PRESIGN_EXPIRES_IN = 900


class R2ConfigError(RuntimeError):
    """R2 环境变量未填齐，无法签发地址。"""


class PresignResult:
    def __init__(self, upload_url: str, object_key: str, expires_in: int) -> None:
        self.upload_url = upload_url
        self.object_key = object_key
        self.expires_in = expires_in


class R2Storage:
    def __init__(self, config: R2Config, client=None) -> None:
        self._config = config
        self._client = client

    def _require_config(self) -> None:
        if not self._config.is_complete():
            raise R2ConfigError("R2 配置不完整，请填写 .env 中的 R2 占位")

    def _s3_client(self):
        if self._client is not None:
            return self._client
        return boto3.client(
            "s3",
            endpoint_url=self._config.endpoint_url,
            aws_access_key_id=self._config.access_key_id,
            aws_secret_access_key=self._config.secret_access_key,
            region_name="auto",
        )

    def presign_put(self, filename: str, content_type: str) -> PresignResult:
        """本地 HMAC 签发 PUT 地址，这一步不访问 Cloudflare。

        密钥留在服务端；前端只拿到一段短时有效的 URL，文件字节也不经过本进程。
        """
        self._require_config()
        object_key = f"{uuid4()}{filename}"
        prefix = (self._config.key_prefix or "").strip("/")
        if prefix:
            object_key = f"{prefix}/{object_key}"
        upload_url = self._s3_client().generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._config.bucket_name,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=PRESIGN_EXPIRES_IN,
        )
        return PresignResult(
            upload_url=upload_url,
            object_key=object_key,
            expires_in=PRESIGN_EXPIRES_IN,
        )
