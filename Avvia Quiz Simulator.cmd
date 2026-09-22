@echo off
cd /d "%~dp0"
if exist "dist\QuizSimulator\QuizSimulator.exe" (
    start "" "dist\QuizSimulator\QuizSimulator.exe"
    exit /b
)
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "run_quiz.py"
    exit /b
)
echo Eseguire prima scripts\setup.ps1 oppure usare il pacchetto completo.
pause
