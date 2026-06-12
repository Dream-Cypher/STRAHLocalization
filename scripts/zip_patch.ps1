<#
.SYNOPSIS
  Zip the built LayeredFS patch (out\01005940182ec000) into a versioned deliverable:
  dist\STRAH_en_patch_switch_<ver>.zip

  The archive is laid out as  atmosphere\contents\01005940182ec000\...  so it can
  be extracted directly onto the root of an Atmosphere CFW SD card.
.PARAMETER Version
  Explicit version (e.g. "0.05"). When omitted, prompts to increment / enter / reuse.
#>
param([string]$Version)

$ErrorActionPreference = "Stop"
$patchDir = "out\01005940182ec000"
$prefix   = "dist\STRAH_en_patch_switch_"
$entryPrefix = "atmosphere/contents/01005940182ec000"

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
if (Test-Path $dest) {
    Write-Host "Overwriting $dest" -ForegroundColor Yellow
    Remove-Item $dest -Force
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$patchRoot = (Resolve-Path $patchDir).Path.TrimEnd('\')
$zip = [System.IO.Compression.ZipFile]::Open($dest, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    Get-ChildItem -Path $patchDir -Recurse -File | ForEach-Object {
        $relPath = $_.FullName.Substring($patchRoot.Length + 1).Replace('\', '/')
        $entryName = "$entryPrefix/$relPath"
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $zip, $_.FullName, $entryName, [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
    }
} finally {
    $zip.Dispose()
}

Write-Host "Wrote $dest" -ForegroundColor Green
Write-Host "Layout: atmosphere/contents/01005940182ec000/... (extract to SD card root)" -ForegroundColor Green
