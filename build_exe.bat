@echo off
REM build_exe.bat — Build the Depreciation Calculator as a Windows .exe
REM
REM Prerequisites
REM -------------
REM   pip install pyinstaller openpyxl
REM
REM Usage
REM -----
REM   Double-click this file, or run from Command Prompt:
REM     build_exe.bat
REM
REM Output
REM ------
REM   dist\DepreciationCalculator\DepreciationCalculator.exe

echo ======================================================
echo  Depreciation Calculator — EXE Builder
echo ======================================================
echo.

REM Check Python is available
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found on PATH.
    echo Please install Python 3.8+ from https://www.python.org/
    pause
    exit /b 1
)

REM Install / upgrade required packages
echo Installing dependencies...
python -m pip install --upgrade pyinstaller openpyxl
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

REM Remove previous build artefacts
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

REM Run PyInstaller
echo.
echo Building executable...
python -m PyInstaller depreciation_app.spec
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo ======================================================
echo  Build successful!
echo  Executable: dist\DepreciationCalculator\DepreciationCalculator.exe
echo ======================================================
echo.
pause
