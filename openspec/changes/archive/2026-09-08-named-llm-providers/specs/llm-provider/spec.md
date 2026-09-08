## MODIFIED Requirements

### Requirement: Caller can list configured chat providers

The system SHALL return a mapping from each configured provider instance name to that instance's chat model names. The mapping MUST NOT include embedding model names. Instance names MUST be the catalog table keys, not client-library identifiers.

#### Scenario: Catalog lists ollama and openai chat models

- **WHEN** the model catalog contains ollama, deepseek, and qwen chat models
- **THEN** the listing includes those instance keys and only the chat model names under each

### Requirement: Caller can construct a chat model by provider and name

The system SHALL construct a chat client when given a configured provider instance name and a chat model name from that instance. The client MUST use that instance's `base_url` as written and MUST obtain any online-provider secret from the same runtime configuration snapshot as the catalog. Think and temperature MUST come from the provider table, not from per-model overrides. An unknown instance or a name that is not in that instance's chat model list MUST fail with a clear error.

#### Scenario: Known provider and chat model

- **WHEN** a caller requests provider `deepseek` and a chat model listed under that instance
- **THEN** the constructed client uses that model name and the deepseek `base_url`

#### Scenario: Qwen instance uses its own endpoint

- **WHEN** a caller requests provider `qwen` and a chat model listed under that instance
- **THEN** the constructed client uses that model name and the qwen `base_url`

#### Scenario: Unknown model name

- **WHEN** a caller requests a model name that is not in the instance's chat model list
- **THEN** construction fails with an error that names the instance and the missing model

#### Scenario: Unknown provider

- **WHEN** a caller requests a provider that is not in the catalog
- **THEN** construction fails with an error that names the missing provider

#### Scenario: Retired openai instance name is missing

- **WHEN** a caller requests provider `openai` and the catalog has no `openai` table
- **THEN** construction fails with an error that names the missing provider

#### Scenario: Online provider needs its configured secret

- **WHEN** a caller requests a chat model from an instance whose `type` is `openai` and the environment name in that instance's `api_key_env` is missing or blank
- **THEN** construction fails with an error that names that environment variable

## ADDED Requirements

### Requirement: Client kind comes from the provider table type

The system SHALL select the chat client implementation from the provider table's `type` field, not from the table name. Multiple instances MAY share `type` `openai` and MUST keep independent `base_url` and `api_key_env` values. An unrecognized `type` MUST fail with a clear error that names the instance and the type.

#### Scenario: Two openai-type instances stay independent

- **WHEN** the catalog has `deepseek` and `qwen`, both with `type` `openai`, different `base_url` values, and different `api_key_env` names
- **THEN** requesting `deepseek` with a listed model uses the deepseek `base_url` and secret, and requesting `qwen` with a listed model uses the qwen `base_url` and secret

#### Scenario: Instance name is not the client kind

- **WHEN** a caller requests provider `qwen` whose table has `type` `openai`
- **THEN** construction uses the openai-compatible client for that table

### Requirement: Request provider name is a catalog instance

The system SHALL treat a caller-supplied provider name as a catalog instance key. The system MUST NOT reject a name solely because it is not a built-in client-library identifier. A name that is not a catalog key MUST fail when constructing the client.

#### Scenario: Qwen instance name is accepted

- **WHEN** a chat request names provider `qwen` and that instance exists in the catalog
- **THEN** the request is accepted as a provider name and construction uses the `qwen` table
