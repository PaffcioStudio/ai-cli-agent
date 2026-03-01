from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="{{PROJECT_NAME}}",
    description="{{DESCRIPTION}}",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Hello from {{PROJECT_NAME}}!"}


@app.get("/health")
async def health():
    return {"status": "ok"}
