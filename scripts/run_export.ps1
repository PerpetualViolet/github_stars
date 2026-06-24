param(
  [ValidateSet("api", "browser")]
  [string]$Mode = "api",
  [string]$Config = ".\config\config.example.yaml"
)

python -m github_stars_tool.cli --config $Config export --mode $Mode
