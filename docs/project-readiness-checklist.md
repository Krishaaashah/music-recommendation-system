# Project Readiness Checklist

This checklist records the current implementation status of the scalable music recommendation project.

## Implemented

- [x] Active Last.fm dataset wired into the serving path.
- [x] `train_triplets.txt`, song mapping, user mapping, and song metadata are kept as separate data layers.
- [x] Apache Mahout recommendation output is parsed and used by the FastAPI recommendation endpoint.
- [x] Hybrid ranking combines collaborative filtering, metadata similarity, and popularity signals.
- [x] Track title, artist, item ID, score, and recommendation reason are returned to the UI.
- [x] User listening history endpoint is connected to the frontend.
- [x] Similar-song endpoint supports catalog metadata and behavioral similarity fallback.
- [x] FastAPI health status exposes dataset size, catalog size, prepared profiles, and MongoDB fallback status.
- [x] Live event ingestion, simulator controls, event statistics, and recent event feed are available.
- [x] Evaluation endpoint exposes precision, recall, MRR, coverage, evaluated users, and split information.
- [x] Static frontend has a responsive music-product layout inspired by the reference application.
- [x] Static frontend has loading, error, empty, API status, recommendation, history, similar-song, activity, architecture, and evaluation states.
- [x] Streamlit dashboard uses the same visual language and current Last.fm terminology.
- [x] Docker Compose definitions include the API, MongoDB, Hadoop/Spark services, and replication-factor configuration.

## Verify Before Final Demonstration

- [ ] Run the complete Docker Compose stack from a clean start.
- [ ] Confirm all Hadoop/Spark worker containers are healthy and the replication factor is visible in the logs.
- [ ] Run the Spark ingest/processing job against the mounted dataset.
- [ ] Confirm Mahout output is regenerated successfully and the API serves the new output.
- [ ] Start MongoDB and confirm the dashboard changes from cache fallback to MongoDB connected.
- [ ] Start the live simulator and capture the event feed and updated statistics.
- [ ] Capture final evidence screenshots for the report: API health, recommendation response, similar songs, live events, architecture, and evaluation metrics.

## Current Local Evidence

The prepared local data currently reports 4,620,928 interaction rows, 1,505,202 catalog tracks, and 874 recommendation profiles. The browser frontend has been verified against the live FastAPI service using user `3143`; named tracks, artists, scores, history, and live activity render correctly.

## Demo URLs

- Static frontend: `http://localhost:3000/index.html?api=http://localhost:8001`
- FastAPI docs: `http://localhost:8001/docs`
- FastAPI health: `http://localhost:8001/health`
