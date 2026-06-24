# GitHub Stars Tool

Portable workflow for exporting GitHub stars, classifying them, syncing GitHub Lists, and auditing the final result.

This project is designed to run in a fresh directory on another machine. It supports three official classification paths:

1. local rules
2. AI classification through an OpenAI-compatible API
3. manual classification by editing JSON or CSV files

## What it does

- Export stars through GitHub GraphQL with a token
- Export stars through a logged-in browser as a fallback
- Generate classification outputs in `json`, `csv`, and `md`
- Import a manually edited classification file
- Create and sync GitHub Lists through browser automation
- Audit whether GitHub List membership matches the classification file

## Quick start

1. Install `Python 3.11+` and `Node.js 20+`
2. Copy `.env.example` to `.env`
3. Review `config/config.example.yaml`
4. Bootstrap:

```powershell
.\scripts\bootstrap.ps1
```

5. Run the interactive menu:

```powershell
.\scripts\menu.ps1
```

If you prefer direct commands, the canonical entrypoint is:

```powershell
python -m github_stars_tool.cli --config .\config\config.example.yaml <command>
```

## Recommended flows

### Flow A: API export + rules classify

```powershell
python -m github_stars_tool.cli --config .\config\config.example.yaml export --mode api
python -m github_stars_tool.cli --config .\config\config.example.yaml classify --mode rules
python -m github_stars_tool.cli --config .\config\config.example.yaml sync-lists
python -m github_stars_tool.cli --config .\config\config.example.yaml audit-lists
```

### Flow B: API export + AI classify

```powershell
python -m github_stars_tool.cli --config .\config\config.example.yaml export --mode api
python -m github_stars_tool.cli --config .\config\config.example.yaml classify --mode ai
```

Then review the generated classification files before syncing lists.

### Flow C: API export + manual classify

1. Export stars
2. Copy one of these templates and edit it:
   - `examples/manual/classification.manual.example.json`
   - `examples/manual/classification.manual.example.csv`
3. Import the edited file:

```powershell
python -m github_stars_tool.cli --config .\config\config.example.yaml import-classification --input .\your_manual_file.json
```

The import command validates structure, auto-fills missing GitHub URLs from `full_name`, regenerates the standard `json/csv/md` outputs, and stops on duplicate repositories.

## Manual classification format

Required fields per repository:

- `category`
- `full_name` in `owner/repo` format

Optional fields:

- `url`
- `language`
- `stars`
- `topics`
- `description`
- `reason`
- `list_description`

JSON accepts either:

- a top-level object with `repositories`
- or a plain array of repository entries

CSV requires at least the `category` and `full_name` columns.

## GitHub token

Set `GITHUB_TOKEN` in your environment.

Recommended token types:

- classic personal access token
- or a fine-grained token that can read the signed-in user's starred repositories

The tool does not hardcode token class. It only checks whether the token can successfully query GitHub.

## AI provider config

The AI classifier is config-driven and assumes an OpenAI-compatible API surface.

Config fields:

- `llm.provider`
- `llm.base_url`
- `llm.endpoint`
  - `chat_completions`
  - `responses`
- `llm.model`
- `llm.structured_output`
  - `json_object`
  - `off`
- `llm.temperature`

Recommended default:

- `endpoint: chat_completions`
- `structured_output: json_object`

If the provider returns an HTML challenge page such as Cloudflare protection, the tool now reports that explicitly instead of failing with a vague parse error.

## GitHub Lists limitation

GitHub has public API support for starring data, but not a stable public API for GitHub Lists management. Because of that:

- `export` prefers API mode
- `sync-lists` and `audit-lists` use browser automation

## Directory layout

- `config/` configuration templates
- `examples/manual/` editable manual classification templates
- `src/github_stars_tool/` Python CLI
- `data/raw/` exported star data
- `data/normalized/` normalized star data
- `data/classification/` classification outputs
- `data/audit/` sync state and audit reports
- `scripts/` bootstrap, menu, and helper scripts

## Notes

- Do not run `sync-lists` and `audit-lists` in parallel
- Run `audit-lists` only after `sync-lists`
- If `github.user` is blank, sync derives the currently logged-in GitHub account from the browser session
- Runtime data under `data/` is ignored by `.gitignore`, so the repository stays publishable
