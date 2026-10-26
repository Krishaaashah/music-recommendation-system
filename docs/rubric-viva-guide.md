# Rubric-by-Rubric Viva Guide

Use this as the explanation for the final project. Say what the system actually does, then show the relevant file, command or screen. Do not claim that a Docker declaration is the same as a live cluster measurement.

## 1. Problem statement and objectives

**What to say:**

The project solves implicit-feedback music recommendation. The dataset does not contain star ratings; it contains listening behaviour, such as how many times a user played a song. The goal is to build a scalable pipeline that stores large interaction data, processes it in batch and near-real time, generates personalised recommendations, serves them through an API, and exposes measurable evaluation results.

**Objectives implemented:**

- Store interaction data in a distributed HDFS design.
- Keep three copies of each HDFS block through replication factor 3.
- Process historical data using Spark batch jobs.
- Process new listening events using Spark Structured Streaming.
- Generate item-based collaborative recommendations using Apache Mahout.
- Improve serving results with metadata, co-occurrence and popularity signals.
- Expose recommendations and operational data through FastAPI.
- Provide MongoDB persistence for application-facing event/history data.
- Evaluate Precision, Recall, MRR, MAP, NDCG, hit rate and catalog coverage.

## 2. Dataset and data engineering

**Dataset:** Last.fm 1K-derived listening data prepared into application files. The repository reports approximately 4.62 million aggregated interaction rows, 1.5 million catalog tracks and 874 recommendation profiles.

**Files:**

- `train_triplets.txt`: user, song and play-count interactions.
- `song_mapping.csv`: original song key to numeric item ID.
- `user_mapping.csv`: original user key to numeric user ID.
- `song_metadata.csv`: track and artist information used by the UI and content similarity.
- `mahout_input.csv`: numeric user-item-play-count format for Mahout.

**How preparation works:** `scripts/prepare_lastfm_dataset.py` streams the source file and uses SQLite-backed aggregation instead of loading the full raw dataset into memory. This is important because the raw event file is too large for a naive in-memory approach.

**Viva answer:** The project separates raw-style interactions, mappings, metadata and model input so that the IDs used by Mahout can be joined back to readable song names at serving time.

## 3. Big Data characteristics

**Volume:** millions of interactions and more than a million catalog records.

**Velocity:** new events arrive continuously through the API/event producer and are processed by Structured Streaming.

**Variety:** tab-separated historical data, CSV mapping/metadata files, JSON live events, Parquet analytical outputs and MongoDB documents.

**Scalability:** HDFS DataNodes, Spark workers and partitioned processing provide the distributed design. The current Docker deployment is a local logical-cluster simulation because all containers share one host.

## 4. HDFS storage and replication

**Current topology:** one NameNode (`h-primary`) and five DataNodes (`h-worker1` through `h-worker5`). The NameNode stores filesystem metadata; DataNodes store HDFS blocks.

**Replication:** `HDFS_CONF_dfs_replication=3` is configured on the NameNode and each DataNode. Replication factor 3 means HDFS aims to keep three copies of every block on different DataNodes. Five DataNodes provide more placement capacity than the minimum three.

**What to show:** NameNode UI at port 9870 and:

```powershell
docker exec h-primary hdfs dfsadmin -report
```

**Important limitation:** five containers are not five physical machines. For genuine host-failure tolerance, place DataNodes on separate VMs or cloud instances with separate disks and networking.

## 5. YARN resource management

**Current topology:** one ResourceManager (`h-primary-yarn`) and five NodeManagers (`h-worker1-yarn` through `h-worker5-yarn`).

**Role:** ResourceManager coordinates cluster resources. NodeManagers run and monitor work on worker nodes. YARN is the Hadoop resource-management layer, not the recommendation algorithm.

**What to show:** YARN UI at port 8088 and:

```powershell
docker exec h-primary-yarn yarn node -list
```

## 6. Spark batch processing

**Current topology:** one standalone Spark master and five Spark workers. Workers execute tasks against partitions of the input.

**Batch code:** `scripts/spark_batch_process.py` reads tab-separated records from HDFS, applies a typed schema, removes null records and writes Snappy-compressed Parquet.

**Medallion code:** `scripts/spark_medallion_pipeline.py` creates:

- Bronze: raw interaction ingestion.
- Silver: validation, positive play-count filtering and duplicate removal.
- Gold: user profile aggregates and item popularity features.

**Spark concepts to explain:** transformations are lazy; actions such as `count()` and Parquet writes trigger execution; `groupBy` causes a shuffle so records can be aggregated by user or song; Parquet is columnar and compressed for analytics.

**Exact distinction:** Spark currently runs in standalone mode in Compose. YARN services are available, but Spark is only YARN-managed when submitted with a YARN master. Do not say that every current Spark job is already running through YARN.

## 7. Spark Structured Streaming

`scripts/spark_streaming_process.py` watches JSON event files. It applies an explicit event schema, validates event type and duration, writes Bronze events, writes cleaned Silver events, aggregates Gold event statistics and uses checkpoint paths for restart recovery.

FastAPI or `scripts/event_producer.py` creates the events. MongoDB stores serving-oriented documents, while Spark/HDFS store distributed analytical outputs. This is near-real-time event processing; it does not retrain Mahout after every click.

## 8. Recommendation algorithm

