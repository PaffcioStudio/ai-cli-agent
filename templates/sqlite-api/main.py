"""
{{PROJECT_NAME}} — {{DESCRIPTION}}
Autor: {{AUTHOR}}, {{YEAR}}
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
from app.routes.items import router as items_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="{{PROJECT_NAME}}", description="{{DESCRIPTION}}", version="0.1.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(items_router, prefix="/api")

@app.get("/")
def root():
    return {"project": "{{PROJECT_NAME}}", "version": "0.1.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
