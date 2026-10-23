@echo off
rem Developer-only build. Usage: tools\build.bat dev
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1" -Mode %*
exit /b %errorlevel%
