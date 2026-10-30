# Release checks

Before publishing a release:

1. Verify source data, serving graph, checkpoint and split fingerprints. Reproduce the deployed fixed-review score.
2. Recompute the matched report metrics from recorded test predictions; verify identical membership across model arms and three fixed seeds. Preserve validation-only checkpoint/cutoff selection.
3. Publish only complete recorded runs. Confirm the documentation and website JSON are byte-identical, and historical results remain outside the matched ranking.
4. Run model-contract tests, backend tests, PostgreSQL feature checks, frontend authentication tests, lint and production build as appropriate to changed files.
5. Check the comparison page at desktop and mobile widths, including seed/metric selection, accessible tables, curves, failure states and downloads.
6. Confirm private history and human feedback behavior remain covered by regressions. Do not copy credentials, raw datasets, private bundles or database dumps into the source archive.
7. Deploy the frontend with the existing checked backend origin. Verify production authentication, comparison/report availability and the unchanged active model score.
8. Update the report and source package, render and review the final document, then publish the release and synchronize the public/private repositories.

AWS mutation scripts must verify the intended active Free plan and remaining credit. Publishing this static comparison does not require new AWS resources or a paid-plan upgrade. No checklist implies universal model correctness or automatic deployment from every Git push.
