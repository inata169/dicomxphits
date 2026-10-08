@echo off
setlocal

rem Launch the independent PHITS ROI GUI from this checkout's virtual environment.
set "ProjectRoot=%~dp0"
set "PythonExe=%ProjectRoot%.venv\Scripts\python.exe"
set "GuiScript=%ProjectRoot%tools\phits_roi_stats_gui.py"

if not exist "%PythonExe%" (
  echo Missing virtual environment Python: "%PythonExe%". 1>&2
  exit /b 1
)

pushd "%ProjectRoot%" || exit /b 1
set "Path=%ProjectRoot%.venv\Scripts;%Path%"
"%PythonExe%" "%GuiScript%"
set "ExitCode=%ERRORLEVEL%"
popd
endlocal & exit /b %ExitCode%
