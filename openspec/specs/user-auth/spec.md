# user-auth Specification

## Purpose

让客户端用用户名和密码注册、登录，并用签发的 JWT 访问受保护接口；请求处理过程中任意一层都能取出当前用户身份，而不必沿调用链传递。

## Requirements

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

### Requirement: Protected routes require a valid bearer token

The system SHALL reject requests to mounted application routes other than register, login, OpenAPI documentation, and CORS preflight unless they include a valid `Authorization: Bearer` JWT signed with the configured secret and not expired. On success the system SHALL make the token's user id and username available for the rest of that request without querying the user table. Missing, malformed, or expired tokens MUST be rejected.

#### Scenario: Request without a token is rejected

- **WHEN** the client sends `POST /files/presign` without an `Authorization` header
- **THEN** the system returns an HTTP client error and does not issue an upload URL

#### Scenario: Valid token allows a protected route

- **WHEN** the client sends `POST /files/presign` with a valid Bearer JWT and a valid file declaration
- **THEN** the system processes the request as an authenticated user

#### Scenario: Expired or invalid token is rejected

- **WHEN** the client sends a request to a protected route with a Bearer token that is expired or not signed with the configured secret
- **THEN** the system returns an HTTP client error

### Requirement: Current user is readable anywhere in the request

During a request that passed JWT validation, application code SHALL be able to read the current user id and username without receiving those values as function parameters from the HTTP handler. Code running after the HTTP response has been sent, including background tasks, MUST NOT rely on that request-scoped identity remaining available.

#### Scenario: Nested service reads the signed-in username

- **WHEN** a protected request is being handled and a nested service asks for the current user
- **THEN** it receives the same user id and username that were in the JWT, without a database lookup

#### Scenario: Documentation stays reachable without a token

- **WHEN** the client requests the OpenAPI documentation path without an `Authorization` header
- **THEN** the system does not reject the request for missing authentication
