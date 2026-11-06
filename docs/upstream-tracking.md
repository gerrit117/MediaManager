# Upstream fixes

Selected fixes adapted from maxdorninger/MediaManager. The request workflow is retained.

| Reference | State in this fork |
| --- | --- |
| PRs 450, 473, 489, 499, 519, 558, 569 | Adapted previously; details in earlier change notes. |
| Issue 573 | Direct Newznab searches omit q when ID search is used; existing regression tests retained. |
| Issue 574 | Preserve a resolved magnet redirect in the release object so the actual client receives it; regression test added. |
| Issue 575 | OIDC no longer automatically links an existing account by email or marks newly created OAuth accounts verified. Existing account links are retained; this does not audit historical associations. Regression test added. |
| Issues 554/566 and PR 569 | Non-1000 runtime/cache covered by UID 99/GID 100 tests and writable cache setup. |

Original authors and contributors retain credit. Closed or draft PRs are not represented as upstream-approved fixes. Dependency updates should be tested separately; an available new version is not evidence of compatibility.
