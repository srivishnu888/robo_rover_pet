@echo off
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconsole --onefile --name RoboRoverPet run.py
pause
