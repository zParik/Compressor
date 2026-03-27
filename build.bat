@echo off
setlocal enabledelayedexpansion
title SquishIt Builder

echo ============================================
echo  SquishIt - Build Script
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install from https://python.org
    pause
    exit /b 1
)

:: Install dependencies
echo [1/3] Installing Python dependencies...
pip install flask pyinstaller --quiet
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)

:: Download ffmpeg if not present
if not exist "ffmpeg\ffmpeg.exe" (
    echo [2/3] Downloading ffmpeg ^(this may take a minute^)...
    mkdir ffmpeg 2>nul

    powershell -Command "& { $url = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'; $out = 'ffmpeg_tmp.zip'; Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing }"
    if not exist "ffmpeg_tmp.zip" (
        echo ERROR: Could not download ffmpeg. Check your internet connection.
        pause
        exit /b 1
    )

    echo     Extracting ffmpeg...
    powershell -Command "& { Expand-Archive -Path 'ffmpeg_tmp.zip' -DestinationPath 'ffmpeg_extracted' -Force }"

    for /d %%d in (ffmpeg_extracted\ffmpeg-*) do (
        copy "%%d\bin\ffmpeg.exe" "ffmpeg\" >nul
        copy "%%d\bin\ffprobe.exe" "ffmpeg\" >nul
    )

    del ffmpeg_tmp.zip
    rmdir /s /q ffmpeg_extracted

    if not exist "ffmpeg\ffmpeg.exe" (
        echo ERROR: ffmpeg extraction failed.
        pause
        exit /b 1
    )
    echo     ffmpeg downloaded successfully.
) else (
    echo [2/3] ffmpeg already present, skipping download.
)

:: Build single-file exe
echo [3/3] Building SquishIt.exe ^(single file, may take a few minutes^)...
pyinstaller squishit.spec --noconfirm --clean --onefile
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  BUILD COMPLETE!
echo ============================================
echo.
echo  Single file: dist\SquishIt.exe
echo  Send just that one file to your friends!
echo  Double-click to run - no installs needed.
echo.
pause
