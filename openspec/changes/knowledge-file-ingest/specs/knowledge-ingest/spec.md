## Purpose

按上传文件的类型解析成可检索文本，识别文档配图，向量入库成功后再留下一条可查的文件记录。

## ADDED Requirements

### Requirement: Ingest path depends on file type

When a signed-in user completes an upload, the system SHALL parse the object according to the declared filename extension before embedding. `.pdf` and `.docx` MUST be converted to markdown by the document converter. `.txt` and `.md` MUST be read as UTF-8 text and MUST NOT use the document converter. `.png`, `.jpg`, and `.jpeg` MUST be sent to the vision model as the whole file and MUST NOT use the document converter. The document converter MUST only be required when the extension is `.pdf` or `.docx`.

#### Scenario: PDF is converted to markdown

- **WHEN** ingest runs for a file named `notes.pdf`
- **THEN** the system converts the file to markdown before splitting and embedding

#### Scenario: TXT skips the document converter

- **WHEN** ingest runs for a file named `notes.txt`
- **THEN** the system reads the object as text and does not call the document converter

#### Scenario: PNG uses the vision model only

- **WHEN** ingest runs for a file named `photo.png`
- **THEN** the system sends the image to the vision model and does not call the document converter

### Requirement: Markdown images are recognized before embedding

When converted markdown contains markdown image references, the system SHALL replace each image with the vision model's text before splitting and embedding. The vision model MUST be given the image URL already present in the markdown. Failure to recognize one image MUST NOT fail ingest of the rest of the document.

#### Scenario: Markdown image is replaced with vision text

- **WHEN** converted markdown contains an image whose URL is reachable
- **THEN** the text that is split and embedded includes the vision model's description in place of that image markup

#### Scenario: One failed image does not abort ingest

- **WHEN** one markdown image cannot be recognized and other content remains
- **THEN** the system still splits and embeds the remaining text

### Requirement: Extracted images are stored under the file prefix

When converted markdown contains images, the system SHALL copy those images into the same per-file object prefix as the original file, under an `images/` segment. The persisted record MUST list those object keys. The system MUST NOT persist expiring download URLs as the long-term image addresses.

#### Scenario: PDF figures land next to the original object

- **WHEN** ingest of a PDF finds markdown images and embedding later succeeds
- **THEN** each copied image's object key shares the original file's prefix, includes an `images/` segment, and is stored on the knowledge file record

### Requirement: Successful embedding persists a knowledge file record

After vectors have been written successfully, the system SHALL insert one MySQL row for that file. The row MUST include the uploader's user id, the original file `object_key`, the declared size, the filename, created and updated timestamps, and a JSON list of companion image object keys (empty when there are none). The row MUST store converted markdown when the file was converted, the read text when the file was `.txt` or `.md`, and the vision model's text when the vision model ran. The original file address MUST be the `object_key`, not an expiring URL. The system MUST NOT insert this row when embedding fails.

#### Scenario: Converted PDF stores markdown, vision text, and image keys

- **WHEN** a PDF with markdown images is embedded successfully
- **THEN** the stored row contains the original `object_key`, the converted markdown, the vision text, and a JSON list of copied image object keys

#### Scenario: TXT stores the file text

- **WHEN** a `.txt` file is embedded successfully
- **THEN** the stored row contains the read text, an empty image key list, and no converted markdown

#### Scenario: PNG stores vision text

- **WHEN** a `.png` file is embedded successfully
- **THEN** the stored row contains the vision model's text, the original `object_key`, and an empty image key list

#### Scenario: Failed embedding does not persist a row

- **WHEN** embedding or vector upsert fails
- **THEN** the system does not insert a knowledge file row

### Requirement: Ingest receives the uploader as a parameter

The system SHALL read the signed-in user id during `POST /files/complete` and pass it into the ingest job. The ingest job MUST NOT read request-scoped identity after the HTTP response has been sent.

#### Scenario: Complete passes the current user into ingest

- **WHEN** a signed-in user completes an upload
- **THEN** the ingest job records that user's id on a successful knowledge file row
