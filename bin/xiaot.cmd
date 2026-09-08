@echo off
rem xiaot\bin\xiaot.cmd — 编排 CLI 薄壳（PATH 用）
rem 用法：xiaot task "..." / xiaot inject --dir <project>
rem PYTHONPATH 指向 lib/python（含 xiaot 编排包与 xiaot_memory）
set PYTHONPATH=%~dp0..\lib\python
python -m xiaot %*
exit /b %errorlevel%
