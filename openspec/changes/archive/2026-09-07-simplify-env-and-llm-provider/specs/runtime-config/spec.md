## MODIFIED Requirements

### Requirement: Runtime configuration has a single load entry

The system SHALL load runtime configuration through one entry that returns one startup snapshot. That snapshot MUST expose named configuration groups for MySQL, Redis, RabbitMQ, Qdrant, R2, MinerU, and the model catalog. Callers MUST read a group directly and MUST NOT need a separate loader or reconstruct a group from flat fields.

#### Scenario: One snapshot contains catalog and secrets

- **WHEN** the application loads runtime configuration
- **THEN** the returned snapshot exposes `mysql`, `redis`, `rabbitmq`, `qdrant`, `r2`, `mineru`, and `llm` groups

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
