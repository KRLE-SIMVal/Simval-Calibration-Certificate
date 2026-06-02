# P2 Closeout

Status: complete for the backend temperature workflow milestone.

This closes P2 as the controlled backend workflow from traceable ValProbe/KAYE import data through selected windows and locked temperature calculation summaries. It does not close the full web application, certificate rendering, or production release.

## Completed P2 Scope

| Area | Status |
|---|---|
| SQLite persistence for jobs, files, DUTs, readings, windows, summaries, certificates, constants, budgets, audit, and numbering | Complete |
| Transactional audit writes for import, window selection, window completion, and calculation run | Complete |
| ValProbe/KAYE XLSX parser boundary for sanitized workbooks | Complete |
| Verification IRTD parser contract using the column immediately after `Time` | Complete |
| Linked logger/IRTD timestamp alignment | Complete |
| Linked logger/IRTD persistence with immutable source traceability | Complete |
| Manual timestamp-window selection from linked readings | Complete |
| Required temperature setpoint plan model and persistence | Complete |
| Window completeness by DUT, setpoint, and unit | Complete |
| Automatic temperature result calculation from linked logger/IRTD windows | Complete |
| CMC floor and AB11 rounding through the calculation summary model | Complete |
| Approved constant-set and uncertainty-budget version checks before calculation | Complete |
| Calculation-run audit evidence with contribution breakdown | Complete |

## Metrology Impact

P2 now calculates automatic temperature result rows using the approved P0 rule:

```text
reference = mean(selected IRTD/reference readings)
indication = mean(selected DUT/logger readings)
error = indication - reference
```

Uncertainty handling follows the P0 GUM/AB11 basis for this backend milestone:

- Reference expanded uncertainty is converted to standard uncertainty by division by coverage factor.
- Reference and DUT repeatability are calculated from selected linked readings using sample standard deviation and standard uncertainty of the mean.
- Optional bath/thermostat and DUT resolution contributions are converted using the documented rules.
- Independent standard uncertainties are combined by RSS.
- Expanded uncertainty uses the configured coverage factor, default `k = 2`.
- Reported expanded uncertainty is floored against the supplied CMC and display-rounded using the AB11 rounding primitives.

The service does not invent or approve uncertainty budgets. It requires approved matching constant-set and uncertainty-budget version records before persisting calculation summaries.

## Intentionally Deferred To P3 Or Later

- API endpoints and request/response models.
- User/session persistence and authenticated actor resolution.
- Production database migration runner beyond the current schema-version marker.
- PDF certificate rendering and visual template matching.
- Production PDF text/table extraction dependency for verification files.
- D4 certificate-number and equipment-data adapter.
- Automatic plateau/stability suggestion.
- Dedicated persisted uncertainty-contribution detail table.
- Controlled customer-safe parser fixtures in default CI.

## P3 Entry Recommendation

Start P3 with the council reviewing API and production-control boundaries:

1. API dependency approval and endpoint contracts.
2. User/session persistence and audit actor identity.
3. Production migration approach.
4. Certificate preview/export service boundary consuming locked summaries.
5. Rendering/template validation strategy.

Do not expose P2 services through an API until actor identity, permissions, and migration controls are agreed.
