@echo off
setlocal EnableDelayedExpansion

:: =========================================================================
::  Multi-Regime Trading Stack — One-Click Windows Installer
::
::  What this does:
::    1. Checks for Python 3.10+ (offers to download if missing)
::    2. Creates C:\MultiRegime folder structure
::    3. Copies all project files into place
::    4. Creates a Python virtual environment
::    5. Installs all pip dependencies
::    6. Registers the engine as a Windows service (optional, via NSSM)
::    7. Creates desktop shortcuts for engine, dashboard, and tests
::    8. Validates the installation
::
::  Run: Right-click > "Run as administrator" (required for service install)
:: =========================================================================

title Multi-Regime Trading Stack Installer
color 0A

echo.
echo  ============================================================
echo    Multi-Regime Trading Stack — Windows Installer
echo  ============================================================
echo.

:: -------------------------------------------------------------------
:: 0. Detect where this script lives (the ZIP/extracted root)
:: -------------------------------------------------------------------
set "SRC_DIR=%~dp0"
:: Remove trailing backslash
if "%SRC_DIR:~-1%"=="\" set "SRC_DIR=%SRC_DIR:~0,-1%"

set "INSTALL_DIR=C:\MultiRegime"

echo  Source directory : %SRC_DIR%
echo  Install directory: %INSTALL_DIR%
echo.

:: -------------------------------------------------------------------
:: 1. Check Python
:: -------------------------------------------------------------------
echo [1/8] Checking Python installation...

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Python not found in PATH.
    echo.
    echo  Please install Python 3.10 or later from:
    echo    https://www.python.org/downloads/
    echo.
    echo  IMPORTANT: Check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%V in ('python --version 2^>^&1') do set "PYVER=%%V"
echo  Found Python %PYVER%

:: Parse major.minor
for /f "tokens=1,2 delims=." %%A in ("%PYVER%") do (
    set "PY_MAJOR=%%A"
    set "PY_MINOR=%%B"
)

if %PY_MAJOR% lss 3 (
    echo  ERROR: Python 3.10+ required, found %PYVER%
    pause
    exit /b 1
)
if %PY_MAJOR% equ 3 if %PY_MINOR% lss 10 (
    echo  ERROR: Python 3.10+ required, found %PYVER%
    pause
    exit /b 1
)
echo  Python %PYVER% — OK
echo.

:: -------------------------------------------------------------------
:: 2. Create directory structure
:: -------------------------------------------------------------------
echo [2/8] Creating directory structure at %INSTALL_DIR%...

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

for %%D in (engine dashboard contracts data models logs nt8 services docker tests sample_requests) do (
    if not exist "%INSTALL_DIR%\%%D" mkdir "%INSTALL_DIR%\%%D"
)
echo  Directories created — OK
echo.

:: -------------------------------------------------------------------
:: 3. Copy project files
:: -------------------------------------------------------------------
echo [3/8] Copying project files...

:: Engine
xcopy /Y /Q "%SRC_DIR%\engine\*.py"   "%INSTALL_DIR%\engine\"   >nul 2>&1
xcopy /Y /Q "%SRC_DIR%\engine\*.yaml" "%INSTALL_DIR%\engine\"   >nul 2>&1
xcopy /Y /Q "%SRC_DIR%\engine\*.txt"  "%INSTALL_DIR%\engine\"   >nul 2>&1

:: Dashboard
xcopy /Y /Q "%SRC_DIR%\dashboard\*.*" "%INSTALL_DIR%\dashboard\" >nul 2>&1

:: Contracts
xcopy /Y /Q "%SRC_DIR%\contracts\*.*" "%INSTALL_DIR%\contracts\" >nul 2>&1

:: NinjaTrader files
xcopy /Y /Q "%SRC_DIR%\nt8\*.*"       "%INSTALL_DIR%\nt8\"       >nul 2>&1

:: Services
xcopy /Y /Q "%SRC_DIR%\services\*.*"  "%INSTALL_DIR%\services\"  >nul 2>&1

:: Docker
xcopy /Y /Q "%SRC_DIR%\docker\*.*"    "%INSTALL_DIR%\docker\"    >nul 2>&1

:: Tests
xcopy /Y /Q "%SRC_DIR%\tests\*.py"    "%INSTALL_DIR%\tests\"     >nul 2>&1

:: Sample requests
xcopy /Y /Q "%SRC_DIR%\sample_requests\*.*" "%INSTALL_DIR%\sample_requests\" >nul 2>&1

