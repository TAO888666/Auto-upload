@echo off
setlocal EnableExtensions
TITLE One-Click Starter for social-auto-upload

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "FFMPEG_DIR=%ROOT%tools\ffmpeg"
if exist "%FFMPEG_DIR%\ffmpeg.exe" (
  set "PATH=%FFMPEG_DIR%;%PATH%"
)

echo ==================================================
echo  social-auto-upload One-Click Starter
echo ==================================================
echo.

echo [1/7] Checking Python...
set "PYTHON_CMD="
py -3 --version >nul 2>nul && set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD (
  python --version >nul 2>nul && set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
  echo [ERROR] Python 3.10+ was not found.
  echo Please install Python first, then run this script again.
  pause
  exit /b 1
)

echo [2/7] Checking Node.js / npm...
npm --version >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm was not found.
  echo Please install Node.js first, then run this script again.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [3/7] Creating Python virtual environment...
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Failed to create .venv
    pause
    exit /b 1
  )
) else (
  echo [3/7] Reusing existing Python virtual environment...
)

set "VENV_PY=%ROOT%.venv\Scripts\python.exe"
set "VENV_ACTIVATE=%ROOT%.venv\Scripts\activate.bat"

echo [4/7] Installing backend dependencies...
call "%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 (
  echo [ERROR] Failed to upgrade pip.
  pause
  exit /b 1
)

call "%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Failed to install requirements.txt
  pause
  exit /b 1
)

call "%VENV_PY%" -m pip install patchright==1.58.2
if errorlevel 1 (
  echo [ERROR] Failed to install patchright.
  pause
  exit /b 1
)

if not exist "conf.py" (
  echo [5/7] Creating conf.py from conf.example.py...
  copy /Y "conf.example.py" "conf.py" >nul
)

echo [6/7] Installing browser runtime and frontend dependencies...
call "%VENV_PY%" -m patchright install chromium
if errorlevel 1 (
  echo [ERROR] Failed to install Chromium runtime for patchright.
  pause
  exit /b 1
)

pushd "%ROOT%sau_frontend"
if not exist "node_modules" (
  call npm install
  if errorlevel 1 (
    popd
    echo [ERROR] Failed to install frontend dependencies.
    pause
    exit /b 1
  )
) else (
  echo Frontend dependencies already installed.
)
popd

if not exist "%FFMPEG_DIR%\ffmpeg.exe" (
  echo [WARN] Bundled FFmpeg was not found under tools\ffmpeg
  echo Some AI media features may not work until FFmpeg is available.
)

echo [7/7] Starting backend and frontend...
start "SAU Backend" cmd /k "cd /d ""%ROOT%"" && set ""PATH=%FFMPEG_DIR%;%%PATH%%"" && call ""%VENV_ACTIVATE%"" && python sau_backend.py"
start "SAU Frontend" cmd /k "cd /d ""%ROOT%sau_frontend"" && npm run dev -- --host 0.0.0.0"

echo.
echo ==================================================
echo  Done.
echo  Backend:  http://localhost:5409
echo  Frontend: http://localhost:5173
echo ==================================================
echo.
echo This window will close in 12 seconds...
timeout /t 12 /nobreak > nul
