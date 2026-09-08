## MODIFIED Requirements

### Requirement: Client can request a temporary upload URL

The system SHALL accept `POST /files/presign` with `filename`, `content_type`, and `size` declared by the client. When the declaration is valid, the system SHALL return a time-limited `upload_url`, a unique `object_key`, and `expires_in` seconds. The file bytes MUST NOT pass through this service. The `object_key` MUST include the original filename so it can be recovered later. The `object_key` MUST place that filename under a unique per-file prefix so later companion objects (such as extracted images) can share the same prefix.

#### Scenario: Valid PDF request receives a presigned URL

- **WHEN** the client sends `POST /files/presign` with filename `notes.pdf`, content type `application/pdf`, and size `1048576`
- **THEN** the system returns an HTTP success response containing `upload_url`, an `object_key` that includes `notes.pdf` under a unique prefix folder, and a positive `expires_in`

#### Scenario: Valid Markdown request accepts plain text content type

- **WHEN** the client sends `POST /files/presign` with filename `readme.md`, content type `text/plain`, and size `2048`
- **THEN** the system returns an HTTP success response containing `upload_url`, `object_key`, and `expires_in`

#### Scenario: Valid PNG request receives a presigned URL

- **WHEN** the client sends `POST /files/presign` with filename `photo.png`, content type `image/png`, and size `1024`
- **THEN** the system returns an HTTP success response containing `upload_url`, an `object_key` that includes `photo.png` under a unique prefix folder, and a positive `expires_in`

#### Scenario: Valid DOCX request receives a presigned URL

- **WHEN** the client sends `POST /files/presign` with filename `report.docx`, content type `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, and size `2048`
- **THEN** the system returns an HTTP success response containing `upload_url`, `object_key`, and `expires_in`

### Requirement: Presign validates declared type and size

The system SHALL reject `POST /files/presign` unless all of the following hold: the filename extension is `.pdf`, `.docx`, `.md`, `.txt`, `.png`, `.jpg`, or `.jpeg`; the declared `content_type` matches that extension (`application/pdf` for `.pdf`; `application/vnd.openxmlformats-officedocument.wordprocessingml.document` for `.docx`; `text/markdown` or `text/plain` for `.md`; `text/plain` for `.txt`; `image/png` for `.png`; `image/jpeg` for `.jpg` and `.jpeg`); and `size` is an integer from 1 through 104857600 inclusive (100 MiB). The system SHALL trust the client declaration and MUST NOT inspect any object in the bucket during this request.

#### Scenario: Disallowed extension is rejected

- **WHEN** the client sends `POST /files/presign` with filename `notes.exe`, content type `application/octet-stream`, and size `1024`
- **THEN** the system returns an HTTP client error and does not return `upload_url`

#### Scenario: Size above 100 MiB is rejected

- **WHEN** the client sends `POST /files/presign` with filename `book.pdf`, content type `application/pdf`, and size `104857601`
- **THEN** the system returns an HTTP client error and does not return `upload_url`

#### Scenario: Zero size is rejected

- **WHEN** the client sends `POST /files/presign` with filename `empty.txt`, content type `text/plain`, and size `0`
- **THEN** the system returns an HTTP client error and does not return `upload_url`

#### Scenario: Content type does not match extension

- **WHEN** the client sends `POST /files/presign` with filename `notes.pdf`, content type `text/plain`, and size `1024`
- **THEN** the system returns an HTTP client error and does not return `upload_url`
