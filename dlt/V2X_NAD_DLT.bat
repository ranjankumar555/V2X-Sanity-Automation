@echo off

:1

adb1 forward tcp:3493 tcp:3493

adb1 forward tcp:3491 tcp:3491

timeout -t 5 /nobreak

goto 1
