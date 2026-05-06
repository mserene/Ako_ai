@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem Compatibility wrapper. The stable developer build pipeline lives in:
rem   build_onefolder_runtime_bootstrap.bat

cd /d "%~dp0"

echo [INFO] build_onefolder.bat is deprecated.
echo [INFO] Delegating to build_onefolder_runtime_bootstrap.bat.
echo.

call "%~dp0build_onefolder_runtime_bootstrap.bat"
exit /b %ERRORLEVEL%
