# runtime-config Specification

## Purpose

让进程用一个配置入口同时拿到模型清单、外部密钥和中间件地址，避免 TOML 与环境变量各走一套读取逻辑。

## Requirements

### Requirement: Runtime configuration has a single load entry

The system SHALL load runtime configuration through one entry that returns one startup snapshot. That snapshot MUST expose named configuration groups for MySQL, Redis, RabbitMQ, Qdrant, R2, MinerU, JWT, and the model catalog. Callers MUST read a group directly and MUST NOT need a separate loader or reconstruct a group from flat fields.

#### Scenario: One snapshot contains catalog and secrets

- **WHEN** the application loads runtime configuration
- **THEN** the returned snapshot exposes `mysql`, `redis`, `rabbitmq`, `qdrant`, `r2`, `mineru`, `jwt`, and `llm` groups

#### Scenario: Importing the application does not require complete secrets

- **WHEN** R2 and MinerU environment placeholders are missing or blank
- **THEN** the process can construct the configuration snapshot without crashing

### Requirement: Secrets and hosts come from the environment, catalog from the model file

The system SHALL parse the project-root `.env` file once per configuration snapshot and overlay process environment variables once, with process values taking precedence. Empty or whitespace-only values MUST be treated as missing. Every named configuration group and online-model secret MUST read from that same merged snapshot. The model catalog MUST come from the existing TOML model file and MUST NOT include secret values. Each provider in that file MUST be a top-level table whose `models` value is a list of chat model name strings. Optional embedding model names MUST live in a separate `embed_models` list on the same table, not in `models`.

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

- **WHEN** the TOML model file has top-level `ollama` and `openai` tables, each with a `models` list of name strings
- **THEN** the snapshot's model catalog contains those provider names and those chat model names

#### Scenario: Embedding names are not mixed into chat models

- **WHEN** a provider table lists embedding model names under `embed_models`
- **THEN** those names are absent from that provider's `models` list in the snapshot

### Requirement: Example environment documents every placeholder

The committed example environment file SHALL list a placeholder for every runtime name the snapshot reads from the environment, including MySQL, Redis, RabbitMQ, Qdrant, R2, MinerU, JWT, and online-model API keys. The example file MUST NOT contain real secret values.

#### Scenario: New middleware names are present

- **WHEN** a developer copies the example environment file
- **THEN** the copy includes names for MySQL, Redis, RabbitMQ, Qdrant, MinerU, R2, JWT, and the configured online-model API key

### Requirement: Model provider URLs are used as configured

The system SHALL pass each provider `base_url` to the chat client as written in the model catalog. The system MUST NOT rewrite `localhost` to `127.0.0.1`.

#### Scenario: Localhost in the catalog is unchanged

- **WHEN** the ollama provider `base_url` is `http://localhost:11434`
- **THEN** the constructed ollama client uses `http://localhost:11434`
