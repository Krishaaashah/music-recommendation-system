# Final Project Readiness and Security Audit

Updated: 2026-10-17

This document separates implemented code from runtime evidence. A Docker Compose file can describe a cluster, but the cluster is only proven when the services are started and their Hadoop/Spark dashboards and command output are captured.

## Current Architecture

The local demonstration stack now contains:

| Layer | Current design | Purpose |
|---|---|---|
| API | FastAPI on port 8000 | Recommendation, similarity, history, event, health and evaluation endpoints |
| Interface | Static frontend on port 3000 or Streamlit on 8501 | User-facing recommendation and project demonstration views |
| Document store | MongoDB on the internal Docker network | Semi-structured event/history persistence and indexed retrieval |
| HDFS | 1 NameNode plus 5 DataNodes | Distributed storage with replication factor 3 |
| YARN | 1 ResourceManager plus 5 NodeManagers | Hadoop resource and task scheduling |
| Spark | 1 master plus 5 workers | Batch processing and Structured Streaming execution |
| Recommender | Mahout Item-Based CF plus hybrid ranking | Offline collaborative recommendations and serving-time fusion |

Five DataNodes with replication 3 provide placement capacity and spare worker slots. They do not provide five independent machines: all containers still run on the same Docker host. Real host-level fault tolerance requires separate VMs or cloud instances, shared networking, persistent disks and a highly available NameNode design.

## Implemented

- Last.fm interaction data, mappings and metadata are wired into the serving path.
- Mahout recommendation output is parsed by FastAPI.
- Hybrid ranking combines collaborative, behavioral/content and popularity signals.
- Recommendations include item ID, track title, artist, score, rank and reason.
- Similar-song, history, live-event, health and evaluation endpoints are available.
- The UI has separate recommendation, catalog, live activity, architecture and evaluation views.
- The UI now has loading, error, empty and API-status states, including an animated request wheel.
- Docker Compose now declares five HDFS DataNodes, five YARN NodeManagers and five Spark workers.
- `HDFS_CONF_dfs_replication=3` is retained on the NameNode and every DataNode.
- Host-published services are bound to `127.0.0.1` for a safer local demonstration.

## Not Yet Proven at Runtime

These items must be run and captured before the final presentation:

1. Start the complete Compose stack from a clean Docker state.
2. Run `docker compose ps` and capture all expected services as running.
3. In the NameNode UI, show five live DataNodes and the configured replication value.
4. Run `hdfs dfsadmin -report` and capture the live capacity and DataNode count.
5. Run `yarn node -list` and show five NodeManagers.
6. Open the Spark master UI and show five registered workers.
7. Run the Spark bronze/silver/gold pipeline against the mounted Last.fm data.
8. Regenerate or verify Mahout output and call `/recommend/{user_id}`.
9. Show MongoDB-connected health output and a stored live event.
10. Start the simulator, refresh the live activity view and capture changing counts.
11. Capture `/health`, `/docs`, a recommendation response, similar songs, evaluation metrics and the Hadoop/Spark dashboards.

## Vulnerabilities and Risks

### High priority before any public or cloud deployment

- MongoDB currently has no authentication or TLS. It is acceptable only for an isolated local demo. Enable a root/user account, move credentials to an ignored `.env` or secret manager, and use an authenticated connection string before deployment.
- Hadoop NameNode, YARN and Spark administration endpoints are development endpoints with no authentication or TLS. They must remain private to the Docker network or a protected management network.
- FastAPI documentation and all application endpoints are unauthenticated. Add API authentication, rate limiting and HTTPS before exposing the service outside localhost.

### Medium priority

- The Hadoop image is an old Hadoop 3.2.1/Java 8 image. It should be replaced with a maintained image after compatibility testing. Spark now uses the official Apache Spark 3.5.9 Python image because the previous Bitnami tag was no longer available.
- Spark authentication, RPC encryption, local-storage encryption and SSL are explicitly disabled for this local demonstration. They must be enabled for a multi-host deployment.
- Docker images use tags rather than immutable digests, and Python dependencies use broad minimum-version ranges. Pin versions and generate a lock or hash-checked requirements file for reproducibility.
- The API image currently runs as root. Add a non-root runtime user and a read-only root filesystem where the streaming write path permits it.
- There are no API rate limits, centralized audit logs, automated backups or recovery tests yet.
- The health endpoint reports Hadoop and Spark as configured but does not probe their live runtime state. A final production version should perform bounded service checks and report worker counts.

### Low priority / presentation hygiene

- Student name and PRN are returned by the root and info endpoints. Keep them for a classroom demo only; remove them from any public deployment.
- The UI loads Google Fonts and image assets from external URLs. Bundle or self-host those assets if the final demonstration must work offline.
- All logical nodes share one host, so a host failure stops the entire cluster. Present this as a local scale-out simulation, not cloud-grade high availability.

## Recommended Final Sequence

1. Validate the Compose file and pull images.
2. Start infrastructure first, then API and UI.
3. Verify HDFS, YARN and Spark worker counts from their native dashboards/CLIs.
4. Run the data pipeline and record bronze, silver and gold output locations.
5. Verify Mahout output and the hybrid API response.
6. Exercise live event ingestion and MongoDB persistence.
7. Capture screenshots and save command output under `screenshots/`.
8. Run the automated test suite and record the exact result in the report.
9. Only after this evidence exists, describe the project as runtime-verified and scalable in the presentation.

## Useful Verification Commands

```powershell
docker compose config --quiet
docker compose up -d mongodb h-primary h-primary-yarn h-worker1 h-worker1-yarn h-worker2 h-worker2-yarn h-worker3 h-worker3-yarn h-worker4 h-worker4-yarn h-worker5 h-worker5-yarn
docker compose up -d spark-master spark-worker1 spark-worker2 spark-worker3 spark-worker4 spark-worker5
docker compose ps
docker exec h-primary hdfs dfsadmin -report
docker exec h-primary-yarn yarn node -list
docker exec h-primary-spark /opt/bitnami/spark/bin/spark-submit --version
```

The final three commands depend on the exact command paths exposed by the selected images; if an image does not include the CLI at that path, use its dashboard or shell to locate the equivalent command and record the result.
