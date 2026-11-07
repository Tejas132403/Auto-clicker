@echo off
title King Autonomous Bot (Quiz + Watch Video)
cd /d "%~dp0"
echo ============================================================
echo   KING AUTONOMOUS BOT: QUIZ -^> WATCH VIDEO
echo ============================================================
echo 1. Strictly enters Quiz section (ignores all other tasks)
echo 2. Answers all 25 questions with Gemini + skips ads
echo 3. Returns to Home screen, scrolls down to Watch Video
echo 4. Plays all video ads and claims rewards
echo.
echo Log file: bot_log.txt
echo.
".venv2\Scripts\python.exe" king_quiz_bot.py --open
echo.
pause
