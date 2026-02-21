@echo off
REM start_engine.bat — Launch the Multi-Regime Engine
REM Configure paths below or set environment variables

SET VENV_PATH=%MULTIREGIME_VENV%
IF "%VENV_PATH%"=="" SET VENV_PATH=C:\MultiRegime\venv

SET ENGINE_PATH=%MULTIREGIME_ENGINE%
IF "%ENGINE_PATH%"=="" SET ENGINE_PATH=C:\MultiRegime\engine

SET LOG_DIR=%MULTIREGIME_LOGS%
IF "%LOG_DIR%"=="" SET LOG_DIR=C:\MultiRegime\logs

SET PYTHON_EXE=%VENV_PATH%\Scripts\python.exe
SET MAIN_SCRIPT=%ENGINE_PATH%\main.py

IF NOT EXIST "%PYTHON_EXE%" (
    echo ERROR: Python not found at %PYTHON_EXE%
    pause
    exit /b 1
)

IF NOT EXIST "%MAIN_SCRIPT%" (
    echo ERROR: Engine script not found at %MAIN_SCRIPT%
    pause
    exit /b 1
)

IF NOT EXIST "%LOG_DIR%" mkdir "%LOG_DIR%"

echo Starting Multi-Regime Engine...
echo   Python: %PYTHON_EXE%
echo   Script: %MAIN_SCRIPT%

cd /d "%ENGINE_PATH%"
"%PYTHON_EXE%" "%MAIN_SCRIPT%" --serve --log-dir "%LOG_DIR%"
