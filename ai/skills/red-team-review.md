# Red-Team Review

## Purpose
Search deliberately for cases where the workflow can appear correct while being wrong.

## Invoke when
- completing a coherent implementation phase;
- before public submission;
- after requirement changes.

## Review questions
- Which assumption is most fragile?
- Which test could pass for the wrong reason?
- What depends on local state?
- Can outputs become internally inconsistent?
- What requirement change would break this design first?

## Evidence expected
- concrete adversarial scenarios;
- targeted failure tests;
- corrected assumptions;
- documented residual limitations.

## Failure signal
Review only confirms existing beliefs and does not attempt to falsify them.
