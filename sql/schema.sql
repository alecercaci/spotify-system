-- Schema for the Spotify Tracks dataset (PostgreSQL 16). Diagram: docs/er-diagram.png
--   * track_id is Spotify's own id (22 characters), so it is the natural primary key of track
--   * artist and track are many-to-many (a track can have several artists): artist_track,
--     with the artist's position (1 = main artist)
--   * genre and track are many-to-many too (the same track is listed under up to 9 genres):
--     track_genre
--   * audio_features is a weak entity: one row per track, track_id is both its primary key
--     and a foreign key to track
--   * names are TEXT: some track and album names are longer than 500 characters

DROP TABLE IF EXISTS artist_track, track_genre, audio_features, track, artist, genre CASCADE;
DROP TYPE IF EXISTS key_signature_t, mode_t;

CREATE TYPE key_signature_t AS ENUM ('C','C#','D','D#','E','F','F#','G','G#','A','A#','B');
CREATE TYPE mode_t AS ENUM ('Major','Minor');

CREATE TABLE artist (
    artist_id   INT PRIMARY KEY,
    artist_name TEXT NOT NULL UNIQUE
);

CREATE TABLE genre (
    genre_id   INT PRIMARY KEY,
    genre_name TEXT NOT NULL UNIQUE
);

CREATE TABLE track (
    track_id    CHAR(22) PRIMARY KEY,
    track_name  TEXT NOT NULL,
    album_name  TEXT NOT NULL,
    popularity  SMALLINT NOT NULL CHECK (popularity BETWEEN 0 AND 100),
    duration_ms INT NOT NULL CHECK (duration_ms > 0),
    explicit    BOOLEAN NOT NULL
);

CREATE TABLE artist_track (
    artist_id INT      NOT NULL REFERENCES artist(artist_id) ON DELETE CASCADE,
    track_id  CHAR(22) NOT NULL REFERENCES track(track_id)   ON DELETE CASCADE,
    position  SMALLINT NOT NULL CHECK (position >= 1),
    PRIMARY KEY (artist_id, track_id)
);

CREATE TABLE track_genre (
    track_id CHAR(22) NOT NULL REFERENCES track(track_id) ON DELETE CASCADE,
    genre_id INT      NOT NULL REFERENCES genre(genre_id) ON DELETE CASCADE,
    PRIMARY KEY (track_id, genre_id)
);

CREATE TABLE audio_features (
    track_id         CHAR(22) PRIMARY KEY REFERENCES track(track_id) ON DELETE CASCADE,
    danceability     REAL NOT NULL CHECK (danceability     BETWEEN 0 AND 1),
    energy           REAL NOT NULL CHECK (energy           BETWEEN 0 AND 1),
    valence          REAL NOT NULL CHECK (valence          BETWEEN 0 AND 1),
    acousticness     REAL NOT NULL CHECK (acousticness     BETWEEN 0 AND 1),
    instrumentalness REAL NOT NULL CHECK (instrumentalness BETWEEN 0 AND 1),
    liveness         REAL NOT NULL CHECK (liveness         BETWEEN 0 AND 1),
    speechiness      REAL NOT NULL CHECK (speechiness      BETWEEN 0 AND 1),
    loudness         REAL NOT NULL,                      -- decibels, usually -60 to 0
    tempo            REAL CHECK (tempo > 0),             -- beats per minute, NULL if unknown
    key_signature    key_signature_t NOT NULL,
    mode             mode_t NOT NULL,
    time_signature   SMALLINT CHECK (time_signature BETWEEN 1 AND 7)  -- beats per bar, NULL if unknown
);
