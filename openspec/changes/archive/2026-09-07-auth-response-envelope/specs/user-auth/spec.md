## MODIFIED Requirements

### Requirement: Client can register with username and password

The system SHALL accept `POST /auth/register` with only `username` and `password`. The system SHALL store a new user whose password is hashed and MUST NOT persist the plaintext password. Duplicate usernames MUST be rejected. Registration MUST NOT require a JWT. Every handled register outcome MUST be returned as an envelope with `code`, `message`, and `data`. A successful register MUST use the success business code and MUST NOT include the password. A duplicate username MUST use a dedicated non-success business code, MUST NOT create another user, and MUST leave `data` empty.

#### Scenario: New username is registered

- **WHEN** the client sends `POST /auth/register` with a username that is not already stored and a password
- **THEN** the system creates the user and returns an envelope whose `code` is the success business code, whose `data` includes the new user id and username, and which does not include the password

#### Scenario: Duplicate username is rejected

- **WHEN** the client sends `POST /auth/register` with a username that already exists
- **THEN** the system returns an envelope whose `code` is the dedicated duplicate-username business code, does not create another user, and does not include a password in `data`

### Requirement: Client can log in and receive a JWT

The system SHALL accept `POST /auth/login` with only `username` and `password`. When the credentials match a stored user, the system SHALL return a signed JWT whose claims include the user id, the username, and an expiry. Login MUST NOT require a JWT. Invalid credentials MUST be rejected without revealing whether the username exists. Every handled login outcome MUST be returned as an envelope with `code`, `message`, and `data`. A successful login MUST use the success business code and include the JWT in `data`. Invalid credentials MUST use a dedicated non-success business code, MUST NOT return a JWT, and MUST leave `data` empty.

#### Scenario: Valid credentials return a token

- **WHEN** the client sends `POST /auth/login` with a registered username and the matching password
- **THEN** the system returns an envelope whose `code` is the success business code and whose `data` contains a JWT

#### Scenario: Wrong password is rejected

- **WHEN** the client sends `POST /auth/login` with a registered username and a password that does not match
- **THEN** the system returns an envelope whose `code` is the dedicated invalid-credentials business code and whose `data` does not contain a JWT
