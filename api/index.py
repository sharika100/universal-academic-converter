from fastapi import FastAPI

app = FastAPI()

status = {}

try:
    import pylatexenc
    status["pylatexenc"] = "OK"
except Exception as e:
    status["pylatexenc"] = f"FAIL: {e}"

try:
    import docx
    status["docx"] = "OK"
except Exception as e:
    status["docx"] = f"FAIL: {e}"

try:
    import lxml
    status["lxml"] = "OK"
except Exception as e:
    status["lxml"] = f"FAIL: {e}"

try:
    import PIL
    status["PIL"] = "OK"
except Exception as e:
    status["PIL"] = f"FAIL: {e}"

try:
    import reportlab
    status["reportlab"] = "OK"
except Exception as e:
    status["reportlab"] = f"FAIL: {e}"

@app.get("/api/health")
@app.get("/health")
def health():
    return {
        "status": "ok",
        "libraries": status
    }
