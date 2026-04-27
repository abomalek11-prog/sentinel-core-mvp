from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/api/ping")
async def ping():
    return {"status": "pong", "message": "Backend is reachable!"}

@app.get("/api/health")
async def health():
    return {"status": "ok", "message": "Backend is healthy!"}
