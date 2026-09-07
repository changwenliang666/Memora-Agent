## MODIFIED Requirements

### Requirement: Runtime configuration has a single load entry

The system SHALL load runtime configuration through one entry that returns a single snapshot. That snapshot MUST include the model catalog, object-storage credentials, document-parser credentials, and connection values for MySQL, Redis, RabbitMQ, and Qdrant. Callers MUST NOT need a second loader for any of those groups.

#### Scenario: One snapshot contains catalog and secrets

- **WHEN** the process asks for runtime configuration
- **THEN** the returned snapshot includes the configured model providers and the R2 / MinerU / middleware fields, without a separate load call per group

#### Scenario: Importing the application does not require complete secrets

- **WHEN** R2 and MinerU environment placeholders are missing or blank
- **THEN** the process can import and construct the configuration snapshot without crashing

### Requirement: Example environment documents every placeholder

The committed example environment file SHALL list a placeholder for every runtime name the snapshot reads from the environment, including MySQL, Redis, RabbitMQ, Qdrant, R2, MinerU, and online-model API keys. The example file MUST NOT contain real secret values.

#### Scenario: New middleware names are present

- **WHEN** a developer copies the example environment file
- **THEN** the copy includes names for MySQL, Redis, RabbitMQ, Qdrant, MinerU, R2, and the configured online-model API key
