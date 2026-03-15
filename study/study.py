from fastapi import FastAPI
import uvicorn
import logging

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Study",
    description="Study",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "study",
            "description": "Study"
        }
    ]
)

FUCKYOU = {
    "fuckyou": "fuckyou",
    "fuckyou": "fuckyou",
    "fuckyou": "fuckyou"
}

@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

@app.get("/fuckyou")
def read_fuckyou():
    result = {}
    for type, value in FUCKYOU.items():
        result[type] = value
    return res
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5050)

