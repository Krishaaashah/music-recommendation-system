# Dataset Documentation

## 1. Overview & Source
This project uses the **Echo Nest Taste Profile Subset**, which is an official component of the **Million Song Dataset (MSD)** project developed in collaboration between Columbia University and The Echo Nest.

- **Primary Source:** Echo Nest Taste Profile Interaction Dataset
- **Format:** Tab-separated triplets (`user_id\tsong_id\tplay_count`)
- **Benchmark Subset:** `dataset/train_triplets_1m.txt` (exactly 1,000,000 user-song listening interaction records)

---

## 2. Data Schema

| Field Name | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `user_id` | `String` (40-char SHA-1) | Anonymized unique listener ID | `b80344d063b5ccb3212f76538f3d9e43d87dca9e` |
| `song_id` | `String` (18-char MSD ID) | Unique Echo Nest track identifier | `SOAKIMP12A58A7E2FE` |
| `play_count` | `Integer` | Frequency of listening events by user | `4` |

---

## 3. Mahout Integer Mappings

Apache Mahout collaborative filtering algorithms (`org.apache.mahout.cf.taste.hadoop.item.RecommenderJob`) require numeric `(Long, Long, Double)` representations. 

The mapping pipeline maps string hashes to integers:
- `dataset/user_mapping.csv`: Maps 40-character user hashes $\to$ `int_user_id` (e.g., User `1`, `2`, `3`...).
- `dataset/song_mapping.csv`: Maps 18-character MSD song codes $\to$ `int_song_id` (e.g., Item `103`, `21666`...).

---

## 4. HDFS Ingestion & Distribution

To upload the dataset into the distributed Hadoop HDFS cluster:

```bash
# 1. Access the Hadoop primary node container
docker exec -it h-primary bash

# 2. Create the HDFS directory hierarchy
hdfs dfs -mkdir -p /music/input
hdfs dfs -mkdir -p /music/processed
hdfs dfs -mkdir -p /music/mahout/input

# 3. Upload the 1,000,000 records file to HDFS
hdfs dfs -put /root/train_triplets_1m.txt /music/input/

# 4. Verify distribution across DataNodes
hdfs dfs -ls -h /music/input/
hdfs fsck /music/input/train_triplets_1m.txt -files -blocks -locations
```

---

## 5. Spark Distributed Batch Ingestion

Spark reads the raw text from `hdfs:///music/input/train_triplets_1m.txt`, enforces the schema, validates non-null rows, removes negative play counts, and saves the optimized partitioned Parquet dataset:

```bash
spark-submit \
  --master yarn \
  --deploy-mode client \
  --executor-memory 2G \
  scripts/spark_batch_process.py
```

Output is written to `hdfs:///music/processed` with Snappy compression.
