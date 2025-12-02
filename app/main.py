# main.py
import asyncio
from fastapi import FastAPI
from app.routes import router
from app.workers import worker
import os

app = FastAPI(title="Event Booking API")
app.include_router(router)

@app.on_event("startup")
async def start_worker():
    asyncio.create_task(worker())  # run worker in background

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

