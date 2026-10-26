# Architecture

```text
Music Data
    |
    v
HDFS
    |
    v
Apache Spark Batch Processing
    |
    v
Apache Mahout
    |
    v
Recommendation Output
    |
    v
FastAPI Recommendation Service
    |
    v
Frontend UI
    |
    v
User
```

Streaming path:

```text
New Events
    |
    v
Spark Structured Streaming
    |
    v
Near-real-time processing
```

The streaming path is documented separately because the current project does not continuously retrain Mahout in real time.

## Current local topology

```text
HDFS NameNode:       h-primary
HDFS DataNodes:      h-worker1, h-worker2, h-worker3, h-worker4, h-worker5
HDFS replication:    3 copies per block
YARN:                1 ResourceManager + 5 NodeManagers
Spark:               1 standalone master + 5 workers
```

## Spark execution

Spark divides input data into partitions. The driver creates a Spark application, the master schedules work, and executors on the workers execute tasks in parallel. The batch job reads tab-separated user-song-play records from HDFS, cleans them, and writes Snappy-compressed Parquet. The medallion job additionally creates user-profile and item-feature aggregates. The Structured Streaming job continuously processes JSON event files with checkpoints and writes event analytics to Bronze, Silver and Gold paths.

The current Docker topology runs Spark in standalone mode. YARN services are present and inspectable, but a Spark job must be explicitly submitted with a YARN master to use YARN scheduling. This distinction should be stated during the demonstration.
