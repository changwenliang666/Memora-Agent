## Purpose

`POST /chat/stream` 在已登录用户请求时，把本轮对话写入其会话历史，并在首帧给出会话 id，使流式回复可被持久化与继续。

## MODIFIED Requirements

### Requirement: Authenticated client can open a streaming chat

The system SHALL accept `POST /chat/stream` with a JSON body that includes `message`, `provider_type`, and `model_name`, and MAY include a `conversation_id`. The route MUST remain behind the existing bearer JWT requirement. Missing or invalid authentication MUST be rejected before a stream starts. When `provider_type` or `model_name` is missing, the system MUST reject the request with a non-stream JSON error and MUST NOT start an event stream. When `conversation_id` is supplied, it MUST reference a conversation owned by the caller; otherwise the request MUST be rejected before a stream starts. When `conversation_id` is omitted, the system MUST create a new conversation for the caller before streaming. The first `message.started` frame SHALL include both the `message_id` for resumable streaming and the `conversation_id` for the persisted turn.

#### Scenario: Valid request starts an event stream

- **WHEN** a signed-in client sends `POST /chat/stream` with a non-empty `message`, a configured `provider_type`, and a configured `model_name`
- **THEN** the response is an event stream (`text/event-stream`) rather than a single JSON chat payload

#### Scenario: Missing model selection is rejected without streaming

- **WHEN** a signed-in client sends `POST /chat/stream` with a `message` but without `provider_type` or `model_name`
- **THEN** the system returns a JSON error and does not open an event stream

#### Scenario: Request without a token is rejected

- **WHEN** the client sends `POST /chat/stream` without a valid Bearer JWT
- **THEN** the system returns an HTTP client error and does not open an event stream

#### Scenario: Started frame carries conversation id

- **WHEN** a signed-in client opens a valid stream
- **THEN** the first `message.started` frame contains both a `message_id` and the `conversation_id` for the turn
