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
