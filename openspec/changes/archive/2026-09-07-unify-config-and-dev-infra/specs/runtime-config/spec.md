## Purpose

让进程用一个配置入口同时拿到模型清单、外部密钥和中间件地址，避免 TOML 与环境变量各走一套读取逻辑。

## ADDED Requirements

### Requirement: Runtime configuration has a single load entry

The system SHALL load runtime configuration through one entry that returns a single snapshot. That snapshot MUST include the model catalog, object-storage credentials, document-parser credentials, and connection values for MySQL, Redis, and RabbitMQ. Callers MUST NOT need a second loader for any of those groups.

#### Scenario: One snapshot contains catalog and secrets

- **WHEN** the process asks for runtime configuration
- **THEN** the returned snapshot includes the configured model providers and the R2 / MinerU / middleware fields, without a separate load call per group

#### Scenario: Importing the application does not require complete secrets

- **WHEN** R2 and MinerU environment placeholders are missing or blank
- **THEN** the process can import and construct the configuration snapshot without crashing

### Requirement: Secrets and hosts come from the environment, catalog from the model file

The system SHALL read secrets and middleware hosts from process environment variables, falling back to a project-root `.env` file when a name is unset in the process environment. Empty or whitespace-only values MUST be treated as missing. The model catalog MUST come from the existing TOML model file and MUST NOT include secret values. The system MUST NOT require secret values to be committed in source or in that TOML file.

#### Scenario: Process environment overrides the dotenv file

- **WHEN** the same name is set in the process environment and in `.env` with different values
- **THEN** the snapshot uses the process environment value

#### Scenario: Blank placeholder is missing

- **WHEN** an R2 placeholder exists in `.env` but is only whitespace
- **THEN** the snapshot treats that field as missing

#### Scenario: Model catalog loads from the TOML file

- **WHEN** the TOML model file lists multiple models under the ollama and openai providers
- **THEN** the snapshot's model catalog contains those provider and model names

### Requirement: Example environment documents every placeholder

The committed example environment file SHALL list a placeholder for every runtime name the snapshot reads from the environment, including MySQL, Redis, RabbitMQ, R2, MinerU, and online-model API keys. The example file MUST NOT contain real secret values.

#### Scenario: New middleware names are present

- **WHEN** a developer copies the example environment file
- **THEN** the copy includes names for MySQL, Redis, RabbitMQ, MinerU, R2, and the configured online-model API key

### Requirement: Model provider URLs are used as configured

The system SHALL pass each provider `base_url` to the chat client as written in the model catalog. The system MUST NOT rewrite `localhost` to `127.0.0.1`.

#### Scenario: Localhost in the catalog is unchanged

- **WHEN** the ollama provider `base_url` is `http://localhost:11434`
- **THEN** the constructed ollama client uses `http://localhost:11434`
