## Purpose

让调用方列出已配置的聊天模型供应商，并用供应商类型加模型名构造客户端，向量模型与聊天模型分开获取。

## ADDED Requirements

### Requirement: Caller can list configured chat providers

The system SHALL return a mapping from each configured provider name to that provider's chat model names. The mapping MUST NOT include embedding model names.

#### Scenario: Catalog lists ollama and openai chat models

- **WHEN** the model catalog contains ollama and openai chat models
- **THEN** the listing includes those provider keys and only the chat model names under each

### Requirement: Caller can construct a chat model by provider and name

The system SHALL construct a chat client when given a configured provider name and a chat model name from that provider. The client MUST use the catalog `base_url` as written and MUST obtain any online-provider secret from the same runtime configuration snapshot as the catalog. Think and temperature MUST come from the provider table, not from per-model overrides. An unknown provider or a name that is not in that provider's chat model list MUST fail with a clear error.

#### Scenario: Known provider and chat model

- **WHEN** a caller requests provider `openai` and a chat model listed under that provider
- **THEN** the constructed client uses that model name and the provider `base_url`

#### Scenario: Unknown model name

- **WHEN** a caller requests a model name that is not in the provider's chat model list
- **THEN** construction fails with an error that names the provider and the missing model

#### Scenario: Unknown provider

- **WHEN** a caller requests a provider that is not in the catalog
- **THEN** construction fails with an error that names the missing provider

#### Scenario: Online provider needs its configured secret

- **WHEN** a caller requests an openai-compatible chat model and the environment name in that provider's `api_key_env` is missing or blank
- **THEN** construction fails with an error that names that environment variable

### Requirement: Embeddings are constructed separately from chat models

The system SHALL construct an embedding client only through an embeddings entry that takes a provider name and an embedding model name from that provider's `embed_models` list. Requesting an embedding model name through the chat-model entry MUST fail.

#### Scenario: Known embedding model

- **WHEN** a caller requests embeddings for a name listed in a provider's `embed_models`
- **THEN** the constructed client uses that model name and the provider `base_url`

#### Scenario: Embedding name rejected by chat entry

- **WHEN** a caller requests a chat model using a name that exists only in `embed_models`
- **THEN** construction fails with an error that names the provider and the missing model
