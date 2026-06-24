param(
  [ValidateSet("rules", "ai")]
  [string]$Mode = "rules",
  [string]$Config = ".\config\config.example.yaml"
)

python -m github_stars_tool.cli --config $Config classify --mode $Mode
