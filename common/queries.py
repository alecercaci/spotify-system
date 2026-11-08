"""The analysis queries, shared by the dashboard (app/) and the benchmark (measure/).

Each entry is  number: (title shown in the dashboard, SQL).
The dashboard draws a bar chart with the first text column as labels and the LAST number column
as values, so in every query the main result is the last column.
"""

QUERIES = {
    1: (
        "Most popular genres",
        """
        SELECT g.genre_name,
               COUNT(*)                        AS tracks,
               ROUND(AVG(t.popularity), 1)     AS avg_popularity
        FROM genre g
        JOIN track_genre tg ON tg.genre_id = g.genre_id
        JOIN track t        ON t.track_id  = tg.track_id
        GROUP BY g.genre_name
        ORDER BY avg_popularity DESC
        LIMIT 15;
        """,
    ),
    2: (
        "What do popular tracks sound like? Audio features by popularity band",
        """
        SELECT CASE WHEN t.popularity = 0   THEN '0'
                    WHEN t.popularity <= 25 THEN '1-25'
                    WHEN t.popularity <= 50 THEN '26-50'
                    WHEN t.popularity <= 75 THEN '51-75'
                    ELSE '76-100' END                       AS popularity_band,
               COUNT(*)                                     AS tracks,
               ROUND(AVG(f.energy)::numeric, 3)             AS avg_energy,
               ROUND(AVG(f.valence)::numeric, 3)            AS avg_valence,
               ROUND(AVG(f.acousticness)::numeric, 3)       AS avg_acousticness,
               ROUND(AVG(f.instrumentalness)::numeric, 3)   AS avg_instrumentalness,
               ROUND(AVG(f.danceability)::numeric, 3)       AS avg_danceability
        FROM track t
        JOIN audio_features f ON f.track_id = t.track_id
        GROUP BY popularity_band
        ORDER BY popularity_band;
        """,
    ),
    3: (
        "The sound of each genre: the 10 most danceable genres",
        """
        SELECT g.genre_name,
               ROUND(AVG(f.energy)::numeric, 3)       AS avg_energy,
               ROUND(AVG(f.valence)::numeric, 3)      AS avg_valence,
               ROUND(AVG(f.tempo)::numeric, 1)        AS avg_tempo_bpm,
               ROUND(AVG(f.danceability)::numeric, 3) AS avg_danceability
        FROM genre g
        JOIN track_genre tg   ON tg.genre_id = g.genre_id
        JOIN audio_features f ON f.track_id  = tg.track_id
        GROUP BY g.genre_name
        ORDER BY avg_danceability DESC
        LIMIT 10;
        """,
    ),
    4: (
        "Do explicit lyrics help? Popularity of explicit and clean tracks",
        """
        SELECT CASE WHEN explicit THEN 'Explicit' ELSE 'Clean' END AS lyrics,
               COUNT(*)                    AS tracks,
               ROUND(AVG(popularity), 1)   AS avg_popularity
        FROM track
        GROUP BY explicit
        ORDER BY avg_popularity DESC;
        """,
    ),
    5: (
        "Most popular artists (at least 10 tracks as main artist)",
        """
        SELECT a.artist_name,
               COUNT(*)                     AS tracks,
               MAX(t.popularity)            AS best_track,
               ROUND(AVG(t.popularity), 1)  AS avg_popularity
        FROM artist a
        JOIN artist_track at ON at.artist_id = a.artist_id AND at.position = 1
        JOIN track t         ON t.track_id   = at.track_id
        GROUP BY a.artist_name
        HAVING COUNT(*) >= 10
        ORDER BY avg_popularity DESC
        LIMIT 15;
        """,
    ),
    6: (
        "Valence (happiness) vs popularity",
        """
        SELECT CASE WHEN f.valence < 0.3  THEN 'Low (<0.3)'
                    WHEN f.valence <= 0.7 THEN 'Moderate (0.3-0.7)'
                    ELSE 'High (>0.7)' END   AS happiness_level,
               COUNT(*)                      AS tracks,
               ROUND(AVG(t.popularity), 1)   AS avg_popularity
        FROM audio_features f
        JOIN track t ON t.track_id = f.track_id
        GROUP BY happiness_level
        ORDER BY avg_popularity DESC;
        """,
    ),
    7: (
        "Keys and modes: how often they are used, and how popular they are",
        """
        SELECT f.key_signature || ' ' || f.mode AS key_and_mode,
               ROUND(AVG(t.popularity), 1)      AS avg_popularity,
               COUNT(*)                         AS tracks
        FROM audio_features f
        JOIN track t ON t.track_id = f.track_id
        GROUP BY f.key_signature, f.mode
        ORDER BY tracks DESC;
        """,
    ),
    8: (
        "Tracks listed under the most genres",
        """
        SELECT t.track_name,
               t.album_name,
               STRING_AGG(DISTINCT a.artist_name, ', ') AS artists,
               STRING_AGG(DISTINCT g.genre_name, ', ')  AS genres,
               COUNT(DISTINCT g.genre_id)               AS number_of_genres
        FROM track t
        JOIN track_genre tg  ON tg.track_id  = t.track_id
        JOIN genre g         ON g.genre_id   = tg.genre_id
        JOIN artist_track at ON at.track_id  = t.track_id
        JOIN artist a        ON a.artist_id  = at.artist_id
        GROUP BY t.track_id, t.track_name, t.album_name
        ORDER BY number_of_genres DESC, t.track_name
        LIMIT 15;
        """,
    ),
}
