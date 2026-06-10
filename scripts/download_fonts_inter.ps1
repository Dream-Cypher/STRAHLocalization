# OPT-IN: replace the game fonts with Inter (Western font, OFL / Google Fonts).
#   FOT-NEWRODINPRO-DB (DemiBold, dialogue) <- Inter SemiBold
#   Default Font       (Medium, UI)         <- Inter Medium
# Uses the TTFs staged in files/_optional_fonts/ if present, else downloads Inter.
# After running this, rebuild the patch. To revert to the original font, delete
# files/fonts/*.ttf (or run download_fonts.ps1).
mkdir files/fonts/ -Force | Out-Null
$staged = "files/_optional_fonts"
if ((Test-Path "$staged/FOT-NEWRODINPRO-DB.ttf") -and (Test-Path "$staged/Default Font.ttf")) {
    Copy-Item "$staged/FOT-NEWRODINPRO-DB.ttf" "files/fonts/FOT-NEWRODINPRO-DB.ttf" -Force
    Copy-Item "$staged/Default Font.ttf"       "files/fonts/Default Font.ttf"       -Force
    Write-Output "Inter fonts copied from $staged into files/fonts/."
} else {
    mkdir out/ -Force | Out-Null
    Invoke-WebRequest -Uri "https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip" -OutFile "out/Inter.zip"
    Expand-Archive -Path "out/Inter.zip" -DestinationPath "out/Inter/" -Force
    Copy-Item "out/Inter/extras/ttf/Inter-SemiBold.ttf" "files/fonts/FOT-NEWRODINPRO-DB.ttf" -Force
    Copy-Item "out/Inter/extras/ttf/Inter-Medium.ttf"   "files/fonts/Default Font.ttf"       -Force
    Write-Output "Inter fonts downloaded into files/fonts/."
}
