# knowledge-ingest Delta

## ADDED Requirements

### Requirement: Converter raw output is archived to object storage

When the document converter successfully converts a `.pdf` or `.docx`, the system SHALL archive the converter's raw output into object storage under the original file's prefix, in a dedicated `mineru/` segment that MUST NOT overlap the kept-figures `images/` segment. The archive MUST include the raw converted markdown exactly as the converter produced it (relative image references intact) and every image asset the converter produced, uploaded so that each raw markdown reference such as `images/<filename>` resolves to an archived object under the same `mineru/` segment. Archiving MUST apply to every converter-produced image, regardless of whether that figure is later kept, skipped as decorative, or fails recognition. Archiving MUST NOT wait for or depend on per-figure vision decisions. A failure to archive any single object MUST be logged, MUST NOT abort the remaining archive uploads, and MUST NOT fail ingest. The archive location MUST be derivable from the original file `object_key` alone, without a database lookup. Files that do not go through the document converter (`.txt`, `.md`, `.png`, `.jpg`, `.jpeg`) MUST NOT produce a converter archive.

#### Scenario: All PDF figures are archived regardless of keep-or-skip

- **WHEN** a PDF converts successfully and the converter produced 5 images, and the vision model later keeps only 3 of them
- **THEN** the original file's prefix contains a `mineru/` segment holding the raw converted markdown and all 5 converter images

#### Scenario: Raw markdown references resolve inside the archive

- **WHEN** the archived raw markdown contains a reference `images/<filename>`
- **THEN** an archived object for that figure exists under the same `mineru/` segment at its `images/` subpath

#### Scenario: Archive survives a later ingest failure

- **WHEN** conversion succeeds and raw output is archived, but splitting, embedding, or vector upsert afterwards fails
- **THEN** the archived `mineru/` objects remain in object storage for troubleshooting

#### Scenario: Single archive upload failure does not fail ingest

- **WHEN** uploading one archived image or the raw markdown fails
- **THEN** the failure is logged, the remaining archive uploads are still attempted, and ingest continues

#### Scenario: Non-converter files produce no archive

- **WHEN** a `.txt`, `.md`, or standalone image file is ingested
- **THEN** no `mineru/` archive objects are created for that file
