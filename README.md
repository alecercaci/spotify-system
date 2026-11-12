# Spotify tracks: what makes a track popular?

Which audio features (energy, danceability, valence...), genres and artists go with the most
popular tracks on Spotify?

## Team

TODO: names and GitHub usernames

## The six questions

| | |
|---|---|
| **Question** | Which audio features, genres and artists go with the most popular tracks on Spotify? |
| **Data** | [Spotify Tracks Dataset](https://huggingface.co/datasets/maharshipandya/spotify-tracks-dataset) on Hugging Face: 114,000 rows, 21 columns, 20 MB CSV, 114 genres. Licence: BSD. Downloaded by the loader from a direct link, no login (`DATA_URL` in `.env.example`). Downloaded: 5 November 2026. |
| **Database** | PostgreSQL. Every track has the same columns, and tracks are linked many-to-many both to artists (a track can have several artists) and to genres (a track can be listed under several genres): this fits tables with foreign keys. |
| **Processing** | The loader cleans the CSV (duplicates, an empty row, different popularity for the same track, unknown values), splits it into 6 tables and loads them with `COPY`. The analysis is 8 SQL queries (`common/queries.py`). |
| **Output** | A Streamlit dashboard: pick a question, see a chart, the table, and how long the query took. |
| **Measurements** | Load time (row-by-row `INSERT` vs `COPY`), time of each query with and without indexes, peak memory per container, database size vs CSV size, at 25%, 50% and 100% of the tracks. |

## Data

Each row of the file is a track **in one genre**: the dataset has about 1,000 tracks per genre,
chosen by its author, so it is not a random sample of everything on Spotify.
`popularity` is Spotify's score from 0 to 100, based on how much the track is played recently.

The loader downloads the CSV into `data/spotify-tracks.csv` the first time it runs (the folder is
empty on GitHub). It is cleaned in `loader/load.py` (`clean()`), which prints what it changed:

| Problem in the original file | How many | What we do |
|---|---|---|
| Rows identical in every column | 450 rows | Dropped |
| Track with no name, artist or album | 1 row | Dropped |
| Same track listed under several genres | 16,299 tracks (up to 9 genres) | One row in `track`, one row per genre in `track_genre` |
| Same track with a different popularity in different genre rows | 720 tracks | Keep the highest value |
| `tempo` = 0 (unknown) | 157 tracks | `NULL` |
| `time_signature` = 0 (unknown) | 162 tracks | `NULL` |
| `key` and `mode` stored as numbers (0–11, 0/1) | all | Labels: `C`, `C#`... and `Major` / `Minor` |

Result: 113,549 rows kept, **89,740 distinct tracks**, 29,858 artists, 114 genres.

For the measurements the loader can keep a **random** part of the tracks (`--scale 0.25`), always
the same thanks to a fixed seed. Random, not the first rows, because the file is sorted by genre:
the first 25% of the rows would contain only the first genres.

## Measurements

Laptop: MacBook Pro 13" (2020), Apple M1, 8 GB RAM, macOS Sequoia 15.3, Docker Desktop for Mac.
Every time is the average of 3 runs. Sizes are a random 25%, 50% and 100% of the tracks.
The benchmark also saves every run in `measure/results/` on the laptop that runs it (not uploaded to GitHub).

| Measurement | 25% | 50% | 100% |
|---|---|---|---|
| Tracks | 22,435 | 44,870 | 89,740 |
| Full run of the loader, start to end (without secondary indexes) | 1.95 s | 3.15 s | 5.49 s |
| Load with `COPY` | 1.05 s | 2.13 s | 4.35 s |
| Load row by row (`INSERT`) | 11.2 s | 21.7 s | 43.0 s |
| Query 1 (most popular genres), no index / index | 9.1 / 8.6 ms | 18.9 / 17.7 ms | 38.3 / 35.7 ms |
| Query 8 (tracks in most genres), no index / index | 101 / 101 ms | 205 / 202 ms | 462 / 461 ms |
| Find a track by name, no index / index | 1.0 / 0.1 ms | 1.9 / 0.1 ms | 3.8 / 0.1 ms |
| 10 most popular tracks, no index / index | 1.9 / 0.1 ms | 3.7 / 0.1 ms | 6.1 / 0.1 ms |
| Tables on disk (with indexes) | 19.0 MB | 36.7 MB | 71.3 MB |
| Same data as CSV | 5.0 MB | 10.1 MB | 20.1 MB |

Peak memory (`measure/memory.sh`, during the benchmark and a normal load): `db` 146 MiB,
benchmark 247 MiB, `loader` 184 MiB, `app` 34 MiB.

**What the numbers mean**

- **Loading grows linearly.** With `COPY`, 2× the tracks takes 2× the time (1.05 → 2.13 → 4.35 s).
  The full run adds about 1 s more: reading and cleaning the CSV in pandas (the benchmark loads
  without the secondary indexes, so building them is not included).
- **`COPY` is about 10× faster than one `INSERT` per row** (4.4 s vs 43 s for all the data).
  Each `INSERT` is a separate round trip to the database; `COPY` sends a whole table in one go.
- **Indexes help when a query needs a few rows, not when it reads everything.** Finding a track by
  name or the 10 most popular tracks goes from milliseconds to under 0.1 ms (about 40× and 60×
  faster), and with the index the time stays the same as the data grows, while without it it
  grows with the data (the database has to scan the whole table). The 8 analysis queries group
  all the tracks, so they read every row anyway: the index changes almost nothing.
- **Query 8 is the slowest** (0.46 s): it joins five tables and builds text lists
  (`STRING_AGG`) for every track before keeping the top 15.
- **The database is about 3.5× bigger than the CSV** (71 MB vs 20 MB). About 10 MB are the
  indexes; the rest comes from the 22-character `track_id` repeated in four tables, the two
  link tables, and the space PostgreSQL adds to every row.
- **Memory stays low**: the database never used more than 146 MiB, under 2% of the laptop's 8 GB.
