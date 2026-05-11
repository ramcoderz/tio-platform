import uvicorn
from backend.config.settings import get_settings

settings = get_settings()

if __name__ == "__main__":
    print(f"Starting {settings.app_name} on {settings.host}:{settings.port}...")
    uvicorn.run(
        "backend.main:app", 
        host=settings.host, 
        port=settings.port, 
        reload=True,
        reload_dirs=["backend"], # Only watch the backend directory
        reload_excludes=["*.db", "data/*", "__pycache__/*", "*.log"]
    )
