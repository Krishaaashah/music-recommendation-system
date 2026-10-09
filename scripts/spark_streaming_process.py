"""Process real JSON event files with Spark Structured Streaming.

The rate source remains available as an explicit test mode. The default source is
the event directory written by ``scripts/event_producer.py``.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, count, current_timestamp, lit, sum as spark_sum, to_timestamp
from pyspark.sql.types import IntegerType, StringType, StructField, StructType


EVENT_SCHEMA = StructType(
    [
        StructField("event_id", StringType(), False),
        StructField("user_id", StringType(), False),
        StructField("song_id", StringType(), False),
        StructField("event_type", StringType(), False),
        StructField("duration_seconds", IntegerType(), False),
        StructField("timestamp", StringType(), False),
    ]
)
VALID_EVENT_TYPES = ("play", "skip", "like", "replay")


def build_stream(
    spark: SparkSession,
    input_dir: str,
    source: str,
    rows_per_second: int,
    rate_user_id: str,
    rate_song_id: str,
) -> DataFrame:
    if source == "rate":
        from pyspark.sql.functions import expr

        return (
            spark.readStream.format("rate").option("rowsPerSecond", rows_per_second).load()
            .select(
                expr("concat('test-', cast(value as string))").alias("event_id"),
                lit(rate_user_id).alias("user_id"),
                lit(rate_song_id).alias("song_id"),
                expr("'play'").alias("event_type"),
                expr("180").cast("int").alias("duration_seconds"),
                col("timestamp").cast("string").alias("timestamp"),
            )
        )
    return spark.readStream.schema(EVENT_SCHEMA).json(input_dir)


def clean_events(raw_stream: DataFrame) -> DataFrame:
    return (
        raw_stream.withColumn("event_time", to_timestamp(col("timestamp")))
        .filter(
            col("event_id").isNotNull()
            & col("user_id").isNotNull()
            & col("song_id").isNotNull()
            & col("event_time").isNotNull()
            & col("duration_seconds").between(0, 86400)
            & col("event_type").isin(*VALID_EVENT_TYPES)
        )
    )


def append_parquet(batch_df: DataFrame, output_path: str) -> None:
    if not batch_df.isEmpty():
        batch_df.write.mode("append").parquet(output_path)


def write_clean_batch(batch_df: DataFrame, batch_id: int, silver_path: str, gold_path: str, mongo_uri: str) -> None:
    if batch_df.isEmpty():
        return

    append_parquet(batch_df, silver_path)
    aggregates = batch_df.groupBy("user_id", "song_id").agg(
        count("event_id").alias("event_count"),
        spark_sum("duration_seconds").alias("total_duration_seconds"),
        current_timestamp().alias("updated_at"),
    )
    append_parquet(aggregates, gold_path)

    if mongo_uri:
        from pymongo import MongoClient

        documents = [row.asDict(recursive=True) for row in batch_df.collect()]
        with MongoClient(mongo_uri, serverSelectionTimeoutMS=2000) as client:
            client[os.getenv("MONGO_DB_NAME", "music_recommendation")].events.insert_many(documents, ordered=False)


def run_streaming_job(
    input_dir: str = "streaming/input",
    bronze_path: str = "hdfs:///music/bronze/events",
    silver_path: str = "hdfs:///music/silver/events",
    gold_path: str = "hdfs:///music/gold/event_aggregates",
    checkpoint_path: str = "hdfs:///music/checkpoints/events",
    mongo_uri: str = "",
    source: str = "json",
    rows_per_second: int = 5,
    rate_user_id: str = "1",
    rate_song_id: str = "103",
    duration_seconds: int = 0,
) -> None:
    spark = SparkSession.builder.appName("MusicStructuredEventProcessor").getOrCreate()
    raw_stream = build_stream(spark, input_dir, source, rows_per_second, rate_user_id, rate_song_id)

    bronze_query = (
        raw_stream.writeStream.foreachBatch(lambda df, _: append_parquet(df, bronze_path))
        .option("checkpointLocation", f"{checkpoint_path}/bronze")
        .start()
    )
    clean_query = (
        clean_events(raw_stream)
        .writeStream.foreachBatch(lambda df, batch_id: write_clean_batch(df, batch_id, silver_path, gold_path, mongo_uri))
        .option("checkpointLocation", f"{checkpoint_path}/clean")
        .start()
    )

    try:
        if duration_seconds > 0:
            clean_query.awaitTermination(timeout=duration_seconds)
        else:
            clean_query.awaitTermination()
    finally:
        bronze_query.stop()
        clean_query.stop()
        spark.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the real event-file Spark streaming pipeline.")
    parser.add_argument("--input-dir", default="streaming/input")
    parser.add_argument("--bronze", default="hdfs:///music/bronze/events")
    parser.add_argument("--silver", default="hdfs:///music/silver/events")
    parser.add_argument("--gold", default="hdfs:///music/gold/event_aggregates")
    parser.add_argument("--checkpoint", default="hdfs:///music/checkpoints/events")
    parser.add_argument("--mongo-uri", default=os.getenv("MONGO_URI", ""))
    parser.add_argument("--source", choices=("json", "rate"), default="json")
    parser.add_argument("--rate", type=int, default=5)
    parser.add_argument("--rate-user-id", default="1")
    parser.add_argument("--rate-song-id", default="103")
    parser.add_argument("--duration", type=int, default=0, help="Seconds; 0 means run continuously")
    args = parser.parse_args()
    run_streaming_job(
        input_dir=args.input_dir,
        bronze_path=args.bronze,
        silver_path=args.silver,
        gold_path=args.gold,
        checkpoint_path=args.checkpoint,
        mongo_uri=args.mongo_uri,
        source=args.source,
        rows_per_second=args.rate,
        rate_user_id=args.rate_user_id,
        rate_song_id=args.rate_song_id,
        duration_seconds=args.duration,
    )
