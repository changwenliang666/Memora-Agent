# streaming-chat Specification

## Purpose

让已登录用户通过 HTTP 流式接口边生成边收到 Agent 的文本回复；连接断开后可凭消息 id 从中断处继续接收，而不必重新提问或等待整段 JSON。

## Requirements

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

### Requirement: Stream uses named message events

A successful stream SHALL use the SSE `event` field to name each frame. The first frame SHALL be `message.started` whose data contains the `message_id` for this turn. Each text increment SHALL be sent as `message.delta` whose data contains a monotonically increasing `seq` and the `content` string of that increment. A turn that finishes with no further tool calls SHALL end with `message.completed`. The system MUST NOT emit tool start or tool end events. Empty text increments MUST NOT produce `message.delta` frames. Tool-call argument fragments MUST NOT be sent as `message.delta` content.

#### Scenario: Text increments arrive as named delta events then completed

- **WHEN** the model produces a text reply with no tool calls
- **THEN** the client receives one `message.started` frame with a `message_id`, one or more `message.delta` frames with increasing `seq`, followed by `message.completed`, and no tool-related events

#### Scenario: Tool use does not add tool event types

- **WHEN** the model calls a tool and then produces a text reply
- **THEN** any text shown to the client still uses only `message.delta`, the stream still ends with `message.completed`, and the client does not receive tool start or tool end events

### Requirement: Failures after the stream starts are closed with failed

Once the event stream has started, a failure in model invocation or tool execution SHALL be sent as a `message.failed` frame whose data contains a `message` string. That stream MUST NOT also send `message.completed`. Validation failures that occur before the stream starts MUST continue to use a JSON error body, not a `message.failed` frame.

#### Scenario: Model failure after streaming begins

- **WHEN** the event stream has already started and the model or a tool raises
- **THEN** the client receives a `message.failed` frame with a `message` and does not receive `message.completed`

### Requirement: In-flight turn can be resumed after disconnect

The system SHALL store the events of a turn being generated in Redis keyed by its `message_id`, including its status and ordered delta events, with a time-limited expiry. The system SHALL accept `GET /chat/messages/{message_id}` with an optional `from_seq`. When the turn is still generating, the system SHALL replay stored `message.delta` events with `seq` greater than `from_seq` (or all when omitted) and then continue streaming new events for that turn. When the turn already finished, the system SHALL replay the remaining stored events and then send its terminal `message.completed` or `message.failed`. When no such turn exists or it has expired, the system MUST return a JSON client error and MUST NOT start an event stream. The resume route MUST require the same bearer JWT. The system MUST NOT regenerate the model reply in order to answer a resume.

#### Scenario: Reconnect continues from the last received seq

- **WHEN** a client that already received deltas up to `seq` 2 reconnects with `GET /chat/messages/{message_id}?from_seq=2` while the turn is still generating
- **THEN** the response is an event stream that first sends the stored deltas after `seq` 2 and then continues with new deltas for that same turn

#### Scenario: Reconnect to a finished turn returns the remaining events

- **WHEN** a client reconnects with `from_seq` after the turn already completed
- **THEN** the stream replays the stored deltas after `from_seq` and then sends `message.completed`, without invoking the model again

#### Scenario: Unknown or expired message is rejected without streaming

- **WHEN** a client requests `GET /chat/messages/{message_id}` for an id that is not stored or has expired
- **THEN** the system returns a JSON client error and does not open an event stream

### Requirement: Conversation state is supplied by the client

The system SHALL treat each `POST /chat/stream` as stateless. When the body includes `history`, the system SHALL use that list as prior turns before the new `message`. When `history` is omitted or empty, the system MUST NOT inject stored or hardcoded prior turns. The system MUST NOT persist the conversation as a browsable history as part of this request; the Redis turn record is only a short-lived resumable buffer.

#### Scenario: No history means a fresh turn

- **WHEN** a signed-in client sends `POST /chat/stream` with a message and no `history`
- **THEN** the Agent runs without server-injected prior chat turns

#### Scenario: Client history is used as prior turns

- **WHEN** a signed-in client sends `POST /chat/stream` with `history` containing prior user and assistant text turns and a new `message`
- **THEN** the Agent sees those prior turns before the new message
