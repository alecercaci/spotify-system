"""Benchmark: how long loading and querying take, and how much disk the data uses.

Run with:  docker compose --profile measure run --rm --build benchmark
Results go to measure/results/: results.csv has every single run, results.md the averages.

For each data size (a random 25%, 50% and 100% of the tracks):
  1. load the data with COPY, then row by row, REPEATS times each (default 3), and time it
  2. run every query without the secondary indexes, then create them and run them again
  3. measure the size of the tables, with and without indexes
Change one thing at a time: same laptop, same data, only the size or the index changes.

It reloads the database, so afterwards run `docker compose up loader` to get 100% back.
Settings (environment variables): SCALES, REPEATS, ROWWISE_MAX_SCALE.
"""
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common.db import connect  # noqa: E402
from common.queries import QUERIES  # noqa: E402

LOADER = Path(os.environ.get("LOADER", ROOT / "loader" / "load.py"))
SQL_DIR = Path(os.environ.get("SQL_DIR", ROOT / "sql"))
OUT = Path(os.environ.get("RESULTS_DIR", ROOT / "measure" / "results"))
REPEATS = int(os.environ.get("REPEATS", 3))
SCALES = [float(s) for s in os.environ.get("SCALES", "0.25,0.5,1").split(",")]
# Two extra queries, only for the benchmark. They need just a few rows, so this is where an
# index should help; the analysis queries read every row anyway.
LOOKUPS = [
    ("lookup_name", ("Find a track by name",
                     "SELECT track_id, popularity FROM track WHERE track_name = 'Blinding Lights';")),
    ("lookup_top10", ("The 10 most popular tracks",
                      "SELECT track_name, popularity FROM track ORDER BY popularity DESC LIMIT 10;")),
]
# Row-by-row loading is slow: it is run only for sizes up to this one (1 = all of them)
ROWWISE_MAX = float(os.environ.get("ROWWISE_MAX_SCALE", 1))


def load(scale: float, mode: str) -> dict:
    """Run the loader as a separate program and read the timings it prints (its last line)."""
    out = subprocess.run([sys.executable, str(LOADER), "--scale", str(scale), "--mode", mode,
                          "--no-index"], capture_output=True, text=True)
    if out.returncode != 0:  # show why the loader failed, then stop
        sys.exit(f"Loader failed (scale={scale}, mode={mode}):\n{out.stdout}{out.stderr}")
    return json.loads(out.stdout.strip().splitlines()[-1])


def time_query(conn, sql: str) -> float:
    """Seconds to run a query and fetch all its rows."""
    t0 = time.perf_counter()
    conn.execute(sql).fetchall()
    return time.perf_counter() - t0


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []

    for scale in SCALES:
        modes = ["copy"] + (["rowwise"] if scale <= ROWWISE_MAX else [])
        for mode in modes:
            for rep in range(REPEATS):
                r = load(scale, mode)
                print(f"scale={scale} mode={mode} rep={rep} load={r['insert_s']:.3f}s", flush=True)
                rows.append({"test": f"load_{mode}", "scale": scale, "rep": rep,
                             "seconds": r["insert_s"], "tracks": r["tracks"]})
                rows.append({"test": f"full_load_run_{mode}", "scale": scale, "rep": rep,
                             "seconds": r["total_s"], "tracks": r["tracks"]})

        # database is now loaded at this scale (copy or rowwise, same content), without indexes
        with connect() as conn:
            size_no_idx = conn.execute("SELECT pg_database_size(current_database())").fetchone()[0]
            for phase in ("no_index", "index"):
                if phase == "index":
                    conn.execute((SQL_DIR / "indexes.sql").read_text())
                    conn.execute("ANALYZE")
                    conn.commit()
                for qid, (_, sql) in [*QUERIES.items(), *LOOKUPS]:
                    time_query(conn, sql)  # first run only warms the cache, not counted
                    for rep in range(REPEATS):
                        rows.append({"test": f"q{qid}_{phase}", "scale": scale, "rep": rep,
                                     "seconds": time_query(conn, sql), "tracks": r["tracks"]})
            size_idx = conn.execute("SELECT pg_database_size(current_database())").fetchone()[0]
            # only our tables and their indexes, without PostgreSQL's own system tables
            tables = conn.execute(
                "SELECT SUM(pg_total_relation_size(c.oid))::bigint FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relkind = 'r'"
            ).fetchone()[0]
        # the CSV is always the whole file, so its size is scaled to compare like with like
        rows.append({"test": "csv_bytes_equiv", "scale": scale, "value": r["csv_bytes"] * scale})
        rows.append({"test": "tables_bytes", "scale": scale, "value": tables})
        rows.append({"test": "db_bytes_no_index", "scale": scale, "value": size_no_idx})
        rows.append({"test": "db_bytes_index", "scale": scale, "value": size_idx})

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "results.csv", index=False)

    # summary: average seconds per test and scale; sizes in MB
    times = df[df["seconds"].notna()].pivot_table(index="test", columns="scale",
                                                  values="seconds", aggfunc=statistics.mean)
    sizes = df[df["value"].notna()].pivot_table(index="test", columns="scale",
                                                values="value", aggfunc="first") / 1e6
    tracks = df[df["tracks"].notna()].groupby("scale")["tracks"].first()
    with open(OUT / "results.md", "w") as f:
        f.write(f"Tracks per scale: {tracks.astype(int).to_dict()}\n\n")
        f.write(f"### Time (seconds, average of {REPEATS} runs)\n\n")
        f.write(times.round(4).to_markdown() + "\n\n")
        f.write("### Disk (MB)\n\n")
        f.write(sizes.round(3).to_markdown() + "\n")
    print((OUT / "results.md").read_text())


if __name__ == "__main__":
    main()
