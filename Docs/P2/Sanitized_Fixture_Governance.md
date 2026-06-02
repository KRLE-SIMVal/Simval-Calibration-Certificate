# Sanitized Fixture Governance

Status: active for P2 parser development.

This document controls how parser tests may use generated or sanitized input files before production validation.

## Purpose

Parser regression must run automatically in CI without exposing customer data, controlled internal records, or confidential certificate examples.

## Allowed Fixture Types

- Generated fixtures created inside tests at runtime.
- Sanitized fixtures containing no customer names, certificate numbers, serial numbers, addresses, purchase orders, task numbers, or traceable customer values.
- Small structural fixtures that preserve table shape, sheet names, column positions, timestamp format, and parser edge cases.

## Not Allowed In Default CI

- Raw customer XLSX/PDF files.
- Third-party certificate examples containing customer or laboratory-specific confidential records.
- Any fixture whose confidentiality classification is not explicitly approved for CI.

## Required Fixture Evidence

Every stored sanitized fixture must have:

- Fixture ID.
- Intended parser contract.
- Sanitization statement.
- Confidentiality classification.
- SHA-256 checksum.
- Approval status for CI use.

Generated runtime fixtures must be deterministic and documented in the test case they support.

## Parser Validation Rule

Generated or sanitized fixtures prove parser behavior and regression coverage. They do not replace final production validation against approved SIMVal examples and first-principles calculation evidence.

## Current P2 Approach

- ValProbe XLSX parser tests generate sanitized XLSX workbooks at runtime.
- Verification IRTD table tests use sanitized extracted table rows.
- Real controlled example files remain excluded from default CI.
