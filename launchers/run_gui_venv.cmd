@echo off
setlocal

rem Launch the public dicomxphits GUI from the repository-local environment.
set "ProjectRoot=%~dp0.."
set "PythonExe=%ProjectRoot%\.venv\Scripts\python.exe"
set "VenvScripts=%ProjectRoot%\.venv\Scripts"

if not exist "%PythonExe%" (
  echo Missing virtual environment Python: %PythonExe%. Create the environment explicitly before running this launcher. 1>&2
  exit /b 1
)

set "Path=%VenvScripts%;%Path%"
"%PythonExe%" -m dicomxphits.gui
set "ExitCode=%ERRORLEVEL%"
endlocal & exit /b %ExitCode%
