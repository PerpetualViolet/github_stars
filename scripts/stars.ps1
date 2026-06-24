param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Args
)

python -m github_stars_tool.cli @Args
