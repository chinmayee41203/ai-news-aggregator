# Uploads the values GitHub Actions needs from your .env to the repo's
# encrypted GitHub Secrets, using the GitHub CLI (gh). Values are piped
# straight to gh and never printed.
#
# Run from the project folder:
#   powershell -ExecutionPolicy Bypass -File scripts\upload_secrets.ps1
#
# DATABASE_URL on GitHub must be the Neon URL, so it is read from
# PRODUCTION_DATABASE_URL in your .env (your local DATABASE_URL stays Docker).

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) { throw ".env not found at $envFile" }

$values = @{}
foreach ($line in Get-Content $envFile) {
    if ($line -match '^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$') { $values[$matches[1]] = $matches[2].Trim() }
}

# GitHub secret name  ->  key in .env
$map = [ordered]@{
    "DATABASE_URL"       = "PRODUCTION_DATABASE_URL"
    "GEMINI_API_KEY"     = "GEMINI_API_KEY"
    "YOUTUBE_API_KEY"    = "YOUTUBE_API_KEY"
    "GUARDIAN_API_KEY"   = "GUARDIAN_API_KEY"
    "MY_EMAIL"           = "MY_EMAIL"
    "EMAIL_PROVIDER"     = "EMAIL_PROVIDER"
    "GMAIL_SENDER"       = "GMAIL_SENDER"
    "GMAIL_APP_PASSWORD" = "GMAIL_APP_PASSWORD"
}

Push-Location $root
try {
    foreach ($secret in $map.Keys) {
        $value = $values[$map[$secret]]
        if ([string]::IsNullOrWhiteSpace($value)) {
            Write-Host "skip  $secret  ($($map[$secret]) is empty in .env)"
            continue
        }
        $value | gh secret set $secret
        Write-Host "set   $secret"
    }
} finally {
    Pop-Location
}
Write-Host "`nDone. Check them at: GitHub repo -> Settings -> Secrets and variables -> Actions"
