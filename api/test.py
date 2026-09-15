from fastapi import FastAPI

app = FastAPI()

@app.get("/api/test")
@app.get("/test")
def test():
    return {"status": "ok"}
