@echo off
rem Builds dist\HOI4CountryEditor.exe (needs Python from python.org, with tcl/tk ticked)
python -m pip install --upgrade pyinstaller pillow
python -m PyInstaller --onefile --windowed --name HOI4CountryEditor hoi4_country_editor.py
pause
