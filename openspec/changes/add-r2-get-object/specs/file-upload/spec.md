## MODIFIED Requirements

### Requirement: Client can submit declared upload metadata

The system SHALL accept `POST /files/complete` with `object_key`, `filename`, `content_type`, and `size` declared by the client. The system SHALL issue a time-limited download URL for the declared `object_key` and return the declared fields together with `download_url` and `expires_in`. The system MUST NOT read or delete the object in the bucket, MUST NOT persist the record, and MUST NOT include object bytes in the HTTP response. The `download_url` MUST be usable as an HTTPS source by a downstream document loader until it expires.

#### Scenario: Complete returns the declared file record and a download URL

- **WHEN** the client sends `POST /files/complete` with `object_key` `abc/notes.pdf`, filename `notes.pdf`, content type `application/pdf`, and size `1048576`
- **THEN** the system returns an HTTP success response whose body contains the same `object_key`, `filename`, `content_type`, and `size`, plus a non-empty `download_url` and a positive `expires_in`

#### Scenario: Complete with missing fields is rejected

- **WHEN** the client sends `POST /files/complete` without `object_key`
- **THEN** the system returns an HTTP client error and does not return `download_url`
