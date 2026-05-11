@echo off
python -m pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
python main.py
