# English build: NO font replacement by default.
# The original game font (FOT-NEWRODINPRO-DB = FONTWORKS New Rodin Pro) is a
# Japanese font that already includes full Latin glyphs, so English renders in
# the game's native typography with no replacement needed. (The Chinese build
# replaced the font only because the JP font lacks Simplified-Chinese hanzi.)
#
# Leaving files/fonts/ without any .ttf makes the helper skip font replacement.
#
# To OPT IN to a Western font (Inter) instead, run:   scripts/download_fonts_inter.ps1
# To use the original Chinese (MiSans) setup, run:     scripts/download_fonts_misans.ps1
mkdir files/fonts/ -Force | Out-Null
Write-Output "No font replacement (using the game's original font). Run download_fonts_inter.ps1 to switch to Inter."
