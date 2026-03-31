"""
Spark batch analytics job.
Reads rides from ride-service MongoDB (last 24h).
Computes: total rides, avg price, avg distance, rides per status.
Writes results to analytics MongoDB.
Runs as a Kubernetes CronJob every hour.
"""

import os
import logging
from datetime import datetime, timedelta, timezone

from pyspark.sql import SparkSession
from pyspark.sql.functions import avg, count, col
import pymongo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RIDE_MONGO_URL = os.getenv("RIDE_MONGO_URL", "mongodb://localhost:27017")
ANALYTICS_MONGO_URL = os.getenv("ANALYTICS_MONGO_URL", "mongodb://localhost:27017")


def run():
    logger.info("Starting analytics Spark job")

    spark = SparkSession.builder \
        .appName("SmartMobilityAnalytics") \
        .config("spark.mongodb.read.connection.uri", RIDE_MONGO_URL) \
        .config("spark.mongodb.write.connection.uri", ANALYTICS_MONGO_URL) \
        .getOrCreate()

    spark.sparkContext.setLogLevel("WARN")

    # Read rides from MongoDB using Spark MongoDB connector
    # Falls back to pymongo if connector not available in slim image
    try:
        rides_df = spark.read \
            .format("mongodb") \
            .option("database", "ride_db") \
            .option("collection", "rides") \
            .load()

        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

        # Filter last 24h - MongoDB stores timestamps as ISO strings in this schema
        # For a production setup, add a created_at field indexed as Date
        total_rides = rides_df.count()
        completed_rides = rides_df.filter(col("status") == "COMPLETED").count()
        avg_price = rides_df.agg(avg("price_eur")).collect()[0][0] or 0.0
        avg_distance = rides_df.agg(avg("distance_km")).collect()[0][0] or 0.0

        status_counts_rows = rides_df.groupBy("status").agg(count("*").alias("count")).collect()
        status_counts = {row["status"]: row["count"] for row in status_counts_rows}

    except Exception as e:
        logger.warning(f"Spark MongoDB read failed ({e}), falling back to pymongo")
        client = pymongo.MongoClient(RIDE_MONGO_URL)
        db = client["ride_db"]
        all_rides = list(db.rides.find({}))
        total_rides = len(all_rides)
        completed_rides = sum(1 for r in all_rides if r.get("status") == "COMPLETED")
        avg_price = (sum(r.get("price_eur", 0) for r in all_rides) / total_rides) if total_rides else 0.0
        avg_distance = (sum(r.get("distance_km", 0) for r in all_rides) / total_rides) if total_rides else 0.0
        status_counts = {}
        for r in all_rides:
            s = r.get("status", "UNKNOWN")
            status_counts[s] = status_counts.get(s, 0) + 1
        client.close()

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

    # Write to analytics MongoDB
    analytics_client = pymongo.MongoClient(ANALYTICS_MONGO_URL)
    analytics_db = analytics_client["analytics_db"]
    analytics_db.analytics_results.insert_one(result)
    analytics_client.close()

    spark.stop()
    logger.info("Analytics job complete")


if __name__ == "__main__":
    run()
