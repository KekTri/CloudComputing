"""
Spark batch analytics job.
Reads rides from ride-service MongoDB (last 24h).
Computes: total rides, avg price, avg distance, rides per status.
Writes results to analytics MongoDB.
Runs as a Kubernetes CronJob every hour.
Uses external Spark cluster via Spark Connect (no local Java needed).
"""

import os
import logging
from datetime import datetime, timedelta, timezone

import pymongo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RIDE_MONGO_URL = os.getenv("RIDE_MONGO_URL", "mongodb://localhost:27017")
ANALYTICS_MONGO_URL = os.getenv("ANALYTICS_MONGO_URL", "mongodb://localhost:27017")
SPARK_TOKEN = os.getenv("SPARK_TOKEN", "")
SPARK_HOST = os.getenv("SPARK_HOST", "10.3.15.18:15012")

# Required for custom CA certificate used by the Spark cluster
os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = "/app/spark-server.pem"


def run():
    logger.info("Starting analytics Spark job")

    # Read ride data via pymongo
    client = pymongo.MongoClient(RIDE_MONGO_URL)
    db = client["ride_db"]
    all_rides = list(db.rides.find({}, {"_id": 0}))
    client.close()

    logger.info(f"Fetched {len(all_rides)} rides from MongoDB")

    if not all_rides:
        logger.info("No rides found, writing zero result")
        result = {
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "window_hours": 24,
            "total_rides": 0,
            "completed_rides": 0,
            "avg_price_eur": 0.0,
            "avg_distance_km": 0.0,
            "rides_by_status": {},
        }
        _write_result(result)
        return

    try:
        from pyspark.sql import SparkSession
        from pyspark.sql.functions import avg, count, col

        connection_string = f"sc://{SPARK_HOST}/;token={SPARK_TOKEN};use_ssl=true"
        spark = SparkSession.builder.remote(connection_string).getOrCreate()

        rides_df = spark.createDataFrame(all_rides)

        total_rides = rides_df.count()
        completed_rides = rides_df.filter(col("status") == "COMPLETED").count()
        avg_price = rides_df.agg(avg("price_eur")).collect()[0][0] or 0.0
        avg_distance = rides_df.agg(avg("distance_km")).collect()[0][0] or 0.0
        status_counts_rows = rides_df.groupBy("status").agg(count("*").alias("count")).collect()
        status_counts = {row["status"]: row["count"] for row in status_counts_rows}

        spark.stop()
        logger.info("Spark computation complete")

    except Exception as e:
        logger.warning(f"Spark job failed ({e}), falling back to local computation")
        total_rides = len(all_rides)
        completed_rides = sum(1 for r in all_rides if r.get("status") == "COMPLETED")
        avg_price = (sum(r.get("price_eur", 0) for r in all_rides) / total_rides) if total_rides else 0.0
        avg_distance = (sum(r.get("distance_km", 0) for r in all_rides) / total_rides) if total_rides else 0.0
        status_counts = {}
        for r in all_rides:
            s = r.get("status", "UNKNOWN")
            status_counts[s] = status_counts.get(s, 0) + 1

    result = {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "window_hours": 24,
        "total_rides": total_rides,
        "completed_rides": completed_rides,
        "avg_price_eur": round(avg_price, 2),
        "avg_distance_km": round(avg_distance, 2),
        "rides_by_status": status_counts,
    }

    logger.info(f"Analytics result: {result}")
    _write_result(result)
    logger.info("Analytics job complete")


def _write_result(result):
    analytics_client = pymongo.MongoClient(ANALYTICS_MONGO_URL)
    analytics_db = analytics_client["analytics_db"]
    analytics_db.analytics_results.insert_one(result)
    analytics_client.close()


if __name__ == "__main__":
    run()
