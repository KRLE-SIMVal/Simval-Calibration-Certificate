# P42 Implementation Log - Discipline-Neutral Certificate Result Wording

## Scope

P42 removes a pressure-template wording blocker from the deterministic PDF
renderer.

## Changes

- Replaced the result-page label `Temperaturskala / Temperature scale` with
  `Skala/enhed / Scale/unit`.
- Kept the existing metadata field unchanged for backward compatibility; the
  field now renders as a discipline-neutral scale or unit value.

## Validation

- Added rendering test coverage proving the PDF includes `Skala/enhed /
  Scale/unit` and no longer emits `Temperature scale:`.
- Re-ran the manual pressure end-to-end release test through rendered PDF
  generation.

## Domain Impact

No calculation logic changed. The change is presentation-only and prevents
manual pressure certificates from carrying temperature-specific result-page
wording.

## Remaining Risk

SIMVal QA/Laboratory still needs to approve the final pressure certificate
wording/layout and any method-specific pressure statements before routine DANAK
production release.
