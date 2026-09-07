## MODIFIED Requirements

### Requirement: R2 credentials are supplied by environment placeholders

The system SHALL obtain R2 account id, access key id, secret access key, and bucket name from the unified runtime configuration snapshot. That snapshot MUST take these values from environment placeholders (process environment, then project-root `.env`). The system MUST NOT require these secret values to be committed in source or TOML model config. Incomplete R2 fields MUST NOT prevent the process from starting; `POST /files/presign` and `POST /files/complete` MUST fail with a server error when the snapshot's R2 fields are incomplete.

#### Scenario: Presign uses configured environment values

- **WHEN** the environment placeholders for R2 are filled in and the client sends a valid `POST /files/presign`
- **THEN** the system issues `upload_url` using those configured values

#### Scenario: Incomplete R2 configuration fails at the HTTP boundary

- **WHEN** R2 environment placeholders are missing or blank and the client sends a valid `POST /files/presign`
- **THEN** the system returns an HTTP server error and does not crash during import
