# Mahout

Apache Mahout 0.13.0 is used for item-based collaborative filtering with `SIMILARITY_LOGLIKELIHOOD` and Top-N recommendations.

Expected Mahout workflow:

1. Prepare a Mahout input CSV from the processed user-song play counts.
2. Place the input in HDFS at `/music/mahout/input/mahout_input.csv`.
3. Run Mahout item-based recommender.
4. Copy the generated recommendation output to `output/mahout` for the FastAPI service, or set `MAHOUT_RECOMMENDATIONS_PATH` to the generated output location.

The API supports common Mahout output lines such as:

```text
1    [103:7.036205,21666:7.031693,33:7.0279803]
```

It also supports simple CSV rows:

```text
1,103,7.036205
```
