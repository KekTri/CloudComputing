import os
import logging
from fastapi import FastAPI
import pymongo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ANALYTICS_MONGO_URL = os.getenv("ANALYTICS_MONGO_URL", "mongodb://localhost:27017")

app = FastAPI(title="Analytics API", docs_url="/analytics/docs", openapi_url="/analytics/openapi.json")


@app.get("/analytics/results")
def get_results():
    client = pymongo.MongoClient(ANALYTICS_MONGO_URL)
    db = client["analytics_db"]
    results = list(db.analytics_results.find({}, {"_id": 0}).sort("computed_at", -1).limit(10))
    client.close()
    return results


@app.get("/analytics/latest")
def get_latest():
    client = pymongo.MongoClient(ANALYTICS_MONGO_URL)
    db = client["analytics_db"]
    result = db.analytics_results.find_one({}, {"_id": 0}, sort=[("computed_at", -1)])
    client.close()
    return result or {}


@app.get("/health")
def health():
    return {"status": "ok"}
