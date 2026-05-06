@echo off
echo [%date% %time%] ?????? %~n0 >> "C:\Users\admin\Documents\CodeProject\Python\switchoff\utility_monitor\scripts\execution_log.txt"
cd /d "C:\Users\admin\Documents\CodeProject\Python\switchoff\utility_monitor\scripts"
call "C:\Users\admin\Documents\CodeProject\Python\venv\Scripts\activate.bat"
python "C:\Users\admin\Documents\CodeProject\Python\switchoff\utility_monitor\scripts\comm_switchoff.py"
set EXIT_CODE=%errorlevel%
call "C:\Users\admin\Documents\CodeProject\Python\venv\Scripts\deactivate.bat"
if %EXIT_CODE% EQU 0 (
    echo [%date% %time%] ???????? ?????????? %~n0 >> "C:\Users\admin\Documents\CodeProject\Python\switchoff\utility_monitor\scripts\execution_log.txt"
) else (
    echo [%date% %time%] ?????? ?????????? %~n0 (???: %EXIT_CODE%) >> "C:\Users\admin\Documents\CodeProject\Python\switchoff\utility_monitor\scripts\execution_log.txt"
)
exit %EXIT_CODE%
