#!/usr/bin/env bash
# Apache Mahout 0.13.0 Item-based Collaborative Filtering Recommender Job
# Similarity: SIMILARITY_LOGLIKELIHOOD
# Top 10 recommendations per user

set -euo pipefail

INPUT_HDFS="${1:-${HDFS_MAHOUT_INPUT:-/music/mahout/input/mahout_input.csv}}"
OUTPUT_HDFS="${2:-${HDFS_MAHOUT_OUTPUT:-/music/mahout/output}}"
SIMILARITY="${3:-${MAHOUT_SIMILARITY:-SIMILARITY_LOGLIKELIHOOD}}"
NUM_RECS="${4:-${MAHOUT_NUM_RECOMMENDATIONS:-10}}"

echo "=== Running Apache Mahout Recommendation Job ==="
echo "Input: ${INPUT_HDFS}"
echo "Output: ${OUTPUT_HDFS}"
echo "Similarity: ${SIMILARITY}"
echo "Number of recommendations per user: ${NUM_RECS}"

# Remove previous output directory if it exists
hdfs dfs -rm -r -f "${OUTPUT_HDFS}" || true

# Execute Mahout Item-Based Recommender MapReduce Job
mahout recommenditembased \
    --input "${INPUT_HDFS}" \
    --output "${OUTPUT_HDFS}" \
    --similarityClassname "${SIMILARITY}" \
    --numRecommendations "${NUM_RECS}"

echo "=== Mahout Recommender Job Finished ==="
hdfs dfs -ls "${OUTPUT_HDFS}"
