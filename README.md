# Terminal 1
cd D:\AI\JEV\laya-server
.\start.ps1

# Terminal 2
cd D:\AI\JEV\PoC
.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --port 8010
