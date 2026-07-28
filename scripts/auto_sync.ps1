param(
    [int]$PollSeconds = 5
)

$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot

# Only these runtime files are committed and pushed automatically.
$AllowedPaths = @(
    'app.py',
    'database.py',
    'question_bank.py',
    'requirements.txt',
    '.streamlit/config.toml',
    'scripts/auto_sync.ps1'
)

Set-Location $Repo

function Get-AllowedChanges {
    $status = git status --porcelain --untracked-files=all
    foreach ($line in $status) {
        if ($line.Length -lt 4) { continue }
        $path = $line.Substring(3).Trim()
        if ($path -match ' -> ') { $path = ($path -split ' -> ')[-1] }
        if ($AllowedPaths -contains $path) { $path }
    }
}

Write-Host "Watching approved app files. Press Ctrl+C to stop."

while ($true) {
    $changes = @(Get-AllowedChanges | Select-Object -Unique)
    if ($changes.Count -gt 0) {
        git add -- $AllowedPaths
        $staged = git diff --cached --name-only
        if ($staged) {
            $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
            git commit -m "Auto-sync app changes ($stamp)"
            git push origin main
            Write-Host "Synced: $($staged -join ', ')"
        }
    }
    Start-Sleep -Seconds $PollSeconds
}
