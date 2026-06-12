<#
.SYNOPSIS
  Zip the built LayeredFS patch (out\01005940182ec000) into a versioned deliverable:
  out\STRAH_en_patch_switch_<ver>.zip
.PARAMETER Version
  Explicit version (e.g. "0.05"). When omitted, prompts to increment / enter / reuse.
#>
param([string]$Version)

$ErrorActionPreference = "Stop"
$patchDir = "out\01005940182ec000"
$prefix   = "dist\STRAH_en_patch_switch_"

if (-not (Test-Path $patchDir)) {
    throw "Patch folder not found: $patchDir  (run tools\STRAHLocalizationHelper.exe first)"
}

# Highest existing version, if any
$existing = Get-ChildItem "$prefix*.zip" -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.Name -match 'switch_(\d+\.\d+)\.zip$') { [decimal]$Matches[1] }
} | Sort-Object
$latest = if ($existing) { $existing[-1] } else { $null }

if (-not $Version) {
    if ($latest) {
        $next = "{0:0.00}" -f ($latest + 0.01)
        Write-Host "Latest existing version: $("{0:0.00}" -f $latest)"
        Write-Host "  [I] Increment to $next   (default)"
        Write-Host "  [S] Specific version"
        Write-Host "  [E] Existing $("{0:0.00}" -f $latest)   (overwrite)"
        $choice = (Read-Host "Choice [I/S/E]").Trim().ToUpper()
    } else {
        Write-Host "No existing versioned zip found - enter a version."
        $choice = "S"
    }
    switch ($choice) {
        "S"     { $Version = (Read-Host "Enter version (e.g. 0.05)").Trim() }
        "E"     { $Version = "{0:0.00}" -f $latest }
        default { $Version = "{0:0.00}" -f ($latest + 0.01) }   # I / Enter
    }
}

$dest = "$prefix$Version.zip"
New-Item -ItemType Directory -Force -Path "dist" | Out-Null
if (Test-Path $dest) { Write-Host "Overwriting $dest" -ForegroundColor Yellow }
Compress-Archive -Path $patchDir -DestinationPath $dest -Force
Write-Host "Wrote $dest" -ForegroundColor Green
