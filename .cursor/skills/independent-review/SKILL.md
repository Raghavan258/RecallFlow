---
name: independent-review
description: Independently review changes for bugs, security risks, regressions, and missing validation.
---

# Independent Code Review
1. Inspect the actual diff and surrounding code.
2. Check correctness, boundary conditions, error handling, and data flow.
3. Review security, permissions, secrets, and sensitive-data handling where relevant.
4. Check compatibility with existing APIs and consumers.
5. Examine test coverage and missing regression cases.
6. Prioritize findings by severity and explain impact.
7. Include file paths and concrete evidence.
8. Avoid speculative findings without a clear failure scenario.
9. Do not edit files or claim unexecuted checks passed.
10. Return findings first, then residual risks and an overall assessment.\n