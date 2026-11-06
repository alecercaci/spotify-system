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
