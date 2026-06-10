# Original Chinese-build font setup (MiSans). Kept for reference; the English
# build uses Inter via scripts/download_fonts.ps1.
mkdir files/fonts/ -Force
mkdir out/ -Force
Invoke-WebRequest -Uri "https://hyperos.mi.com/font-download/MiSans.zip" -OutFile "out/MiSans.zip"
Expand-Archive -Path "out/MiSans.zip" -DestinationPath "out/"
Copy-Item -Path "out/MiSans/otf/MiSans-Semibold.otf" -Destination "files/fonts/FOT-NEWRODINPRO-DB.ttf" -Force
Copy-Item -Path "out/MiSans/otf/MiSans-Medium.otf" -Destination "files/fonts/Default Font.ttf" -Force
