# Output

Generated files should be placed here during local runs.

Recommended local layout:

```text
output/
  mahout/
    part-r-00000
```

The FastAPI backend reads Mahout recommendations from `output/mahout` by default. To use another file or directory, set:

```text
MAHOUT_RECOMMENDATIONS_PATH=/path/to/mahout/output
```

The recommendation output itself is generated data and should not be committed.
