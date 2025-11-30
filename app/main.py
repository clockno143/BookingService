# main.py
import asyncio
from fastapi import FastAPI
from app.routes import router
from app.workers import worker

app = FastAPI(title="Event Booking API")
app.include_router(router)

@app.on_event("startup")
async def start_worker():
    asyncio.create_task(worker())  # run worker in background

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
