---
name: test-and-verify
description: Validate code changes using tests, builds, static checks, and reproducible evidence.
---

# Test and Verify
1. Inspect the diff and identify expected behavior.
2. Discover the project's actual test and build commands.
3. Run the narrowest relevant tests first.
4. Test important edge cases and failure paths.
5. Run broader checks when practical.
6. Capture actual results and diagnose failures.
7. Distinguish pre-existing failures from new failures where evidence allows.
8. Report passed, failed, skipped, and blocked checks separately.
9. Never modify code merely to hide a failing test.\n