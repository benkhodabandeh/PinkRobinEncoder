param(
    [string]$RepoName = "PinkRobinEncoder",
    [ValidateSet("public", "private")]
    [string]$Visibility = "public"
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

# --- 0. Preconditions -------------------------------------------------------
Write-Step "Preconditions"
git --version | Out-Null
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot
if (!(Test-Path ".git")) { Write-Error "No .git here. Run from the repo root."; exit 1 }

# --- 1. GitHub CLI (download portable if missing; github.com is reachable) --
Write-Step "GitHub CLI"
$ghCmd = Get-Command gh -ErrorAction SilentlyContinue
$gh = if ($ghCmd) { $ghCmd.Source } else { $null }
if (-not $gh) {
    Write-Host "gh not found - downloading portable gh ..."
    $toolsDir = Join-Path $repoRoot ".tools"
    New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
    $latest = Invoke-RestMethod "https://api.github.com/repos/cli/cli/releases/latest"
    $asset = @($latest.assets | Where-Object { $_.name -like "*windows*amd64.zip" })[0]
    if (-not $asset) { throw "No windows-amd64 gh asset found in latest release." }
    Write-Host "Latest gh: $($latest.tag_name) ($($asset.name))"
    $zipUrl = $asset.browser_download_url
    $zipPath = Join-Path $toolsDir "gh.zip"
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath
    Expand-Archive -Path $zipPath -DestinationPath (Join-Path $toolsDir "gh") -Force
    $gh = Get-ChildItem -Path (Join-Path $toolsDir "gh") -Recurse -Filter "gh.exe" | Select-Object -First 1 -ExpandProperty FullName
    Write-Host "gh portable ready: $gh"
}

# --- 2. Auth (the ONE interactive step; browser/device flow, once ever) -----
Write-Step "GitHub auth"
& $gh auth status 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Not logged in - starting browser login (one-time) ..." -ForegroundColor Yellow
    & $gh auth login
    & $gh auth status
    if ($LASTEXITCODE -ne 0) { Write-Error "Auth failed. Aborting."; exit 1 }
}
$owner = (& $gh api user -q .login).Trim()
Write-Host "Logged in as: $owner"

# --- 3. Repo: reuse if it exists, else create -------------------------------
Write-Step "Repository $owner/$RepoName"
$repoFull = "$owner/$RepoName"
& $gh repo view $repoFull --json name 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating $Visibility repo $repoFull ..."
    & $gh repo create $RepoName --$Visibility --description "Pink Robin Encoder - cinema-grade FFmpeg encoding (Windows)"
} else {
    Write-Host "Repo already exists - reusing it."
}

# --- 4. Push ----------------------------------------------------------------
Write-Step "Push"
$remote = (git remote get-url origin 2>$null)
$wantUrl = "https://github.com/$repoFull.git"
if (-not $remote) {
    git remote add origin $wantUrl
} elseif ($remote -ne $wantUrl) {
    Write-Host "Remote points at $remote - repointing to $wantUrl"
    git remote set-url origin $wantUrl
}
git add -A
$status = git status --porcelain
if ($status) {
    git commit -m "Pink Robin Encoder: push to GitHub" | Out-Null
    Write-Host "Committed pending changes."
} else {
    Write-Host "Working tree clean - nothing new to commit."
}
git push -u origin main

# --- 5. What to watch --------------------------------------------------------
Write-Step "Done - monitor here"
Write-Host "CI:            https://github.com/$repoFull/actions/workflows/ci.yml" -ForegroundColor Green
Write-Host "FFmpeg build:  https://github.com/$repoFull/actions/workflows/build-ffmpeg.yml" -ForegroundColor Green
Write-Host "App build:     https://github.com/$repoFull/actions/workflows/build-app.yml" -ForegroundColor Green
Write-Host ""
Write-Host "Next: run the 'Build custom FFmpeg (Windows)' workflow, wait for"
Write-Host "RESULT: PASSED, then run the 'Build Pink Robin Encoder' workflow."
Write-Host "The CI workflow runs automatically on this push - check it first."
