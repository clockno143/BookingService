# main.py
import asyncio
import os
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.routes import router
from app.workers import worker

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    print("App starting up...")
    # Start worker in background
    asyncio.create_task(worker())
    yield
    # Shutdown logic (optional)
    print("App shutting down...")

app = FastAPI(title="Event Booking API", lifespan=lifespan)

# Include your routes
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
