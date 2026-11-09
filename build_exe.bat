@echo off
chcp 65001 >nul
REM Сборка SimsDict (папка dist\SimsDict, запуск — dist\SimsDict\SimsDict.exe).
REM Режим "папка" стартует заметно быстрее, чем один большой exe (не распаковывается при каждом запуске).
cd /d "%~dp0"
py -3 -c "import sys; assert sys.version_info >= (3, 10), sys.version" || (echo Нужен Python 3.10+ с python.org & goto :err)
py -3 -m pip install --upgrade -r requirements.txt "pyinstaller>=6.22" || goto :err
REM Shaders: gui\qml\SimsDict\shaders\*.qsb are prebuilt (pyside6-qsb, from PySide6-Addons) and committed.
py -3 -m PyInstaller --noconfirm --clean SimsDict.spec || goto :err
echo.
echo Готово: dist\SimsDict\SimsDict.exe  (переносить можно всю папку dist\SimsDict)
pause
exit /b 0
:err
echo Ошибка сборки — пришлите текст выше.
pause
exit /b 1
