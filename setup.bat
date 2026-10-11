@echo off
echo ============================================
echo   Club Ledger - Setup
echo ============================================
echo.

REM Used to check with "where python", but "where" itself lives at
REM C:\Windows\System32\where.exe. If a user's PATH is missing System32
REM (this happened in practice), "where" fails on its own and this check
REM wrongly reports "Python not found" even though "python" works fine
REM when typed directly. Checking "python --version" directly avoids
REM depending on "where" at all.
python --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10 or newer:
    echo         https://www.python.org/downloads/
    echo         IMPORTANT: check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo Creating virtual environment in folder "venv"...
python -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create the virtual environment.
    pause
    exit /b 1
)

echo Installing packages, please wait...
call venv\Scripts\activate.bat
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Package install failed. Check the messages above, or your
    echo         internet connection, then try again.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Setup complete! Double-click run.bat to start.
echo ============================================
pause
