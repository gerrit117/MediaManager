# Upstream review

The fork keeps the v1.12.3 request workflow and reviews fixes individually. It does not merge upstream master wholesale. References below point to maxdorninger/MediaManager.

| Reference | State in this fork |
| --- | --- |
| PRs 450, 473, 489, 499, 519, 558, 569 | Adapted previously; details in earlier change notes. |
| Issue 573 | Direct Newznab searches omit q when ID search is used; existing regression tests retained. |
| Issue 574 | Preserve a resolved magnet redirect in the release object so the actual client receives it; regression test added. |
| Issue 575 | OIDC no longer automatically links an existing account by email or marks newly created OAuth accounts verified. Existing account links are retained; this does not audit historical associations. Regression test added. |
| PR 576 | Reviewed as an upstream Easypanel deployment-doc proposal. Not copied as our managed-stack paths/image differ. |
| Issues 554/566 and PR 569 | Non-1000 runtime/cache covered by UID 99/GID 100 tests and writable cache setup. |
| Issue 562 | Routing/redirect report remains tracked separately; no claim of a general routing fix in this release. |
| Issue 559 | Connection-pool problem remains for a focused reproduction and regression test. |
| PRs 454/455/461/541 | Large architecture/schema/request-removal changes excluded. |

Original authors and contributors retain credit. Closed or draft PRs are not represented as upstream-approved fixes. Dependency updates should be tested separately; an available new version is not evidence of compatibility.
