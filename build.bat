@echo off
setlocal
pushd "%~dp0"

set VENV_PY=%~dp0.venv\Scripts\python.exe
if exist "%VENV_PY%" (
  set PYEXE=%VENV_PY%
) else (
  set PYEXE=python
)

"%PYEXE%" -m pip show pyinstaller >nul 2>&1
if errorlevel 1 "%PYEXE%" -m pip install pyinstaller

if exist "%~dp0dist\FastCap.exe" (
  taskkill /IM FastCap.exe /F >nul 2>&1
  del /f /q "%~dp0dist\FastCap.exe" >nul 2>&1
)

"%PYEXE%" -m PyInstaller --clean -y FastCap.spec
if errorlevel 1 (
  echo Build failed
  exit /b 1
)

echo Build complete: "%~dp0dist\FastCap.exe"
popd