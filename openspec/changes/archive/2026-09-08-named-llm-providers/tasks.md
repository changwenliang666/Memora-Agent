## 1. Schema and catalog loading

- [x] 1.1 Rename `ProviderType` to `ClientType = Literal["ollama", "openai"]`, add required `ProviderConfig.type: ClientType`, and change `AgentConfig.provider_type` plus `ChatRequest.provider_type` to `str`; verify a table missing `type` or using another value fails in `ProviderConfig.model_validate` with the table name available to `load_llm()`
- [x] 1.2 Keep `Config.load_llm()` iterating top-level TOML tables and validating each into `ProviderConfig`; verify a fixture with `ollama`, `deepseek`, and `qwen` loads three catalog keys and a missing `type` prevents constructing `Config`

## 2. Provider construction by table type

- [x] 2.1 Change `get_model` and `get_embeddings` to branch on `provider.type` instead of the catalog key; verify `get_model("qwen", listed-model)` and `get_model("deepseek", listed-model)` both construct `ChatOpenAI` with that instance's `base_url` and `api_key_env` secret
- [x] 2.2 Preserve unknown-instance and unknown-model errors; verify requesting `"openai"` against a catalog that only has `deepseek`/`qwen` raises an error naming the missing provider, and a missing `QWEN_API_KEY` names that environment variable

## 3. Committed catalog and secrets placeholders

- [x] 3.1 Update `config/models.toml`: add `type` to every table, rename `[openai]` to `[deepseek]`, and add `[qwen]` with DashScope compatible-mode `base_url`, `api_key_env = "QWEN_API_KEY"`, and `models = ["qwen3.8-max"]`; verify `Config` against the committed file lists `ollama`, `deepseek`, and `qwen`
- [x] 3.2 Add `QWEN_API_KEY` placeholder to `.example.env` next to `DEEPSEEK_API_KEY`; verify the example file documents both names and contains no real secret values

## 4. Tests and documentation

- [x] 4.1 Rewrite `tests/core/test_provider.py` fixtures to named instances with `type`, cover two openai-type tables keeping separate secrets, and reject missing `type`; verify `uv run pytest tests/core/test_provider.py` passes
- [x] 4.2 Update `tests/core/test_r2_config.py` and `tests/core/test_chat_schema.py` so catalog assertions use `deepseek`/`qwen` and a chat request may name `qwen`; verify those tests pass
- [x] 4.3 Update README examples so callers use `"deepseek"` or `"qwen"` instead of `"openai"`, and show the `type` field on each TOML table; verify no remaining docs tell callers to pass `provider_type: "openai"`
- [ ] 4.4 Run `uv run pytest` and `openspec validate --change named-llm-providers --strict`; verify both succeed
