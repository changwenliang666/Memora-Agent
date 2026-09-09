# knowledge-ingest Specification

## Purpose

按上传文件的类型解析成可检索文本，识别文档配图，向量入库成功后再留下一条可查的文件记录，供后续检索对照。

## Requirements

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

When converted markdown contains markdown image references, the system SHALL give the vision model each image URL already present in the markdown and SHALL decide per image whether the figure has retrieval value. When the vision model returns extractable knowledge text, the system MUST replace that image markup with that text before splitting and embedding. When the vision model indicates the figure has no retrieval value, or when recognition of that image fails, the system MUST remove that image markup from the text that is split and embedded and MUST NOT substitute a placeholder description. Failure or skip of one image MUST NOT fail ingest of the rest of the document. This per-image skip MUST apply only to markdown image references, not to a standalone image file upload.

#### Scenario: Meaningful markdown image is replaced with vision text

- **WHEN** converted markdown contains an image whose URL is reachable and the vision model returns knowledge text
- **THEN** the text that is split and embedded includes that vision text in place of that image markup

#### Scenario: Decorative markdown image is stripped from embedding text

- **WHEN** converted markdown contains an image and the vision model indicates it has no retrieval value
- **THEN** the text that is split and embedded does not contain that image markup and does not contain vision text for that image

#### Scenario: One failed image does not abort ingest

- **WHEN** one markdown image cannot be recognized and other content remains
- **THEN** the system still splits and embeds the remaining text, and the failed image's markup is not left in the embedding text

### Requirement: Extracted images are stored under the file prefix

When converted markdown contains images that the vision model treats as having retrieval value, the system SHALL copy those kept images into the same per-file object prefix as the original file, under an `images/` segment. The persisted record MUST list only those copied object keys. Images that the vision model treats as having no retrieval value, and images whose recognition failed, MUST NOT be copied into object storage and MUST NOT appear in the companion image key list. The system MUST NOT persist expiring download URLs as the long-term image addresses.

#### Scenario: PDF figures land next to the original object

- **WHEN** ingest of a PDF finds markdown images that the vision model treats as having retrieval value and embedding later succeeds
- **THEN** each copied image's object key shares the original file's prefix, includes an `images/` segment, and is stored on the knowledge file record

#### Scenario: Decorative markdown figure is not copied

- **WHEN** ingest of a PDF finds a markdown image that the vision model treats as having no retrieval value and embedding later succeeds
- **THEN** that image is not copied into object storage and its key is not stored on the knowledge file record

### Requirement: Knowledge file body columns store complete text

When the system persists a knowledge file row, the converted markdown and read plain text MUST be stored in full. The MySQL columns for those bodies MUST be `MEDIUMTEXT`. The system MUST NOT use MySQL `TEXT` for these columns. A value that fits in `MEDIUMTEXT` MUST NOT be truncated by the schema.

#### Scenario: Converted markdown longer than 64 KiB is stored in full

- **WHEN** a converted PDF whose markdown exceeds 64 KiB is embedded successfully
- **THEN** the stored `markdown` column contains the complete converted markdown, not only the leading fragment

#### Scenario: Body columns are MEDIUMTEXT

- **WHEN** the knowledge file table is created or an existing table is started against
- **THEN** `markdown` and `plain_text` are MySQL `MEDIUMTEXT` (nullable)

### Requirement: Vision results are stored per image

