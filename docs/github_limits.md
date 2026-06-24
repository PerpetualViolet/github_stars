# GitHub Limits

## Public constraints

- Star export is supported through GitHub APIs.
- GitHub Lists management does not have a stable public API.
- List creation and membership updates therefore rely on browser automation.

## Operational implications

- Prefer token/API mode for export and metadata collection.
- Prefer browser mode only for list sync and auditing.
- Keep all intermediate artifacts on disk for replay and recovery.
