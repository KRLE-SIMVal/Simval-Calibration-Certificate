# P0 Control Package

Status: approved for documentation and planning.

P0 defines how the SIMVal calibration certificate application will be built, tested, validated, and controlled before production application code begins.

## Scope

P0 includes:

- Repository and architecture structure.
- Requirements-to-test mapping.
- Automated test strategy.
- GUM/DANAK AB11 calculation principles.
- Domain model and workflow states.
- Roles and permissions.
- Validation and regression plan.
- Quarterly scheduled regression control.
- D4 deferred integration decision.

P0 does not include production application code, migrations, UI implementation, or calculation-engine implementation.

## Approved Assumptions

- No legacy calculation examples will be provided.
- Calculation validation must be based on first principles from GUM, DANAK AB11, and approved SIMVal domain assumptions.
- D4 is not critical for the first implementation and is deferred as a future integration.
- The application must be tests-first.
- Every behavior change must add or update automated tests.
- A full automated regression suite must run quarterly on January 1, April 1, July 1, and October 1, even if no code has changed.

## P0 Documents

- [Architecture_And_Repository_Structure.md](Architecture_And_Repository_Structure.md)
- [Calculation_Principles_GUM_AB11.md](Calculation_Principles_GUM_AB11.md)
- [CMC_Range_Interpolation_Rules.md](CMC_Range_Interpolation_Rules.md)
- [Decision_Record_D4_Deferred.md](Decision_Record_D4_Deferred.md)
- [Domain_Model_And_Workflow.md](Domain_Model_And_Workflow.md)
- [Requirements_To_Test_Matrix.md](Requirements_To_Test_Matrix.md)
- [Roles_And_Permissions.md](Roles_And_Permissions.md)
- [Test_Case_Catalog.md](Test_Case_Catalog.md)
- [Test_Strategy.md](Test_Strategy.md)
- [Validation_And_Regression_Plan.md](Validation_And_Regression_Plan.md)

## Gate To P1

P1 may start only after P0 is reviewed and accepted by SIMVal.

The P1 start gate requires:

- Approved calculation principles.
- Approved test strategy and test-case catalog.
- Approved workflow states.
- Approved roles and permissions.
- Approved audit and evidence expectations.
- Approved repository structure.
- Clear list of remaining open decisions.
