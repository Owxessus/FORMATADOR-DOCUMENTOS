@echo off
rem Cria um atalho do Formatador na Área de Trabalho.
rem Coloque este arquivo na MESMA pasta do Formatador.exe e dê dois cliques.
set SCRIPT="%TEMP%\criar_atalho.vbs"
echo Set oWS = WScript.CreateObject("WScript.Shell") > %SCRIPT%
echo sLinkFile = oWS.SpecialFolders("Desktop") ^& "\Formatador de Relatorios.lnk" >> %SCRIPT%
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> %SCRIPT%
echo oLink.TargetPath = "%~dp0Formatador.exe" >> %SCRIPT%
echo oLink.WorkingDirectory = "%~dp0" >> %SCRIPT%
echo oLink.Save >> %SCRIPT%
cscript /nologo %SCRIPT%
del %SCRIPT%
echo.
echo Atalho criado na Area de Trabalho!
pause
