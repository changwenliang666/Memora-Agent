# chat-history Specification

## Purpose

把 Agent 对话持久化为按用户隔离的会话与消息，使已登录用户可以翻历史、跨请求继续同一段对话，并为后续压缩长上下文提供数据基础。

## Requirements

### Requirement: Conversations and messages are persisted per user

The system SHALL store conversations and their messages in MySQL. Each conversation MUST belong to exactly one user. Each message MUST belong to exactly one conversation, MUST record a `role` of `user` or `assistant`, its `content`, and a monotonically increasing `seq` within that conversation. A conversation MUST NOT be readable or writable by a user other than its owner.

#### Scenario: Conversation belongs to one user

- **WHEN** a conversation is created for a signed-in user
- **THEN** it is stored with that user's id and is not returned for a different user

#### Scenario: Message keeps role, content, and order

- **WHEN** a user message and the assistant reply of one turn are stored
- **THEN** each message keeps its `role` and `content`, and their `seq` values reflect the order within the conversation

### Requirement: Streaming turns are written to history

When `POST /chat/stream` carries a valid `conversation_id` owned by the caller, the system SHALL store the turn in that conversation: the user message MUST be stored before streaming starts, and the complete assistant reply MUST be stored when the turn finishes with `message.completed`. When `conversation_id` is omitted, the system SHALL create a new conversation for the caller and store the turn in it. The first `message.started` frame of such a request SHALL include the `conversation_id` alongside the `message_id`. A request that supplies `history` without a `conversation_id` MAY run statelessly and MUST NOT create a conversation.

#### Scenario: Turn with conversation id is stored

- **WHEN** a signed-in user streams a turn with their own `conversation_id` and the turn completes
- **THEN** the user message and the full assistant reply are both stored under that conversation in order

#### Scenario: New conversation is created when id is omitted

- **WHEN** a signed-in user streams a turn without a `conversation_id`
- **THEN** a new conversation is created for that user, the `message.started` frame carries its `conversation_id`, and the turn is stored in it

#### Scenario: Another user's conversation is not writable

- **WHEN** a signed-in user streams with a `conversation_id` owned by a different user
- **THEN** the system rejects the request and does not store the turn into that conversation

### Requirement: Users can read their conversation history

The system SHALL provide `GET /conversations` returning the caller's conversations ordered by most recently updated, and `GET /conversations/{id}/messages` returning that conversation's messages in `seq` order with pagination. Both MUST require a valid bearer JWT. A conversation or message list for an id not owned by the caller MUST NOT be exposed.

#### Scenario: List shows only the caller's conversations

- **WHEN** a signed-in user requests `GET /conversations`
- **THEN** the response contains only that user's conversations

#### Scenario: Messages of another user's conversation are not exposed

- **WHEN** a signed-in user requests `GET /conversations/{id}/messages` for a conversation owned by another user
- **THEN** the system returns an error and does not return its messages

#### Scenario: Messages come back in order

- **WHEN** a signed-in user requests their own conversation's messages
- **THEN** the messages are returned ordered by `seq`
