# Output

Generated files should be placed here during local runs.

Recommended local layout:

```text
output/
  mahout/
    part-r-00000
  local-cf-train-split/
    part-r-00000
  local-cf-top100/
    part-r-00000
  local-cf-top70/
    part-r-00000
```

The FastAPI backend reads Mahout recommendations from `output/mahout` by default. To use another file or directory, set:

```text
MAHOUT_RECOMMENDATIONS_PATH=/path/to/mahout/output
```

The Mahout recommendation output is generated data and should normally not be committed.

The checked-in `local-cf-train-split` artifact is the reproducible local benchmark
used by the Docker evaluation endpoint when Mahout is unavailable. Regenerate it
with `python scripts/build_local_cf_benchmark.py`.

The optional `local-cf-top100` artifact is generated with `--k 100` for wider
Recall@100 and Hit Rate@100 analysis.

The `local-cf-top70` artifact is generated with `--k 70` and is useful for the
intermediate Recall@70 and Hit Rate@70 report point.
