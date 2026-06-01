# Example File Classification

Status: active P1 control.

## Decision

The raw files in `Docs/Input and output file examples/` are classified as:

```text
controlled_internal_confidential
```

They are not approved for Git tracking or CI execution at this stage.

## Files

| File | SHA-256 | Classification | Git tracking | CI use |
|---|---|---|---|---|
| `Calibration_input_file_Valprobe RT Loggers.xlsx` | `71B6AAE2BCF599A65F25B16330473B1D7B60D3A3C0D3FD169D929E25CB362B02` | `controlled_internal_confidential` | No | No |
| `KAYE Verification file - Valprobe Logger.pdf` | `AD60CBA78FFEC2B9FF9D23BC4440DD849C6337FD3C407F773A4CA36B18F8F0F5` | `controlled_internal_confidential` | No | No |
| `Calibration Certificate Output file.pdf` | `C1D02553D14EC400099A48A4E1F8AA506E18DB4FD3FC0FFD15CA85FCEDFF1DC6` | `controlled_internal_confidential` | No | No |

## Rationale

The files may contain customer, equipment, personnel, third-party laboratory, or traceability information. Until repository visibility and data-sharing controls are explicitly approved, the safest compliant position is to keep raw examples local and out of Git.

## Use In P1

The files may be used locally for controlled parser-contract exploration after explicit opt-in:

```text
SIMVAL_RUN_CONTROLLED_FIXTURE_TESTS=1
```

These tests are skipped by default.

## Required Future Action

Before enabling these examples in CI or committing equivalent fixtures:

- Confirm repository visibility and access control.
- Confirm whether customer/personnel/third-party data is present.
- Create sanitized fixtures where possible.
- Retain checksum and source metadata for any controlled fixtures.
- Update the fixture manifest and this classification record.

