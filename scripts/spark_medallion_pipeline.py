#!/usr/bin/env python3
"""
Spark Medallion Architecture Pipeline
Demonstrates 3-Tier Layered Data Processing on Hadoop / HDFS using PySpark:
- Bronze: Raw interaction logs and ingestion files (/music/bronze/)
- Silver: Validated, cleaned, schema-typed Parquet dataset (/music/silver/)
- Gold: Aggregated user listening profiles and item feature tables (/music/gold/)
"""
from __future__ import annotations

import logging
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SparkMedallionPipeline")

try:
    from pyspark.sql import SparkSession
    from pyspark.sql.functions import col, count, desc, sum as spark_sum
    from pyspark.sql.types import IntegerType, StringType, StructField, StructType
except ImportError:
    logger.error("PySpark is required to run this script. Ensure Spark is installed and SPARK_HOME is set.")
    sys.exit(1)


def build_spark_session(app_name: str = "MusicRecommendationMedallionPipeline") -> SparkSession:
    return (
        SparkSession.builder.appName(app_name)
        .config("spark.sql.parquet.compression.codec", "snappy")
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )


def run_pipeline(
    bronze_input: str = "hdfs:///music/input/train_triplets_1m.txt",
    silver_output: str = "hdfs:///music/silver/interactions.parquet",
    gold_user_output: str = "hdfs:///music/gold/user_profiles.parquet",
    gold_item_output: str = "hdfs:///music/gold/item_features.parquet",
):
    start_time = time.time()
    spark = build_spark_session()
    logger.info("Spark Session Initialized (Spark Version: %s)", spark.version)

    schema = StructType([
        StructField("user_id", StringType(), False),
        StructField("song_id", StringType(), False),
        StructField("play_count", IntegerType(), False),
    ])

    # ==========================================
    # 1. BRONZE LAYER: Raw Data Ingestion
    # ==========================================
    logger.info(">>> [BRONZE LAYER] Ingesting raw interactions from: %s", bronze_input)
    raw_df = (
        spark.read.option("delimiter", "\t")
        .schema(schema)
        .csv(bronze_input)
    )
    raw_count = raw_df.count()
    logger.info("[BRONZE LAYER] Ingested %d raw records", raw_count)

    # ==========================================
    # 2. SILVER LAYER: Data Cleaning & Parquet
    # ==========================================
    logger.info(">>> [SILVER LAYER] Cleaning and validating dataset...")
    clean_df = (
        raw_df.filter(
            (col("user_id").isNotNull())
            & (col("song_id").isNotNull())
            & (col("play_count") > 0)
        )
        .dropDuplicates(["user_id", "song_id"])
    )
    silver_count = clean_df.count()
    logger.info("[SILVER LAYER] Valid records after deduplication: %d", silver_count)

    logger.info("[SILVER LAYER] Writing Snappy Parquet to: %s", silver_output)
    clean_df.write.mode("overwrite").parquet(silver_output)

    # ==========================================
    # 3. GOLD LAYER: User Profiles & Item Features
    # ==========================================
    logger.info(">>> [GOLD LAYER] Computing aggregated User Profiles...")
    user_profiles_df = (
        clean_df.groupBy("user_id")
        .agg(
            count("song_id").alias("total_unique_songs"),
            spark_sum("play_count").alias("total_plays"),
        )
        .orderBy(desc("total_plays"))
    )
    logger.info("[GOLD LAYER] Writing User Profiles to: %s", gold_user_output)
    user_profiles_df.write.mode("overwrite").parquet(gold_user_output)

    logger.info(">>> [GOLD LAYER] Computing aggregated Item Popularity Features...")
    item_features_df = (
        clean_df.groupBy("song_id")
        .agg(
            count("user_id").alias("unique_listeners"),
            spark_sum("play_count").alias("total_item_plays"),
        )
        .orderBy(desc("total_item_plays"))
    )
    logger.info("[GOLD LAYER] Writing Item Features to: %s", gold_item_output)
    item_features_df.write.mode("overwrite").parquet(gold_item_output)

    elapsed = round(time.time() - start_time, 2)
    logger.info(">>> [SUCCESS] Medallion Pipeline completed in %.2f seconds", elapsed)
    spark.stop()


if __name__ == "__main__":
    run_pipeline()
