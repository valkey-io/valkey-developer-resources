CREATE TABLE IF NOT EXISTS catalog (
    id              VARCHAR(36) PRIMARY KEY,
    title           VARCHAR(255) NOT NULL,
    genre           VARCHAR(50) NOT NULL,
    description     TEXT,
    tags            TEXT,
    release_year    INTEGER,
    rating          DOUBLE PRECISION DEFAULT 0,
    duration_minutes DOUBLE PRECISION DEFAULT 0,
    video_path      TEXT,
    thumbnail_path  TEXT,
    created_at      TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS watch_history (
    user_id          VARCHAR(36) NOT NULL,
    catalog_id       VARCHAR(36) NOT NULL,
    title            VARCHAR(255),
    resume_timestamp BIGINT DEFAULT 0,
    completed        BOOLEAN DEFAULT false,
    last_watched     BIGINT DEFAULT 0,
    PRIMARY KEY (user_id, catalog_id)
);
