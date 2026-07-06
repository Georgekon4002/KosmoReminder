@echo off
echo Building KosmoSMS Dashboard...
python -m PyInstaller KosmoSMS_Dashboard.spec --clean -y
echo Build completed successfully.
pause
