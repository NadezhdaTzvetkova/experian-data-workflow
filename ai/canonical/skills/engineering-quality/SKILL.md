# Engineering Quality

## Purpose
Review code quality, maintainability, testing, error handling, reproducibility, Git discipline, and repository hygiene without overengineering the exercise.

## Workflow
1. Prefer cohesive functions and modules over unnecessary class hierarchies.
2. Separate I/O from deterministic transformation logic.
3. Use explicit configuration instead of hidden constants.
4. Fail clearly on structural or configuration errors.
5. Never broadly swallow unexpected exceptions.
6. Test observable behavior rather than implementation trivia.
7. Include at least one true end-to-end pipeline test.
8. Verify deterministic rerun behavior.
9. Test key uniqueness, join cardinality, and reconciliation.
10. Keep documentation, paths, commands, counts, and architecture aligned with the actual repository.
11. Use meaningful Git checkpoints.
12. Verify execution from a clean checkout/environment.
13. Keep the submission free of unrelated internal scaffolding, credentials, generated noise, and stale artifacts.
14. Before adding a dependency, abstraction, module, test category, or infrastructure component, apply the Reviewer Value Test.

## Reviewer Value Test
Ask:
"What would the Experian panel learn from this addition that they could not already learn from something simpler?"

If the answer is weak:
- do not add it;
- simplify it; or
- keep it as an interview/production-evolution discussion instead of implementation.

## Preferred Engineering Style
- explicit names;
- pathlib;
- context managers;
- vectorized Pandas operations where appropriate;
- clear SQL;
- narrow, meaningful exceptions;
- small configuration objects or dataclasses only when useful;
- structured control results;
- deterministic ordering where output comparison depends on order.

## Tests to Prioritize
- missing required schema fails clearly;
- duplicate transaction key is detected;
- invalid amount is quarantined;
- unknown required reference is quarantined;
- source rows reconcile;
- duplicate reference key blocks unsafe enrichment;
- accepted count equals curated count after one-to-one enrichment;
- valid audit exception remains in trusted data and is flagged;
- deterministic rerun produces equivalent business output;
- known injected defect oracle is detected;
- one full input-to-output end-to-end test.

## Avoid
- generic utils.py dumping grounds;
- unnecessary factories, managers, or service layers;
- speculative extensibility;
- duplicate Python and SQL business logic;
- broad exception swallowing;
- line-coverage theatre;
- unused dependencies;
- stale README claims;
- generated files committed accidentally;
- abstractions the candidate cannot explain.

## Guardrail
A technically sophisticated solution that is harder to verify, explain, or reproduce is worse than a simpler solution that fully satisfies the exercise.
