@echo off
setlocal
echo Salve e feche o Power BI Desktop antes de continuar.
echo Selecione o RetailAnalytics.pbip ANTIGO que ja funciona com seus dados.
echo Sera feito um backup do relatorio; o modelo e a conexao serao preservados.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Atualizar-Layout.ps1"
set "layout_result=%ERRORLEVEL%"
echo.
pause
exit /b %layout_result%
