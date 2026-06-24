param(
  [string]$Config = ".\config\config.example.yaml"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-StarsCli {
  param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CliArgs
  )

  python -m github_stars_tool.cli --config $Config @CliArgs
}

function Show-Menu {
  Write-Host ""
  Write-Host "GitHub Stars Tool Menu"
  Write-Host "1. Bootstrap environment"
  Write-Host "2. Export stars (API)"
  Write-Host "3. Export stars (Browser)"
  Write-Host "4. Classify stars (Rules)"
  Write-Host "5. Classify stars (AI)"
  Write-Host "6. Import manual classification"
  Write-Host "7. Sync GitHub Lists"
  Write-Host "8. Audit GitHub Lists"
  Write-Host "9. Open manual examples folder"
  Write-Host "0. Exit"
  Write-Host ""
}

while ($true) {
  Show-Menu
  $choice = Read-Host "Choose an action"
  switch ($choice) {
    "1" {
      & ".\scripts\bootstrap.ps1"
    }
    "2" {
      Invoke-StarsCli export --mode api
    }
    "3" {
      Invoke-StarsCli export --mode browser
    }
    "4" {
      Invoke-StarsCli classify --mode rules
    }
    "5" {
      Invoke-StarsCli classify --mode ai
    }
    "6" {
      $inputPath = Read-Host "Enter JSON or CSV classification file path"
      if (-not $inputPath) {
        Write-Host "No file selected."
        continue
      }
      Invoke-StarsCli import-classification --input $inputPath
    }
    "7" {
      Write-Host "Make sure Chrome is logged into GitHub and remote debugging is enabled on port 9222."
      Invoke-StarsCli sync-lists
    }
    "8" {
      Invoke-StarsCli audit-lists
    }
    "9" {
      Start-Process explorer.exe (Resolve-Path ".\examples\manual").Path
    }
    "0" {
      break
    }
    default {
      Write-Host "Unsupported option: $choice"
    }
  }
}
