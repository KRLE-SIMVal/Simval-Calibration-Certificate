# P40 Implementation Log - Controlled Generic Source Evidence Upload

## Scope

P40 removes a pressure-workflow blocker in the source-file upload boundary. It
allows controlled generic source evidence files to be stored before manual
pressure entry or future pressure parser validation.

## Changes

- Added an explicit upload whitelist for `UploadedFileKind.OTHER`.
- Allowed `.csv`, `.json`, and `.txt` files for generic source evidence.
- Added an explicit whitelist for `certificate_reference_pdf`.
- Kept parser execution disabled for generic source evidence; files are stored
  with checksum, storage URI, upload audit evidence, and `parser_status` of
  `not_run`.

## Validation

- Added API upload workflow coverage for a pressure-style `.csv` source file.
- Verified the uploaded file is persisted, stored under controlled artifact
  storage, and not parsed.

## Domain Impact

No calculation logic changed. P40 only broadens controlled raw-evidence storage
for non-ValProbe source files. Pressure calculations still require manually
validated entry or a future approved pressure parser before routine production
use.

## Remaining Risk

P45 later adds known-schema automatic pressure CSV import for paired
reference/DUT source files. Unknown CSV/XLSX mapping remains outside the generic
upload boundary and still requires controlled manual entry or a future approved
mapping workflow.
