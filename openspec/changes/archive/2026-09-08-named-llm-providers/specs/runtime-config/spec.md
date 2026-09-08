## MODIFIED Requirements

### Requirement: Secrets and hosts come from the environment, catalog from the model file

The system SHALL parse the project-root `.env` file once per configuration snapshot and overlay process environment variables once, with process values taking precedence. Empty or whitespace-only values MUST be treated as missing. Every named configuration group and online-model secret MUST read from that same merged snapshot. The model catalog MUST come from the existing TOML model file and MUST NOT include secret values. Each provider in that file MUST be a top-level table whose `models` value is a list of chat model name strings. Optional embedding model names MUST live in a separate `embed_models` list on the same table, not in `models`. Each provider table MUST declare a `type` of `ollama` or `openai`. Two openai-type tables MUST be allowed in the same file, each with its own `base_url` and `api_key_env`.

#### Scenario: Process environment overrides the dotenv file

- **WHEN** the same name is set in the process environment and in `.env` with different values
- **THEN** the snapshot uses the process environment value

#### Scenario: Blank placeholder is missing

- **WHEN** an R2 placeholder exists in `.env` but is only whitespace
- **THEN** the snapshot treats that field as missing

#### Scenario: All groups share one environment snapshot

- **WHEN** the application constructs its runtime configuration
- **THEN** middleware, R2, MinerU, and model-secret values are derived from one merged environment snapshot

#### Scenario: Model catalog loads from the TOML file

- **WHEN** the TOML model file has top-level `ollama`, `deepseek`, and `qwen` tables, each with a `type` and a `models` list of name strings
- **THEN** the snapshot's model catalog contains those instance names and those chat model names

#### Scenario: Embedding names are not mixed into chat models

- **WHEN** a provider table lists embedding model names under `embed_models`
- **THEN** those names are absent from that provider's `models` list in the snapshot

#### Scenario: Two openai-type tables keep separate secrets

- **WHEN** the catalog has a `deepseek` table with `api_key_env` `DEEPSEEK_API_KEY` and a `qwen` table with `api_key_env` `QWEN_API_KEY`
- **THEN** the snapshot records those distinct environment names and does not copy either secret into the TOML-backed catalog fields

### Requirement: Example environment documents every placeholder

The committed example environment file SHALL list a placeholder for every runtime name the snapshot reads from the environment, including MySQL, Redis, RabbitMQ, Qdrant, R2, MinerU, JWT, and every online-model API key named by the model catalog. The example file MUST NOT contain real secret values.

#### Scenario: New middleware names are present

- **WHEN** a developer copies the example environment file
- **THEN** the copy includes names for MySQL, Redis, RabbitMQ, Qdrant, MinerU, R2, JWT, `DEEPSEEK_API_KEY`, and `QWEN_API_KEY`

## ADDED Requirements

### Requirement: Provider table type is required at load

The system SHALL reject a model catalog in which any top-level provider table omits `type` or sets `type` to a value other than `ollama` or `openai`. Loading MUST fail before callers can request a model from that table.

#### Scenario: Missing type is rejected

- **WHEN** a provider table omits `type`
- **THEN** catalog loading fails

#### Scenario: Unsupported type is rejected

- **WHEN** a provider table sets `type` to a value other than `ollama` or `openai`
- **THEN** catalog loading fails
