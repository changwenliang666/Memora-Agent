from collections.abc import Iterator
from pathlib import Path

import pytest

from memora_agent.core import config as config_module
from memora_agent.core.config import get_settings


@pytest.fixture(autouse=True)
def isolated_env_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[Path]:
    env_file = tmp_path / ".env"
    env_file.write_text("")
    monkeypatch.setattr(config_module, "ENV_FILE", env_file)
    get_settings.cache_clear()
    yield env_file
    get_settings.cache_clear()