When the system persists vision-model output on a knowledge file row, it MUST store a JSON array of per-image results, not a single concatenated string. Each array element MUST include `text` (the vision model's knowledge text for that image) and `image_key`. For a standalone image file, `image_key` MUST be the original file `object_key`. For a kept markdown figure, `image_key` MUST be the copied object key when that figure was copied into object storage, and MUST be JSON `null` when the copy failed. The array MUST be empty when the vision model did not run, and MUST omit markdown figures that had no retrieval value and markdown figures whose recognition failed. The array order for kept markdown figures MUST follow their order of appearance in the converted document. The system MUST NOT join multiple images' texts with separators for persistence.

#### Scenario: PDF with two kept figures stores two vision results

- **WHEN** a converted PDF contains two markdown images, both treated as having retrieval value, and embedding later succeeds
- **THEN** the stored vision-results array has two elements in markdown order, each with that figure's `text` and `image_key`

#### Scenario: Decorative or failed markdown figure is omitted from vision results

- **WHEN** a converted PDF contains one markdown image that has no retrieval value or cannot be recognized, and another image that is kept, and embedding later succeeds
- **THEN** the stored vision-results array contains only the kept image's element

#### Scenario: Standalone PNG stores one result keyed to the file

- **WHEN** a `.png` file is embedded successfully
- **THEN** the stored vision-results array has one element whose `text` is the vision model's output and whose `image_key` is the original file `object_key`

#### Scenario: TXT stores an empty vision-results array

- **WHEN** a `.txt` file is embedded successfully
- **THEN** the stored vision-results array is empty

### Requirement: Successful embedding persists a knowledge file record

After vectors have been written successfully, the system SHALL insert one MySQL row for that file. The row MUST include the uploader's user id, the original file `object_key`, the declared size, the filename, created and updated timestamps, and a JSON list of companion image object keys (empty when there are none). The row MUST store converted markdown when the file was converted, the read text when the file was `.txt` or `.md`, and a JSON list of per-image vision results when the vision model ran (empty when it did not). Converted markdown MUST retain the converter's original image references even when some figures were skipped for embedding and persistence. The original file address MUST be the `object_key`, not an expiring URL. The system MUST NOT insert this row when embedding fails.

#### Scenario: Converted PDF stores markdown, per-image vision results, and image keys

- **WHEN** a PDF with markdown images is embedded successfully
- **THEN** the stored row contains the original `object_key`, the converted markdown, a JSON list of per-image vision results for kept figures only, and a JSON list of copied image object keys for kept figures only

#### Scenario: TXT stores the file text

- **WHEN** a `.txt` file is embedded successfully
- **THEN** the stored row contains the read text, an empty image key list, an empty vision-results list, and no converted markdown

#### Scenario: PNG stores one vision result for the file

- **WHEN** a `.png` file is embedded successfully
- **THEN** the stored row contains a one-element vision-results list keyed to the original `object_key`, and an empty companion image key list

#### Scenario: Failed embedding does not persist a row

- **WHEN** embedding or vector upsert fails
- **THEN** the system does not insert a knowledge file row

### Requirement: Markdown-shaped text is split without breaking tables or fenced code

When the system splits markdown-shaped text for embedding (converted PDF/DOCX markdown after figure handling, and uploaded `.md` files), it MUST keep each HTML table (`<table>` through `</table>`), each markdown pipe table, and each fenced code block (opening fence through matching closing fence, including ` ``` ` and `~~~`) inside a single chunk. Those atomic regions MUST NOT be split on newlines, semicolons, spaces, or other prose separators. An atomic region longer than the prose chunk size MUST still occupy one chunk. Prose outside atomic regions MUST continue to use the existing 500-character chunk size and 50-character overlap. A fenced code region MUST be treated as one atomic unit even when it contains table markup or lines that look like markdown headings. Each chunk MUST remain readable markdown: tables keep their opening and closing tags or pipe rows, and fenced code keeps both fence lines.

#### Scenario: HTML table stays in one chunk

- **WHEN** markdown-shaped text contains an HTML table whose serialized length exceeds 500 characters, surrounded by prose
- **THEN** one embedding chunk contains the entire `<table>` through `</table>` and does not contain only a fragment of that table

#### Scenario: Fenced code stays in one chunk

- **WHEN** markdown-shaped text contains a fenced code block that includes statements such as `console.log()` and lines starting with `#`
- **THEN** one embedding chunk contains the opening fence, the full code, and the closing fence, and that code is not split across chunks

#### Scenario: Markdown pipe table stays in one chunk

- **WHEN** markdown-shaped text contains a pipe table
- **THEN** one embedding chunk contains every row of that table

### Requirement: Plain text ingest does not use markdown structure splitting

When the system splits `.txt` content or the vision text of a standalone `.png` / `.jpg` / `.jpeg` file, it MUST use character-based recursive splitting with the existing 500-character chunk size and 50-character overlap. It MUST NOT treat heading markers, fenced code, or HTML tables as atomic markdown structure.

#### Scenario: TXT with hash prefixes is not split as markdown headings

- **WHEN** a `.txt` file whose body includes lines starting with `#` is ingested
- **THEN** the system splits that body as plain text and does not treat those lines as markdown section headings

#### Scenario: Standalone PNG vision text uses plain splitting

- **WHEN** a `.png` file is ingested
- **THEN** the vision model's text is split as plain text, not as markdown

### Requirement: Heading path is kept on markdown chunks

When markdown-shaped text is split on ATX headings (`#`, `##`, `###`), each resulting embedding chunk MUST include the heading path in its stored metadata. Splitting MUST NOT discard heading metadata after the header pass. Lines that look like headings inside fenced code MUST NOT start a new section.

#### Scenario: Section heading remains on the chunk

- **WHEN** markdown-shaped text has an `h2` section whose prose is split into multiple chunks
- **THEN** each of those chunks' metadata includes that `h2` heading text

#### Scenario: Hash comment inside a fence is not a heading

- **WHEN** a fenced code block contains a line starting with `#`
- **THEN** that line does not create a new heading section and remains inside the code chunk

### Requirement: Standalone image ingest is not filtered by decorative-figure rules

When the uploaded file itself is `.png`, `.jpg`, or `.jpeg`, the system MUST send the whole file to the vision model and MUST persist that result. The decorative-figure skip used for markdown images MUST NOT apply to this path.

#### Scenario: Uploaded PNG is always persisted

- **WHEN** a `.png` file is ingested successfully
- **THEN** the stored vision-results array has one element for that file even if the image would be decorative as a markdown figure

### Requirement: Ingest receives the uploader as a parameter

The system SHALL read the signed-in user id during `POST /files/complete` and pass it into the ingest job. The ingest job MUST NOT read request-scoped identity after the HTTP response has been sent.

#### Scenario: Complete passes the current user into ingest

- **WHEN** a signed-in user completes an upload
- **THEN** the ingest job records that user's id on a successful knowledge file row
