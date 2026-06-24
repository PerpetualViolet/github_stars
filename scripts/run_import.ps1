param(
  [Parameter(Mandatory = $true)]
  [string]$Input,
  [string]$Config = ".\config\config.example.yaml"
)

python -m github_stars_tool.cli --config $Config import-classification --input $Input
