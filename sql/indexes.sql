-- Secondary indexes, created by the loader after the data is in.
-- The benchmark times every query before and after them.
-- Primary keys and UNIQUE columns already have an index, so they are not listed here.

-- artist_track's primary key starts with artist_id; this one finds the artists of a track
CREATE INDEX IF NOT EXISTS idx_artist_track_track ON artist_track (track_id);
-- same for track_genre: its primary key starts with track_id, this one goes from a genre to its tracks
CREATE INDEX IF NOT EXISTS idx_track_genre_genre  ON track_genre (genre_id);
-- "the most popular tracks": PostgreSQL reads the first entries instead of sorting the table
CREATE INDEX IF NOT EXISTS idx_track_popularity   ON track (popularity DESC);
-- looking up a track by its name
CREATE INDEX IF NOT EXISTS idx_track_name         ON track (track_name);
-- grouping and filtering by key and mode (query 7)
CREATE INDEX IF NOT EXISTS idx_features_key       ON audio_features (key_signature, mode);
