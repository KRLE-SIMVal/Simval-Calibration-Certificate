# P21 Implementation Log

Status: implemented for evidence-reference manifest verification.

P21 extends the production-readiness report CLI so supplied go-live evidence
references are checked for existence and retained in the report payload as a
manifest.

## Scope Implemented

- Added evidence reference manifest records to the production-readiness report
  payload.
- The CLI now checks every supplied `--evidence key=value` reference.
- Existing file references are recorded with SHA-256 and byte size.
- Existing directory references are recorded as directories.
- Missing references are listed in `unavailable_references` and produce
  deterministic blockers such as
  `live_entra_evidence_reference_unavailable`.
- Added focused tests for missing references and successful manifest creation.

## Compliance Notes

- This reduces the risk that a go-live report references evidence that is not
  present at report-generation time.
- The report still cannot judge whether the evidence content is adequate.
  System Owner and QA/Laboratory review remains mandatory.
- No calculation, uncertainty, CMC, rounding, certificate rendering, release,
  audit immutability, reviewer-independence, authentication, or token-validation
  logic was changed.

## Verification

- Focused production-readiness report and documentation suite:
  17 passed on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| Directory evidence references are existence-checked but not recursively checksummed. | Prefer file evidence records for final go-live approvals, or include a validation package manifest with checksums for directory contents. |
| The report checks presence and checksum, not the technical adequacy of the evidence. | Require System Owner and QA/Laboratory review of the evidence content before routine production use. |
| Live production evidence still has to be created outside this workspace. | Run the report on the approved SIMVal host after real Entra, TLS, backup/restore, reviewer-independence, retention, and human approval evidence is complete. |
