## ADDED Requirements

### Requirement: Knowledge file body columns store complete text

When the system persists a knowledge file row, the converted markdown, read plain text, and vision-model text MUST be stored in full. The MySQL columns for those three bodies MUST be `MEDIUMTEXT`. The system MUST NOT use MySQL `TEXT` for these columns. A value that fits in `MEDIUMTEXT` MUST NOT be truncated by the schema.

#### Scenario: Converted markdown longer than 64 KiB is stored in full

- **WHEN** a converted PDF whose markdown exceeds 64 KiB is embedded successfully
- **THEN** the stored `markdown` column contains the complete converted markdown, not only the leading fragment

#### Scenario: Body columns are MEDIUMTEXT

- **WHEN** the knowledge file table is created or an existing table is started against
- **THEN** `markdown`, `plain_text`, and `ocr_text` are MySQL `MEDIUMTEXT` (nullable)
