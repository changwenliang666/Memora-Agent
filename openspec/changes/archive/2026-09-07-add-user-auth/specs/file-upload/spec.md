## ADDED Requirements

### Requirement: File upload routes require a signed-in user

The system SHALL reject `POST /files/presign` and `POST /files/complete` unless the request includes a valid Bearer JWT. Missing or invalid authentication MUST fail before the system issues an upload or download URL.

#### Scenario: Presign without a token is rejected

- **WHEN** the client sends `POST /files/presign` with a valid file declaration and no `Authorization` header
- **THEN** the system returns an HTTP client error and does not return `upload_url`

#### Scenario: Complete without a token is rejected

- **WHEN** the client sends `POST /files/complete` with declared metadata and no `Authorization` header
- **THEN** the system returns an HTTP client error and does not return `download_url`
