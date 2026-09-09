## MODIFIED Requirements

### Requirement: Successful embedding persists a knowledge file record

When a signed-in user completes an upload, the system SHALL insert one MySQL knowledge-file row in the `pending` status before enqueueing ingest, including the uploader's user id, the original file `object_key`, the declared size, the filename, the declared content type, and created and updated timestamps. Companion image keys, converted markdown, read plain text, and per-image vision results MUST be empty at insert. After vectors have been written successfully, the system SHALL update that same row to `done` and fill converted markdown when the file was converted, the read text when the file was `.txt` or `.md`, a JSON list of per-image vision results when the vision model ran (empty when it did not), and a JSON list of companion image object keys (empty when there are none). Converted markdown MUST retain the converter's original image references even when some figures were skipped for embedding and persistence. The original file address MUST be the `object_key`, not an expiring URL. When embedding or vector upsert fails, the system MUST update that same row to `failed` with a short public error message and MUST NOT leave converted bodies as if ingest succeeded. When splitting produces no chunks, the system MUST still mark the row `done`. The system MUST NOT insert a second row for the same ingest job.

#### Scenario: Converted PDF stores markdown, per-image vision results, and image keys

- **WHEN** a PDF with markdown images is embedded successfully
- **THEN** the stored row contains the original `object_key`, the converted markdown, a JSON list of per-image vision results for kept figures only, and a JSON list of copied image object keys for kept figures only, and its status is `done`

#### Scenario: TXT stores the file text

- **WHEN** a `.txt` file is embedded successfully
- **THEN** the stored row contains the read text, an empty image key list, an empty vision-results list, no converted markdown, and status `done`

#### Scenario: PNG stores one vision result for the file

- **WHEN** a `.png` file is embedded successfully
- **THEN** the stored row contains a one-element vision-results list keyed to the original `object_key`, an empty companion image key list, and status `done`

#### Scenario: Failed embedding marks the existing row failed

- **WHEN** embedding or vector upsert fails after the pending row was inserted
- **THEN** the system does not insert another knowledge file row, and the existing row's status is `failed`

#### Scenario: Empty chunks still complete

- **WHEN** ingest splits the prepared text and produces no chunks
- **THEN** the existing row's status is `done`

## ADDED Requirements

### Requirement: Ingest runs asynchronously from a durable queue

When a signed-in user completes an upload, the HTTP response MUST return before parsing, embedding, or vector upsert finishes. The system SHALL enqueue a durable ingest message that identifies the knowledge-file row and the stable object key. The ingest worker MUST issue a fresh time-limited download URL from the object key at consume time. The message MUST NOT carry an expiring download URL as the long-term fetch address. The ingest worker MUST NOT read request-scoped identity; user id and username MUST be taken from the persisted row and the message payload passed at enqueue time.

#### Scenario: Complete returns before ingest finishes

- **WHEN** a signed-in user completes an upload of a PDF
- **THEN** the HTTP response succeeds while the file row is still `pending` or `processing`, and embedding has not necessarily finished

#### Scenario: Worker fetches with a fresh download URL

- **WHEN** the ingest worker starts a job whose object still exists
- **THEN** it downloads using a download URL issued at consume time for that object key

### Requirement: Knowledge file ingest has a visible status machine

A knowledge file row MUST occupy exactly one of: `pending`, `processing`, `done`, `failed`. Completing an upload MUST create the row as `pending`. When a worker begins ingest it MUST set `processing`, record `started_at`, and store `queue_wait_ms` as the milliseconds between `created_at` and `started_at`. When ingest reaches a terminal state it MUST set `finished_at` and store `duration_ms` as the milliseconds between `started_at` and `finished_at`. A redelivered job that is already `processing` MUST keep the original `started_at` and `queue_wait_ms`. A redelivered job that is already `done` or `failed` MUST NOT run ingest again. Failed rows MUST include a short public `error_message` and MUST NOT include internal exception details in that field.

#### Scenario: Pending moves to processing then done

- **WHEN** ingest of a txt file succeeds
- **THEN** the row was `pending` after complete, became `processing` while work ran, and ends as `done` with both `queue_wait_ms` and `duration_ms` populated

#### Scenario: Processing failure records duration and a public error

- **WHEN** ingest fails after the worker has started
- **THEN** the row is `failed`, `error_message` is a short public message, and `duration_ms` is populated

#### Scenario: Already finished job is not ingested again

- **WHEN** a message for a row that is already `done` is delivered
- **THEN** the worker does not embed again and does not change the stored bodies
