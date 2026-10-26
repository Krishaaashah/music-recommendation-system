# Live Verification Evidence

Captured on 2026-10-26 from the local application service.

## Verified live

- FastAPI health: `healthy`
- Mahout recommendation data: loaded
- Recommendation profiles: `20,729`
- Catalog items: `148,039`
- Source interactions scanned: `1,000,000`
- MongoDB: connected on port `27017` using the cached local MongoDB image
- Live events processed during capture: `72`
- Unique active users during capture: `68`
- Simulator: stopped after capture
- Recommendation dashboard: working
- Similar-song view: working with item `103`
- FastAPI Swagger UI: available at `/docs`
- Evaluation view: rendered configured Precision@10, Recall@10, MRR@10 and catalog coverage
- Architecture view: rendered HDFS, Spark, Mahout and FastAPI workflow

## Screenshot files

The screenshots are saved in the repository under `screenshots/`:

- `screenshots/recommendation-dashboard-live.png`
- `screenshots/similar-songs-live.png`
- `screenshots/live-activity-live.png`
- `screenshots/evaluation-live.png`
- `screenshots/architecture-live.png`
- `screenshots/fastapi-docs-live.png`
- `screenshots/fastapi-health-live.png`

## Screenshots captured in the verification session

1. Recommendation dashboard with FastAPI and MongoDB connected.
2. Similar-song results for item `103`.
3. Live activity feed with changing event counts and event rows.
4. Evaluation metrics page.
5. Architecture page.
6. FastAPI `/docs` page.
7. FastAPI `/health` JSON response.

## Infrastructure blocker

The project Compose stack was not fully started because Docker Hub could not pull the legacy `bde2020/hadoop-*` images and the old `bitnami/spark:3.5.9` tag no longer exists. The Spark reference was updated to the official Apache Spark 3.5.9 Python image, but Hadoop still requires image availability or a local image build before HDFS, YARN and Spark worker screenshots can be honestly captured.

Do not label the currently running containers from another Compose project as this music project’s HDFS/Spark cluster. The music application evidence above is valid; the Hadoop/Spark runtime evidence remains pending.
