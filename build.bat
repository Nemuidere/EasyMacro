@echo off
REM EasyMacro Development Build Script
REM This script sets up the development environment and runs the application

echo ========================================
echo EasyMacro Development Build
echo ========================================
echo.

REM Check if virtual environment exists
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        exit /b 1
    )
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    exit /b 1
)

REM Install/upgrade dependencies
echo.
echo Installing dependencies...
pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: Failed to upgrade pip
    exit /b 1
)

pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install requirements.txt
    exit /b 1
)

pip install -r requirements-dev.txt
if errorlevel 1 (
    echo ERROR: Failed to install requirements-dev.txt
    exit /b 1
)

REM Create data directory if it doesn't exist
if not exist "data" mkdir data
if not exist "data\logs" mkdir data\logs

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Available commands:
echo   build.bat run     - Run the application
echo   build.bat test    - Run tests
echo   build.bat lint    - Run linting
echo   build.bat clean   - Clean build artifacts
echo.

REM Handle command line argument
if "%~1"=="" goto :end
if /i "%~1"=="run" goto :run
if /i "%~1"=="test" goto :test
if /i "%~1"=="lint" goto :lint
if /i "%~1"=="clean" goto :clean
echo Unknown command: %~1
echo Use: run, test, lint, or clean
goto :end

:run
echo.
echo Starting EasyMacro...
echo.
python -m src.main
goto :end

:test
echo.
echo Running tests...
echo.
pytest
goto :end

:lint
echo.
echo Running linting...
echo.
python -m py_compile src\main.py
echo Syntax check passed.
goto :end

:clean
echo.
echo Cleaning build artifacts...
echo.
if exist "__pycache__" rmdir /s /q "__pycache__"
if exist "src\__pycache__" rmdir /s /q "src\__pycache__"
if exist "tests\__pycache__" rmdir /s /q "tests\__pycache__"
for /r %%i in (*.pyc) do del /q "%%i" 2>nul
for /r %%i in (*.pyo) do del /q "%%i" 2>nul
for /r %%i in (.pytest_cache) do rmdir /s /q "%%i" 2>nul
echo Clean complete.
goto :end

:end
echo.
echo Done.
