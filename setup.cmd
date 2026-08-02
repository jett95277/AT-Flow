@echo off
setlocal
python "%~dp0scripts\setup.py" %*
exit /b %ERRORLEVEL%
