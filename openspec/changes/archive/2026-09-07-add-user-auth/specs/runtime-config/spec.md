## MODIFIED Requirements

### Requirement: Runtime configuration has a single load entry

The system SHALL load runtime configuration through one entry that returns one startup snapshot. That snapshot MUST expose named configuration groups for MySQL, Redis, RabbitMQ, Qdrant, R2, MinerU, JWT, and the model catalog. Callers MUST read a group directly and MUST NOT need a separate loader or reconstruct a group from flat fields.

#### Scenario: One snapshot contains catalog and secrets

- **WHEN** the application loads runtime configuration
- **THEN** the returned snapshot exposes `mysql`, `redis`, `rabbitmq`, `qdrant`, `r2`, `mineru`, `jwt`, and `llm` groups

#### Scenario: Importing the application does not require complete secrets

- **WHEN** R2 and MinerU environment placeholders are missing or blank
- **THEN** the process can construct the configuration snapshot without crashing

### Requirement: Example environment documents every placeholder

The committed example environment file SHALL list a placeholder for every runtime name the snapshot reads from the environment, including MySQL, Redis, RabbitMQ, R2, MinerU, JWT, and online-model API keys. The example file MUST NOT contain real secret values.

#### Scenario: New middleware names are present

- **WHEN** a developer copies the example environment file
- **THEN** the copy includes names for MySQL, Redis, RabbitMQ, MinerU, R2, JWT, and the configured online-model API key
