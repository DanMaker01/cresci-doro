@echo off
setlocal
rem ==========================================================
rem  Gera dist\crescidoro.exe  (duplo clique para executar)
rem  Os dados em dist\ (historico/config .json) sao mantidos.
rem ==========================================================
cd /d "%~dp0"

rem --- localiza o Python (py launcher ou python no PATH) ---
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
    echo [ERRO] Python nao encontrado. Instale em https://www.python.org/downloads/
    goto :fim_erro
)
echo Usando: %PY%

rem --- fecha o app se estiver aberto (senao o .exe fica travado) ---
tasklist /fi "imagename eq crescidoro.exe" | find /i "crescidoro.exe" >nul
if not errorlevel 1 (
    echo Fechando crescidoro.exe em execucao...
    taskkill /im crescidoro.exe /f >nul 2>nul
    timeout /t 1 /nobreak >nul
)

echo.
echo [1/2] Instalando dependencias...
%PY% -m pip install --quiet --disable-pip-version-check -r requirements.txt pyinstaller
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias.
    goto :fim_erro
)

echo [2/2] Gerando executavel...
%PY% -m PyInstaller --noconfirm --clean --log-level WARN main.spec
if errorlevel 1 (
    echo [ERRO] Falha no PyInstaller.
    goto :fim_erro
)

if not exist "dist\crescidoro.exe" (
    echo [ERRO] dist\crescidoro.exe nao foi gerado.
    goto :fim_erro
)

echo.
echo ==========================================================
echo  Pronto: %cd%\dist\crescidoro.exe
echo ==========================================================
choice /c sn /n /m "Abrir agora? [S/N] "
if errorlevel 2 goto :fim
start "" "dist\crescidoro.exe"
goto :fim

:fim_erro
echo.
pause
exit /b 1

:fim
endlocal
exit /b 0
