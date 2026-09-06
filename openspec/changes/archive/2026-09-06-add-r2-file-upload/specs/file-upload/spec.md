## Purpose

让前端把允许的文档直传到 Cloudflare R2：先向本服务申请临时上传地址，上传完成后再把申报的文件信息交给本服务整理返回。本服务不接收文件字节，也不在本次持久化这些信息。

## ADDED Requirements

### Requirement: Client can request a temporary upload URL

The system SHALL accept `POST /files/presign` with `filename`, `content_type`, and `size` declared by the client. When the declaration is valid, the system SHALL return a time-limited `upload_url`, a unique `object_key`, and `expires_in` seconds. The file bytes MUST NOT pass through this service. The `object_key` MUST include the original filename so it can be recovered later.

#### Scenario: Valid PDF request receives a presigned URL

- **WHEN** the client sends `POST /files/presign` with filename `notes.pdf`, content type `application/pdf`, and size `1048576`
- **THEN** the system returns an HTTP success response containing `upload_url`, an `object_key` that includes `notes.pdf`, and a positive `expires_in`

#### Scenario: Valid Markdown request accepts plain text content type

- **WHEN** the client sends `POST /files/presign` with filename `readme.md`, content type `text/plain`, and size `2048`
- **THEN** the system returns an HTTP success response containing `upload_url`, `object_key`, and `expires_in`

### Requirement: Presign validates declared type and size

The system SHALL reject `POST /files/presign` unless all of the following hold: the filename extension is `.pdf`, `.md`, or `.txt`; the declared `content_type` matches that extension (`application/pdf` for `.pdf`; `text/markdown` or `text/plain` for `.md`; `text/plain` for `.txt`); and `size` is an integer from 1 through 104857600 inclusive (100 MiB). The system SHALL trust the client declaration and MUST NOT inspect any object in the bucket during this request.

#### Scenario: Disallowed extension is rejected

- **WHEN** the client sends `POST /files/presign` with filename `photo.png`, content type `image/png`, and size `1024`
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

### Requirement: Client can submit declared upload metadata

The system SHALL accept `POST /files/complete` with `object_key`, `filename`, `content_type`, and `size` declared by the client. The system SHALL return these fields as a structured file record. The system MUST NOT read or delete the object in the bucket, MUST NOT persist the record, and MUST NOT issue a download URL.

#### Scenario: Complete returns the declared file record

- **WHEN** the client sends `POST /files/complete` with `object_key` `abc/notes.pdf`, filename `notes.pdf`, content type `application/pdf`, and size `1048576`
- **THEN** the system returns an HTTP success response whose body contains the same `object_key`, `filename`, `content_type`, and `size`

#### Scenario: Complete with missing fields is rejected

- **WHEN** the client sends `POST /files/complete` without `object_key`
- **THEN** the system returns an HTTP client error

### Requirement: R2 credentials are supplied by environment placeholders

The system SHALL read R2 account id, access key id, secret access key, and bucket name from environment placeholders. The system MUST NOT require these secret values to be committed in source or TOML model config.

#### Scenario: Presign uses configured environment values

- **WHEN** the environment placeholders for R2 are filled in and the client sends a valid `POST /files/presign`
- **THEN** the system issues `upload_url` using those configured values
