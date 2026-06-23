from fastapi import FastAPI

app = FastAPI(
    title="Expense Splitter API",
    version="1.0.0"
)


@app.get("/")
def root():
    return {
        "message": "Expense Splitter API Running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }