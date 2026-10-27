@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Building FakeGameStatus.exe ===
py -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo.
    echo Python was not found. Install it from python.org and tick "Add to PATH".
    pause
    exit /b 1
)
py -m PyInstaller --onefile --noconsole --clean --name FakeGameStatus FakeGameStatus.pyw
echo.
if exist "dist\FakeGameStatus.exe" (
    copy /y "dist\FakeGameStatus.exe" "FakeGameStatus.exe" >nul
    echo Done!  FakeGameStatus.exe is ready in this folder.
    rmdir /s /q build >nul 2>&1
    del /q FakeGameStatus.spec >nul 2>&1
) else (
    echo Build failed - see the messages above.
)
pause
