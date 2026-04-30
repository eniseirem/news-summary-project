# SWP News Summary Monorepo Layout

This monorepo is composed from multiple original branches/repositories.

## Source mapping

- `n8n/` -> base import from local `n8n` project content (intended `n8n-pipeline` line)
- `opensearch/` -> imported via `git subtree --squash` from branch `Opensearch`
- `cswspws25-WebCrawlerMain/` -> imported via `git subtree --squash` from branch `WebCrawlerMain`
- `cswspws25-m3-final/` -> imported via `git subtree --squash` from branch `m3-final`
- `frontend/` -> imported via `git subtree --squash` from branch `frontend/dashboard-ui`

## Notes

- The `n8n` setup scripts expect sibling directories listed above.
- Bundle archives are intentionally gitignored; fetch backups with `n8n/bundle_fetch_backups.sh` when needed.
