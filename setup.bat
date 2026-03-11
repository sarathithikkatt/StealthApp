@echo off
setlocal

echo === StealthApp Setup ===
echo.

REM Find python
where python3.13 >nul 2>&1 && set PY=python3.13 || (
    where python3 >nul 2>&1 && set PY=python3 || (
        where python >nul 2>&1 && set PY=python || (
            echo [ERROR] Python not found. Install Python 3.11+ from https://python.org
            pause & exit /b 1
        )
    )
)

echo [1/4] Using: %PY%
%PY% --version

echo.
echo [2/4] Creating virtual environment...
if exist .venv (
    echo       .venv already exists, skipping.
) else (
    %PY% -m venv .venv
    if errorlevel 1 ( echo [ERROR] venv creation failed. & pause & exit /b 1 )
    echo       Done.
)

echo.
echo [3/4] Activating and installing dependencies...
call .venv\Scripts\activate.bat
pip install --upgrade pip -q
pip install -e .
if errorlevel 1 ( echo [ERROR] pip install failed. & pause & exit /b 1 )
echo       Done.

echo.
echo [4/4] Creating default config if missing...
if not exist config.json (
    copy /y config.example.json config.json >nul
    echo       config.json created. Edit it before running.
) else (
    echo       config.json already exists.
)

echo.
echo ============================================
echo  Setup complete!
echo  Run:  .venv\Scripts\activate
echo        stealthapp
echo ============================================
pause
