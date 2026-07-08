@echo off
echo Building KosmoReminder...
python -m PyInstaller KosmoReminder.spec --clean -y
if %errorlevel% neq 0 (
    echo Build failed!
    pause
    exit /b %errorlevel%
)
echo Build completed successfully.
pause