**Mahout:** Apache Mahout produces item-based collaborative-filtering recommendations using `SIMILARITY_LOGLIKELIHOOD`. This is suitable for implicit play-count behaviour. The model finds relationships between items based on users who listened to them together.

**Serving layer:** `backend/recommendation_service.py` reads recommendation output, removes already-consumed items where possible, maps IDs to track metadata and applies fallback strategies.

**Hybrid ranking:** the project combines collaborative score, metadata or behavioural co-occurrence and popularity. The documented default is:

```text
final_score = 0.7 * collaborative_score
            + 0.2 * content_or_cooccurrence_score
            + 0.1 * popularity_score
```

**Cold start:** new or unknown users receive popularity-based results instead of an empty response.

## 9. MongoDB and SQL/NoSQL choice

MongoDB stores flexible event/history documents and supports indexed application retrieval. It is useful for changing JSON-shaped event data and quick point lookups.

SQLite is used during dataset preparation as a local aggregation helper, not as the production serving database. The project does not need a relational database for the recommendation-serving path because the main interaction and event data are document/analytic oriented.

## 10. FastAPI and API design

FastAPI is the serving boundary between the model/data layer and the frontend. Important endpoints include:

- `/health`: service and dataset status.
- `/api/info`: architecture and strategy information.
- `/recommend/{user_id}`: personalised Top-N recommendations.
- `/similar/{song_id}`: similar-track results.
- `/songs/{song_id}`: catalog metadata.
- `/user/{user_id}/history`: listening history.
- `/events`: validated event ingestion.
- `/live/events` and `/live/stats`: activity feed and counters.
- `/evaluation/metrics`: offline evaluation.

The API returns readable track title, artist, numeric item ID, score, rank, reason, strategy and execution time. The automatic `/docs` page is useful evidence for the implementation.

## 11. Frontend and user workflow

The interface supports listener selection, strategy selection, recommendation count, similar-song lookup, listening history, live activity, architecture and evaluation views. It includes loading, success, empty, error and API-status states. The loading wheel appears while recommendation or similarity requests are running.

Demonstrate this sequence:

1. Open the dashboard.
2. Select a prepared user.
3. Generate recommendations and point out title, artist, ID, score and reason.
4. Open Similar Songs and query an item.
5. Open Live Activity and start the simulator.
6. Open Evaluation and show the configured metrics.

## 12. Evaluation and interpretation

The project uses a deterministic train-only holdout rather than evaluating on the same interactions used for candidate generation. Metrics include Precision@K, Recall@K, MRR@K, MAP@K, NDCG@K, hit rate and catalog coverage.

- **Precision@K:** fraction of the first K recommendations that are relevant.
- **Recall@K:** fraction of held-out relevant items retrieved in the first K.
- **MRR@K:** reciprocal rank of the first relevant result, averaged across users.
- **MAP@K:** rewards multiple relevant items appearing early.
- **NDCG@K:** discounts relevant items that appear lower in the list.
- **Hit rate:** percentage of users with at least one hit.
- **Coverage:** how much of the catalog is recommended.

Do not promise 80–90% Precision@10. In implicit-feedback recommendation, Precision@10 and MRR are usually much harder than Recall@70 or Recall@100. The repository documents a wider retrieval result separately: Recall@70 around 70.36% and Recall@100 around 80.34%. Those are different operating points and must not be presented as Precision@10.

## 13. Testing and evidence

The repository contains tests for API behavior, recommendation parsing/ranking and MongoDB behavior. Focused checks previously passed for MongoDB service and recommendation service. Full API integration is expensive because it initializes the large local catalog and should be rerun with the dataset/runtime ready.

Infrastructure still needs live evidence:

- `docker compose ps` showing expected services.
- NameNode UI or `hdfs dfsadmin -report` showing five DataNodes.
- YARN UI or `yarn node -list` showing five NodeManagers.
- Spark master UI showing five workers.
- API `/health`, `/docs`, recommendation response and evaluation response.
- Live event feed with changing counters.

## 14. Scalability and deployment answer

The design scales horizontally by adding DataNodes for storage, Spark workers for parallel computation and API replicas behind a load balancer. HDFS replication protects blocks from a DataNode failure. Parquet reduces analytic I/O. Checkpoints support streaming recovery.

The current local version demonstrates logical scale-out, not production high availability. Before cloud deployment, add authentication and TLS, protect Hadoop/Spark admin interfaces, configure MongoDB authentication, pin images and Python dependencies, run containers as non-root, add resource limits, add live dependency probes and distribute nodes across separate machines.

## 15. Final honest status

**Implemented in code:** data preparation, recommendation logic, APIs, frontend states, Spark batch/streaming scripts, Mahout integration, MongoDB integration, Docker topology and evaluation logic.

**Configured but requiring runtime proof:** five live DataNodes, replication placement, five NodeManagers, five Spark workers, HDFS Parquet outputs and MongoDB-connected operation.

**Remaining for a production-quality system:** separate physical/virtual hosts, security controls, authenticated services, stronger observability, automated deployment, backups and full live evidence.

## Closing answer

This is a complete academic Big Data pipeline: HDFS provides replicated storage, Spark provides distributed batch and streaming computation, Mahout provides offline collaborative filtering, MongoDB supports flexible event persistence, FastAPI provides model serving, and the frontend demonstrates the user workflow. The main distinction is that the local Docker cluster is a reproducible simulation of a distributed deployment; production fault tolerance would require separate machines and security hardening.
