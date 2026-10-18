@echo off
rem Builds dist\HOI4CountryEditor.exe, dist\HOI4FocusEditor.exe and dist\HOI4TechEditor.exe (needs Python from python.org, with tcl/tk ticked)
python -m pip install --upgrade pyinstaller pillow
python -m PyInstaller --onefile --windowed --name HOI4CountryEditor hoi4_country_editor.py
python -m PyInstaller --onefile --windowed --name HOI4FocusEditor hoi4_focus_editor.py
python -m PyInstaller --onefile --windowed --name HOI4TechEditor hoi4_tech_editor.py
pause
