@echo off
title Train Quiz Answers (Gemini self-consistency)
cd /d "%~dp0"
echo This improves quiz_answers.json using Gemini majority voting.
echo.
".venv2\Scripts\python.exe" train_quiz.py --samples 3
echo.
pause
