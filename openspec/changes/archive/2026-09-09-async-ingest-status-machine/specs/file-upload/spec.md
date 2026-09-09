## MODIFIED Requirements

### Requirement: Client can submit declared upload metadata

The system SHALL accept `POST /files/complete` with `object_key`, `filename`, `content_type`, and `size` declared by the client. The system SHALL persist a knowledge-file row for the signed-in user in `pending` status, enqueue ingest for that row, issue a time-limited download URL for the declared `object_key`, and return the declared fields together with `id`, `status`, `download_url`, and `expires_in`. The system MUST NOT read or delete the object in the bucket and MUST NOT include object bytes in the HTTP response. The `download_url` in this response is for the client and MUST NOT be the ingest worker's fetch address.

#### Scenario: Complete returns the declared file record, a download URL, and pending status

- **WHEN** the client sends `POST /files/complete` with `object_key` `abc/notes.pdf`, filename `notes.pdf`, content type `application/pdf`, and size `1048576`
- **THEN** the system returns an HTTP success response whose body contains the same `object_key`, `filename`, `content_type`, and `size`, plus a knowledge-file `id`, `status` `pending`, a non-empty `download_url`, and a positive `expires_in`

#### Scenario: Complete with missing fields is rejected

- **WHEN** the client sends `POST /files/complete` without `object_key`
- **THEN** the system returns an HTTP client error and does not return `download_url`

## ADDED Requirements

### Requirement: Signed-in user can list their knowledge files

The system SHALL accept `GET /files` from a signed-in user and return that user's knowledge-file summaries in reverse `created_at` order. The response body MUST include `total` (the signed-in user's full file count, not affected by pagination) and `items` (the current page). Each summary MUST include `id`, `status`, `error_message`, `filename`, `object_key`, `content_type`, `size`, `created_at`, `started_at`, `finished_at`, `queue_wait_ms`, and `duration_ms`. Summaries MUST NOT include `markdown`, `plain_text`, or `ocr_results`. The list MUST NOT include other users' files. The system SHALL honor `limit` (default 20, maximum 100) and `offset` (default 0) query parameters.

#### Scenario: Owner sees only their files newest first

- **WHEN** a signed-in user has two knowledge files and another user has one
- **THEN** `GET /files` returns `total` 2 and only the signed-in user's two files in `items`, newest `created_at` first, without body columns

#### Scenario: Limit and offset paginate the list

- **WHEN** a signed-in user has three knowledge files and requests `limit=1` and `offset=1`
- **THEN** the response `items` contains exactly one file, the second newest, and `total` is 3

### Requirement: Signed-in user can read one of their knowledge files by id

The system SHALL accept `GET /files/{id}` from a signed-in user. When the id belongs to that user, the system MUST return the same summary fields as the list endpoint. When the id does not exist or belongs to another user, the system MUST return HTTP 404 and MUST NOT reveal whether the row exists.

#### Scenario: Owner reads their file status

- **WHEN** a signed-in user requests `GET /files/{id}` for a file they uploaded
- **THEN** the response includes that file's `id`, `status`, timing fields, and no body columns

#### Scenario: Other user's file is not found

- **WHEN** a signed-in user requests `GET /files/{id}` for a file owned by someone else
- **THEN** the system returns HTTP 404
