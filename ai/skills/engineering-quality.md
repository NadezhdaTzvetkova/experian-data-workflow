# Engineering Quality

## Purpose
Review maintainability, testing, packaging and reproducibility.

## Invoke when
- adding modules or dependencies;
- changing execution flow;
- preparing the repository for another engineer.

## Review questions
- Is the code understandable and appropriately separated?
- Are tests behavioural and hermetic?
- Are failures explicit?
- Can the project be reproduced from declared dependencies?

## Evidence expected
- Ruff;
- pytest;
- locked dependencies;
- documented execution instructions;
- clean repository state.

## Failure signal
The solution works only because of undocumented local state or fragile assumptions.