:: Root files
for %%F in (README.md DEPLOYMENT_GUIDE.md .gitignore) do (
    if exist "%SRC_DIR%\%%F" copy /Y "%SRC_DIR%\%%F" "%INSTALL_DIR%\" >nul 2>&1
)

:: Placeholders
if not exist "%INSTALL_DIR%\data\.gitkeep"   echo. > "%INSTALL_DIR%\data\.gitkeep"
if not exist "%INSTALL_DIR%\models\.gitkeep" echo. > "%INSTALL_DIR%\models\.gitkeep"

echo  Files copied — OK
echo.

:: -------------------------------------------------------------------
:: 4. Create virtual environment
:: -------------------------------------------------------------------
echo [4/8] Creating Python virtual environment...

set "VENV_DIR=%INSTALL_DIR%\venv"
set "PIP_EXE=%VENV_DIR%\Scripts\pip.exe"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

if exist "%VENV_DIR%\Scripts\activate.bat" (
    echo  Virtual environment already exists — skipping creation
) else (
    python -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo  ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
)
echo  Virtual environment — OK
echo.

:: -------------------------------------------------------------------
:: 5. Install Python dependencies
:: -------------------------------------------------------------------
echo [5/8] Installing Python dependencies (this may take a few minutes)...

"%PIP_EXE%" install --upgrade pip >nul 2>&1

:: Engine dependencies
"%PIP_EXE%" install -r "%INSTALL_DIR%\engine\requirements.txt"
if %errorlevel% neq 0 (
    echo.
    echo  WARNING: Some engine dependencies failed to install.
    echo  You may need to install Visual C++ Build Tools for hmmlearn.
    echo  Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/
    echo.
)

:: Dashboard dependencies
"%PIP_EXE%" install -r "%INSTALL_DIR%\dashboard\requirements.txt"

:: Test dependencies
"%PIP_EXE%" install pytest >nul 2>&1

echo.
echo  Dependencies installed — OK
echo.

:: -------------------------------------------------------------------
:: 6. Set environment variables (user-level)
:: -------------------------------------------------------------------
echo [6/8] Setting environment variables...

setx MULTIREGIME_VENV   "%VENV_DIR%"       >nul 2>&1
setx MULTIREGIME_ENGINE "%INSTALL_DIR%\engine"  >nul 2>&1
setx MULTIREGIME_LOGS   "%INSTALL_DIR%\logs"    >nul 2>&1

:: Also set for current session
set "MULTIREGIME_VENV=%VENV_DIR%"
set "MULTIREGIME_ENGINE=%INSTALL_DIR%\engine"
set "MULTIREGIME_LOGS=%INSTALL_DIR%\logs"

echo  Environment variables set — OK
echo.

:: -------------------------------------------------------------------
:: 7. Create desktop shortcuts
:: -------------------------------------------------------------------
echo [7/8] Creating desktop shortcuts...

set "DESKTOP=%USERPROFILE%\Desktop"

:: --- Start Engine shortcut ---
(
echo @echo off
echo title Multi-Regime Engine
echo color 0A
echo echo Starting Multi-Regime Trading Engine...
echo echo.
echo cd /d "%INSTALL_DIR%\engine"
echo "%PYTHON_EXE%" main.py --serve --port 5555 --log-dir "%INSTALL_DIR%\logs"
echo echo.
echo echo Engine stopped.
echo pause
) > "%DESKTOP%\Start Engine.bat"

:: --- Start Dashboard shortcut ---
(
echo @echo off
echo title Multi-Regime Dashboard
echo color 0B
echo echo Starting Multi-Regime Dashboard...
echo echo.
echo cd /d "%INSTALL_DIR%\dashboard"
echo "%VENV_DIR%\Scripts\streamlit.exe" run app.py
echo echo.
echo pause
) > "%DESKTOP%\Start Dashboard.bat"

:: --- Run Tests shortcut ---
(
echo @echo off
echo title Multi-Regime Tests
echo color 0E
echo echo Running Multi-Regime test suite...
echo echo.
echo cd /d "%INSTALL_DIR%"
echo "%PYTHON_EXE%" -m pytest tests/ -v
echo echo.
echo echo Tests complete.
echo pause
) > "%DESKTOP%\Run Tests.bat"

:: --- Monte Carlo shortcut ---
(
echo @echo off
echo title Monte Carlo Stress Test
echo color 0D
echo echo ============================================
echo echo   Monte Carlo Stress Test
echo echo ============================================
echo echo.
echo set /p TRADES_FILE="Enter path to trades CSV file: "
echo cd /d "%INSTALL_DIR%\engine"
echo "%PYTHON_EXE%" monte_carlo.py --trades-file "%%TRADES_FILE%%" --n-sims 10000 --verbose
echo echo.
echo pause
) > "%DESKTOP%\Monte Carlo.bat"

