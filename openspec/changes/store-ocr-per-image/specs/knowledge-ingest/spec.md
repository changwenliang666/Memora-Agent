## ADDED Requirements

### Requirement: Vision results are stored per image

When the system persists vision-model output on a knowledge file row, it MUST store a JSON array of per-image results, not a single concatenated string. Each array element MUST include `text` (the vision model's text for that image, or an empty string when recognition of that image failed) and `image_key`. For a standalone image file, `image_key` MUST be the original file `object_key`. For a markdown figure, `image_key` MUST be the copied object key when that figure was copied into object storage, and MUST be JSON `null` when the copy failed. The array MUST be empty when the vision model did not run. The array order for markdown figures MUST follow the order of markdown image references in the converted document. The system MUST NOT join multiple images' texts with separators for persistence.

#### Scenario: PDF with two figures stores two vision results

- **WHEN** a converted PDF contains two markdown images and embedding later succeeds
- **THEN** the stored vision-results array has two elements in markdown order, each with that figure's `text` and `image_key`

#### Scenario: One failed figure still occupies its own result

- **WHEN** one markdown image cannot be recognized and another image succeeds, and embedding later succeeds
- **THEN** the stored vision-results array still has one element per markdown image, and the failed image's `text` is an empty string

#### Scenario: Standalone PNG stores one result keyed to the file

- **WHEN** a `.png` file is embedded successfully
- **THEN** the stored vision-results array has one element whose `text` is the vision model's output and whose `image_key` is the original file `object_key`

#### Scenario: TXT stores an empty vision-results array

- **WHEN** a `.txt` file is embedded successfully
- **THEN** the stored vision-results array is empty

## MODIFIED Requirements

### Requirement: Successful embedding persists a knowledge file record

After vectors have been written successfully, the system SHALL insert one MySQL row for that file. The row MUST include the uploader's user id, the original file `object_key`, the declared size, the filename, created and updated timestamps, and a JSON list of companion image object keys (empty when there are none). The row MUST store converted markdown when the file was converted, the read text when the file was `.txt` or `.md`, and a JSON list of per-image vision results when the vision model ran (empty when it did not). The original file address MUST be the `object_key`, not an expiring URL. The system MUST NOT insert this row when embedding fails.

#### Scenario: Converted PDF stores markdown, per-image vision results, and image keys

- **WHEN** a PDF with markdown images is embedded successfully
- **THEN** the stored row contains the original `object_key`, the converted markdown, a JSON list of per-image vision results, and a JSON list of copied image object keys

#### Scenario: TXT stores the file text

- **WHEN** a `.txt` file is embedded successfully
- **THEN** the stored row contains the read text, an empty image key list, an empty vision-results list, and no converted markdown

#### Scenario: PNG stores one vision result for the file

- **WHEN** a `.png` file is embedded successfully
- **THEN** the stored row contains a one-element vision-results list keyed to the original `object_key`, and an empty companion image key list

#### Scenario: Failed embedding does not persist a row

- **WHEN** embedding or vector upsert fails
- **THEN** the system does not insert a knowledge file row
