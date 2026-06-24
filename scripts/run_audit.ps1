param(
  [string]$Config = ".\config\config.example.yaml"
)

python -m github_stars_tool.cli --config $Config audit-lists
