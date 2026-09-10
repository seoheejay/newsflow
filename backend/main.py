from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="NewsFlow API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/settings")
def get_settings():
    return {
        "mail_subject": "",
        "mail_to": "",
        "max_per_source": 10,
        "keywords": [],
    }


@app.get("/feed-sources")
def get_feed_sources(page: int = 1, items_per_page: int = 20):
    return {
        "total_count": 0,
        "page": page,
        "items_per_page": items_per_page,
        "items": [],
    }


@app.get("/articles")
def get_articles(
    page: int = 1,
    items_per_page: int = 20,
    keyword: str | None = None,
    site: str | None = None,
):
    return {
        "total_count": 0,
        "page": page,
        "items_per_page": items_per_page,
        "items": [],
    }


@app.post("/collect", status_code=202)
def collect():
    return {"execution_id": "dummy", "status": "queued"}


@app.get("/executions/{execution_id}")
def get_execution(execution_id: str):
    return {
        "id": execution_id,
        "status": "success",
        "started_at": None,
        "finished_at": None,
        "collected_count": 0,
        "new_count": 0,
        "error": None,
    }