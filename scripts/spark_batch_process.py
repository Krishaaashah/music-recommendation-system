"""
Spark 3.5.9 Batch Processing Job for Music Recommendation System.
Reads 1,000,000 user-song-play_count interactions from HDFS,
cleans the dataset, and writes optimized Parquet partitions to HDFS.
"""

from __future__ import annotations

import argparse
import sys
from pyspark.sql import SparkSession
from pyspark.sql.types import IntegerType, StringType, StructField, StructType


def run_batch_job(input_path: str, output_path: str) -> int:
    print(f"Starting Spark batch processing: {input_path} -> {output_path}")

    spark = (
        SparkSession.builder
        .appName("MusicDataProcessing-1M")
        .config("spark.sql.parquet.compression.codec", "snappy")
        .getOrCreate()
    )

    schema = StructType([
        StructField("user_id", StringType(), False),
        StructField("song_id", StringType(), False),
        StructField("play_count", IntegerType(), False),
    ])

    df = spark.read.csv(
        input_path,
        sep="\t",
        header=False,
        schema=schema,
    )

    # Drop null values if any
    cleaned_df = df.dropna()

    record_count = cleaned_df.count()
    print(f"Total records processed: {record_count}")

    cleaned_df.write.mode("overwrite").parquet(output_path)
    print(f"Successfully wrote Parquet dataset to: {output_path}")

    spark.stop()
    return record_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Spark batch preprocessing on music dataset.")
    parser.add_argument(
        "--input",
        type=str,
        default="hdfs:///music/input/train_triplets_1m.txt",
        help="Input dataset path in HDFS or local filesystem",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="hdfs:///music/processed",
        help="Output Parquet path in HDFS or local filesystem",
    )
    args = parser.parse_args()

    count = run_batch_job(args.input, args.output)
    print(f"Spark job finished with {count} records.")