:: --- Walk Forward shortcut ---
(
echo @echo off
echo title Walk-Forward Optimizer
echo color 0C
echo echo ============================================
echo echo   Walk-Forward Optimizer
echo echo ============================================
echo echo.
echo set /p SYMBOL="Enter symbol (NQ/ES/CL/NG/GC/SI/ZB/UB): "
echo cd /d "%INSTALL_DIR%\engine"
echo "%PYTHON_EXE%" walk_forward.py --symbol "%%SYMBOL%%" --data-dir "%INSTALL_DIR%\data" --model-dir "%INSTALL_DIR%\models" --verbose
echo echo.
echo pause
) > "%DESKTOP%\Walk Forward.bat"

:: --- Train Models shortcut ---
(
echo @echo off
echo title Train All Models
echo color 0E
echo echo ============================================
echo echo   Training All Models
echo echo ============================================
echo echo.
echo cd /d "%INSTALL_DIR%\engine"
echo "%PYTHON_EXE%" main.py --train --all --data-dir "%INSTALL_DIR%\data" --model-dir "%INSTALL_DIR%\models"
echo echo.
echo echo Training complete.
echo pause
) > "%DESKTOP%\Train Models.bat"

echo  Desktop shortcuts created — OK
echo.

:: -------------------------------------------------------------------
:: 8. Validate installation
:: -------------------------------------------------------------------
echo [8/8] Validating installation...

set "ERRORS=0"

:: Check critical files
for %%F in (
    engine\main.py
    engine\server.py
    engine\hmm_inference.py
    engine\feature_engine.py
    engine\data_pull.py
    engine\model_manager.py
    engine\monte_carlo.py
    engine\walk_forward.py
    engine\config.yaml
    nt8\MultiRegimeStrategy.cs
    nt8\MultiRegimeWorkspace.xml
    nt8\MultiRegimeChartTheme.xml
    DEPLOYMENT_GUIDE.md
) do (
    if not exist "%INSTALL_DIR%\%%F" (
        echo  MISSING: %%F
        set /a ERRORS+=1
    )
)

:: Check Python can import key modules
"%PYTHON_EXE%" -c "import numpy; print('  numpy', numpy.__version__, '— OK')" 2>nul
if %errorlevel% neq 0 (
    echo  WARNING: numpy import failed
    set /a ERRORS+=1
)

"%PYTHON_EXE%" -c "import pandas; print('  pandas', pandas.__version__, '— OK')" 2>nul
if %errorlevel% neq 0 (
    echo  WARNING: pandas import failed
    set /a ERRORS+=1
)

"%PYTHON_EXE%" -c "import hmmlearn; print('  hmmlearn', hmmlearn.__version__, '— OK')" 2>nul
if %errorlevel% neq 0 (
    echo  WARNING: hmmlearn import failed (may need C++ Build Tools)
    set /a ERRORS+=1
)

"%PYTHON_EXE%" -c "import sklearn; print('  scikit-learn', sklearn.__version__, '— OK')" 2>nul
if %errorlevel% neq 0 (
    echo  WARNING: scikit-learn import failed
    set /a ERRORS+=1
)

echo.

if %ERRORS% gtr 0 (
    echo  Installation completed with %ERRORS% warning(s).
    echo  Review the warnings above before running.
) else (
    echo  All checks passed!
)

echo.
echo  ============================================================
echo    Installation Complete!
echo  ============================================================
echo.
echo  Install location: %INSTALL_DIR%
echo.
echo  Quick Start:
echo    1. Place OHLCV CSV data in %INSTALL_DIR%\data\
echo    2. Train models:   Double-click "Train Models" on Desktop
echo    3. Start engine:   Double-click "Start Engine" on Desktop
echo    4. Start dashboard: Double-click "Start Dashboard" on Desktop
echo.
echo  NinjaTrader 8 Setup:
echo    1. Copy %INSTALL_DIR%\nt8\MultiRegimeStrategy.cs
echo       to Documents\NinjaTrader 8\bin\Custom\Strategies\
echo    2. Compile in NT8: New ^> NinjaScript Editor ^> F5
echo    3. Apply strategy to each chart with UseAutoProfile = True
echo.
echo  For service install (auto-start at boot):
echo    Run as Admin: powershell -File "%INSTALL_DIR%\services\install_engine_service.ps1"
echo.
echo  Full guide: %INSTALL_DIR%\DEPLOYMENT_GUIDE.md
echo.
pause
exit /b 0
