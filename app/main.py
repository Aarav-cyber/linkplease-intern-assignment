from fastapi import FastAPI

app = FastAPI(title="LinkPlease Assignment")


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "linkplease"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }