"""Loader: downloads the Spotify Tracks CSV, cleans it, and loads it into PostgreSQL.

Usage (inside the container):
    python load.py                      # all the data, fast COPY load (what docker compose up runs)
    python load.py --scale 0.25         # a random 25% of the tracks, for the measurements
    python load.py --mode rowwise       # one INSERT per row (slow, to compare with COPY)

Prints what the cleaning changed, then one JSON line with the timings (read by measure/benchmark.py).
"""
import argparse
import io
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # for common/ when run locally
from common.db import connect  # noqa: E402

SQL_DIR = Path(os.environ.get("SQL_DIR", Path(__file__).resolve().parent.parent / "sql"))
DATA_PATH = Path(os.environ.get("DATA_PATH", "/data/spotify-tracks.csv"))
DATA_URL = os.environ.get("DATA_URL", "")

KEYS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]  # Spotify: 0 = C, 1 = C#...
FEATURES = ["danceability", "energy", "valence", "acousticness", "instrumentalness",
            "liveness", "speechiness", "loudness", "tempo"]


# ---------------------------------------------------------------- 1. get the data
def get_csv() -> Path:
    """Download the CSV if DATA_URL is set and the file is not there yet."""
    if DATA_URL and not DATA_PATH.exists():
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {DATA_URL}", flush=True)
        urllib.request.urlretrieve(DATA_URL, DATA_PATH)
    if not DATA_PATH.exists():
        sys.exit(f"Data file not found: {DATA_PATH} (set DATA_URL in .env)")
    return DATA_PATH


