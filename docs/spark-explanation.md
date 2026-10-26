# Spark Explanation for Viva

## One-minute answer

Apache Spark is used as the distributed processing engine. Hadoop HDFS stores the data, and Spark reads that data in partitions so multiple worker processes can clean and aggregate it in parallel. The batch pipeline creates Bronze, Silver and Gold datasets in Parquet. The Structured Streaming pipeline reads new JSON listening events, validates them, maintains checkpoints and writes near-real-time analytics. Mahout uses the prepared historical data for offline collaborative filtering, and FastAPI serves the resulting recommendations.

## What happens during batch processing

1. The Spark driver starts an application.
2. The Spark master schedules work across the five workers.
3. Each worker processes a partition of the HDFS input.
4. Spark applies lazy transformations such as filtering and deduplication.
5. Actions such as `count()` and Parquet writes trigger execution.
6. Shuffle operations move records between workers for `groupBy` and aggregation.
7. The output is written as compressed Parquet files in HDFS.

The medallion pipeline uses:

- **Bronze:** raw interaction ingestion.
- **Silver:** typed, validated and deduplicated interactions.
- **Gold:** user profiles and item popularity features.

## What happens during streaming

FastAPI or the event producer writes a JSON event into the streaming input directory. Spark Structured Streaming treats the directory as an incremental source. It validates the schema, rejects invalid event types or durations, updates aggregates and writes checkpoint files. Checkpoints allow the query to resume from its last processed position after a restart.

MongoDB is used for quick application-facing event retrieval, while Spark and HDFS are used for distributed analytics. This is near-real-time processing; the project does not retrain the Mahout model after every event.

## Hadoop, YARN and Spark relationship

- **HDFS:** distributed storage and replication.
- **YARN:** Hadoop resource manager and scheduler for Hadoop applications.
- **Spark:** distributed computation engine.
- **Mahout:** offline recommendation algorithm execution.
- **FastAPI:** online serving layer.

The Compose file currently runs Spark as a standalone cluster with one master and five workers. YARN is also deployed so its ResourceManager and NodeManagers can be inspected. Spark becomes YARN-managed only when a job is submitted with a YARN master configuration; the presence of YARN containers alone does not automatically make standalone Spark jobs run on YARN.

## Why five DataNodes with replication three?

Replication factor 3 means each HDFS block should have three copies on different DataNodes. Five DataNodes provide more capacity and allow the cluster to continue placing replicas when a node is unavailable. In this local project these are logical containers on one host, so the topology demonstrates distributed configuration but not independent-machine fault tolerance.
