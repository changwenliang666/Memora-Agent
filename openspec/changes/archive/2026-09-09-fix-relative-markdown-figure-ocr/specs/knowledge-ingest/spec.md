## MODIFIED Requirements

### Requirement: Markdown images are recognized before embedding

When converted markdown contains markdown image references, the system SHALL present each figure to the vision model in a form the model can read, and SHALL decide per image whether the figure has retrieval value using the same keep-or-skip rules for every address form. When a reference is an absolute `http`/`https` URL or a `data:` URI, the system MUST give that URI to the existing markdown-figure recognition path. When a reference is a relative path (including `images/<filename>` and a bare filename), the system MUST first resolve it against image bytes produced with the converted markdown, MUST present those bytes to the same recognition path, and MUST NOT pass the relative path string to the vision model as if it were a fetchable URL. When the relative path cannot be resolved to image bytes, the system MUST treat that figure as a recognition failure. When the vision model returns extractable knowledge text, the system MUST replace that image markup with that text before splitting and embedding. When the vision model indicates the figure has no retrieval value, or when recognition of that image fails, the system MUST remove that image markup from the text that is split and embedded and MUST NOT substitute a placeholder description. Failure or skip of one image MUST NOT fail ingest of the rest of the document. Adjacent image markups without surrounding whitespace MUST each be processed. This per-image skip MUST apply only to markdown image references, not to a standalone image file upload.

#### Scenario: Meaningful markdown image is replaced with vision text

- **WHEN** converted markdown contains an image whose URL is reachable and the vision model returns knowledge text
- **THEN** the text that is split and embedded includes that vision text in place of that image markup

#### Scenario: Relative markdown image is recognized from converter bytes

- **WHEN** converted markdown contains `![](images/<filename>)` (or the same markup adjacent to another image with no whitespace) and the converter produced bytes for that filename, and the vision model returns knowledge text
- **THEN** the text that is split and embedded includes that vision text in place of that image markup, and the stored vision-results array includes an element for that figure

#### Scenario: Unresolved relative markdown image is treated as a failed image

- **WHEN** converted markdown contains a relative image path that has no matching converter image bytes
- **THEN** that image's markup is not left in the embedding text, and that figure is omitted from the stored vision-results array

#### Scenario: Decorative markdown image is stripped from embedding text

- **WHEN** converted markdown contains an image and the vision model indicates it has no retrieval value
- **THEN** the text that is split and embedded does not contain that image markup and does not contain vision text for that image

#### Scenario: One failed image does not abort ingest

- **WHEN** one markdown image cannot be recognized and other content remains
- **THEN** the system still splits and embeds the remaining text, and the failed image's markup is not left in the embedding text

### Requirement: Extracted images are stored under the file prefix

When converted markdown contains images that the vision model treats as having retrieval value, the system SHALL copy those kept images into the same per-file object prefix as the original file, under an `images/` segment. When a kept figure was an absolute `http`/`https` URL, the system MUST copy by downloading that URL, as it does today. When a kept figure was resolved from converter image bytes, the system MUST copy those bytes into object storage and MUST NOT attempt to download the relative path as a URL. The persisted record MUST list only those copied object keys. Images that the vision model treats as having no retrieval value, and images whose recognition failed, MUST NOT be copied into object storage and MUST NOT appear in the companion image key list. The system MUST NOT persist expiring download URLs as the long-term image addresses.

#### Scenario: PDF figures land next to the original object

- **WHEN** ingest of a PDF finds markdown images that the vision model treats as having retrieval value and embedding later succeeds
- **THEN** each copied image's object key shares the original file's prefix, includes an `images/` segment, and is stored on the knowledge file record

#### Scenario: Relative kept figure is copied from converter bytes

- **WHEN** ingest of a PDF finds a relative markdown image that the vision model treats as having retrieval value, converter bytes exist for that path, and embedding later succeeds
- **THEN** those converter bytes are stored under the original file's prefix with an `images/` segment, and that object key is stored on the knowledge file record

#### Scenario: Decorative markdown figure is not copied

- **WHEN** ingest of a PDF finds a markdown image that the vision model treats as having no retrieval value and embedding later succeeds
- **THEN** that image is not copied into object storage and its key is not stored on the knowledge file record
