# Runbook

## Fresh machine

1. Install Python 3.11+
2. Install Node.js 20+
3. Clone or copy this project directory
4. Copy `.env.example` to `.env`
5. Run `.\scripts\bootstrap.ps1`
6. Run `.\scripts\menu.ps1`

## Official operator flows

### Rules path

1. Export stars
2. Classify with local rules
3. Sync GitHub Lists
4. Audit GitHub Lists

### AI path

1. Export stars
2. Configure `OPENAI_API_KEY` and `llm.*` fields
3. Classify with AI
4. Review generated outputs
5. Sync GitHub Lists
6. Audit GitHub Lists

### Manual path

1. Export stars
2. Copy a template from `examples/manual/`
3. Edit JSON or CSV manually
4. Run `import-classification`
5. Review regenerated outputs
6. Sync GitHub Lists
7. Audit GitHub Lists

## Browser attach example

```powershell
& 'C:\Program Files\Google\Chrome\Application\chrome.exe' `
  --remote-debugging-port=9222 `
  --user-data-dir="$env:LOCALAPPDATA\Google\Chrome\User Data" `
  --profile-directory=Default `
  https://github.com
```

## Minimal command reference

```powershell
python -m github_stars_tool.cli --config .\config\config.example.yaml export --mode api
python -m github_stars_tool.cli --config .\config\config.example.yaml classify --mode rules
python -m github_stars_tool.cli --config .\config\config.example.yaml classify --mode ai
python -m github_stars_tool.cli --config .\config\config.example.yaml import-classification --input .\examples\manual\classification.manual.example.json
python -m github_stars_tool.cli --config .\config\config.example.yaml sync-lists
python -m github_stars_tool.cli --config .\config\config.example.yaml audit-lists
```
