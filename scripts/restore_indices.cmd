@echo off
setlocal

set OS=https://localhost:9200

echo Waiting for OpenSearch...
:wait
curl -k -u admin:admin %OS% >nul 2>&1
if errorlevel 1 (
  timeout /t 2 >nul
  goto wait
)

echo OpenSearch is up.
echo.

for %%f in (..\indices\*.json) do (
  echo Creating index: %%~nf
  curl -k -u admin:admin -X PUT "%OS%/%%~nf" ^
    -H "Content-Type: application/json" ^
    --data-binary "@%%f"
  echo.
)

echo All indices processed.
pause