# ---------------------------------------------------------------- 2. clean it
def clean(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (track, genre), with valid values. Prints what it changed."""
    report = {"rows_in_file": len(df)}
    df = df.drop(columns=[c for c in df.columns if c.startswith("Unnamed")])

    # 1. rows that appear twice, identical in every column
    dup = df.duplicated()
    report["exact_duplicate_rows_dropped"] = int(dup.sum())
    df = df[~dup]

    # 2. one track has no name, artist or album
    missing = df[["track_name", "artists", "album_name"]].isna().any(axis=1)
    report["rows_without_name_dropped"] = int(missing.sum())
    df = df[~missing].copy()

    # 3. the same track has a different popularity in different genre rows: keep the highest
    pop = df.groupby("track_id")["popularity"].transform("max")
    report["tracks_with_different_popularity"] = int(
        df.loc[df["popularity"] != pop, "track_id"].nunique())
    df["popularity"] = pop

    # 4. tempo 0 and time signature 0 mean "unknown", not a real value
    report["tempo_unknown"] = int((df.drop_duplicates("track_id")["tempo"] == 0).sum())
    report["time_signature_unknown"] = int(
        (df.drop_duplicates("track_id")["time_signature"] == 0).sum())
    df["tempo"] = df["tempo"].where(df["tempo"] > 0)
    df["time_signature"] = df["time_signature"].where(df["time_signature"] > 0).astype("Int64")

    # 5. numbers to readable labels
    df["key_signature"] = df["key"].map(lambda k: KEYS[int(k)])
    df["mode_name"] = df["mode"].map({1: "Major", 0: "Minor"})
    for col in ["track_name", "album_name", "artists", "track_genre"]:
        df[col] = df[col].astype(str).str.strip()

    report["rows_kept"] = len(df)
    report["distinct_tracks"] = int(df["track_id"].nunique())
    print("cleaning:", json.dumps(report), flush=True)
    return df.reset_index(drop=True)


def sample(df: pd.DataFrame, fraction: float) -> pd.DataFrame:
    """Keep a random `fraction` of the tracks (with all their genres), for the measurements.

    Random and not the first rows, because the file is sorted by genre: the first 25% of the
    rows would be the first 25% of the genres only. The seed makes it the same every run.
    """
    if fraction >= 1:
        return df
    ids = df["track_id"].drop_duplicates().sample(frac=fraction, random_state=42)
    return df[df["track_id"].isin(ids)].reset_index(drop=True)


# ---------------------------------------------------------------- 3. split into tables
def build_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """One DataFrame per table, in the order they must be loaded (foreign keys)."""
    tracks = df.drop_duplicates("track_id")

    # artists: "Ingrid Michaelson;ZAYN" -> two rows, with their position
    pairs = tracks[["track_id", "artists"]].assign(artist_name=tracks["artists"].str.split(";"))
    pairs = pairs.explode("artist_name")
    pairs["artist_name"] = pairs["artist_name"].str.strip()
    pairs = pairs[pairs["artist_name"] != ""]
    pairs["position"] = pairs.groupby("track_id").cumcount() + 1
    artists = pd.DataFrame({"artist_name": pairs["artist_name"].drop_duplicates().to_list()})
    artists["artist_id"] = artists.index + 1
    artist_track = pairs.merge(artists, on="artist_name")[["artist_id", "track_id", "position"]]

    genres = pd.DataFrame({"genre_name": sorted(df["track_genre"].unique())})
    genres["genre_id"] = genres.index + 1
    track_genre = (df[["track_id", "track_genre"]]
                   .merge(genres, left_on="track_genre", right_on="genre_name")
                   [["track_id", "genre_id"]])

    return {
        "artist": artists[["artist_id", "artist_name"]],
        "genre": genres[["genre_id", "genre_name"]],
        "track": tracks[["track_id", "track_name", "album_name", "popularity",
                         "duration_ms", "explicit"]],
        "artist_track": artist_track,
        "track_genre": track_genre,
        "audio_features": tracks[["track_id", *FEATURES, "key_signature", "mode_name",
                                  "time_signature"]],
    }


COLUMNS = {
    "artist": "artist_id, artist_name",
    "genre": "genre_id, genre_name",
    "track": "track_id, track_name, album_name, popularity, duration_ms, explicit",
    "artist_track": "artist_id, track_id, position",
    "track_genre": "track_id, genre_id",
    "audio_features": "track_id, danceability, energy, valence, acousticness, instrumentalness, "
                      "liveness, speechiness, loudness, tempo, key_signature, mode, time_signature",
}


# ---------------------------------------------------------------- 4. load
def load_copy(conn, tables):
    """Fast path: one COPY per table (all the rows in one go)."""
    with conn.cursor() as cur:
        for name, frame in tables.items():
            buf = io.StringIO()
            frame.to_csv(buf, index=False, header=False)
            buf.seek(0)
            with cur.copy(f"COPY {name} ({COLUMNS[name]}) FROM STDIN WITH (FORMAT csv)") as cp:
                cp.write(buf.read())
    conn.commit()


def load_rowwise(conn, tables):
    """Slow path: one INSERT statement per row, to compare with COPY."""
    with conn.cursor() as cur:
        for name, frame in tables.items():
            cols = COLUMNS[name]
            marks = ", ".join(["%s"] * len(cols.split(",")))
            sql = f"INSERT INTO {name} ({cols}) VALUES ({marks})"
            for row in frame.astype(object).where(frame.notna(), None).itertuples(index=False):
                cur.execute(sql, tuple(v.item() if hasattr(v, "item") else v for v in row))
    conn.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", type=float, default=float(os.environ.get("SCALE", 1)))
    parser.add_argument("--mode", choices=["copy", "rowwise"], default="copy")
    parser.add_argument("--no-index", action="store_true", help="skip secondary indexes")
    args = parser.parse_args()

    t = {}
    start = time.perf_counter()

    path = get_csv()
    df = sample(clean(pd.read_csv(path)), args.scale)
    tables = build_tables(df)
    t["prepare_s"] = time.perf_counter() - start

    with connect() as conn:
        t0 = time.perf_counter()
        conn.execute((SQL_DIR / "schema.sql").read_text())
        conn.commit()
        t["schema_s"] = time.perf_counter() - t0

        t0 = time.perf_counter()
        (load_copy if args.mode == "copy" else load_rowwise)(conn, tables)
        t["insert_s"] = time.perf_counter() - t0

        t0 = time.perf_counter()
        if not args.no_index:
            conn.execute((SQL_DIR / "indexes.sql").read_text())
        conn.execute("ANALYZE")
        conn.commit()
        t["index_s"] = time.perf_counter() - t0

        size = conn.execute("SELECT pg_database_size(current_database())").fetchone()[0]

    t["total_s"] = time.perf_counter() - start
    result = {"scale": args.scale, "mode": args.mode,
              "tracks": len(tables["track"]), "rows": sum(len(f) for f in tables.values()),
              "csv_bytes": path.stat().st_size, "db_bytes": size,
              **{k: round(v, 4) for k, v in t.items()}}
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
