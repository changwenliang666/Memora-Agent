## 1. Group configuration data

- [x] 1.1 Move R2 and MinerU configuration models out of `core/config.py` and add simple MySQL, Redis, RabbitMQ, and Qdrant configuration models in `schema/config.py`; verify every group exposes only fields belonging to that service

## 2. Replace the failed configuration loader

- [x] 2.1 Replace module-level `env()`, `env_int()`, `_load_llm()`, `_settings`, `get_settings()`, and `reset_settings()` with one `Config` class whose constructor accepts env/model file paths; verify `load_env()` parses dotenv once and overlays `os.environ` once
- [x] 2.2 Add explicit `get()`, `get_int()`, `load_mysql()`, `load_redis()`, `load_rabbitmq()`, `load_qdrant()`, `load_r2()`, `load_mineru()`, and `load_llm()` methods; verify a constructed instance exposes the corresponding named groups without flat duplicate fields
- [x] 2.3 Export one production `config = Config()` instance and update files, RAG, chat, and Provider callers to use it directly; verify no source reference to `get_settings`, `reset_settings`, module `env`, or flat R2/MinerU fields remains

## 3. Keep the Provider API simple

- [x] 3.1 Make `LLMProvider` receive a `Config` instance (defaulting to the production instance) and read both catalog and API keys from it; preserve `list_providers()`, `get_model(provider_type, model_name)`, and `get_embeddings(provider_type, model_name)` and verify provider tests cover all three

## 4. Tests and documentation

- [x] 4.1 Rewrite configuration tests to construct `Config(env_file=temporary_file)` explicitly; verify process environment overrides dotenv, dotenv is parsed once, blanks become missing, and every service group has the expected defaults
- [x] 4.2 Update README and configuration documentation to show `config.<group>` and the `Config.load_*()` structure; verify no documentation presents `get_settings()` as the runtime entry
- [x] 4.3 Run `uv run pytest` and OpenSpec strict validation; confirm all tests and change validation pass
