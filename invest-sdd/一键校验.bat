@echo off
pushd "%~dp0"
python -X utf8 bin\guard_invest.py %*
set RC=%ERRORLEVEL%
if "%~1"=="" pause
popd
exit /b %RC%
