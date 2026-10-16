-- The pgvector image ships the extension but does not enable it, and the
-- halfvec column type does not exist until it is created. Without this a
-- fresh database makes the api crash on startup with
-- "type halfvec does not exist", which reads like a code bug.
--
-- Files here run once, on an empty data directory only.
CREATE EXTENSION IF NOT EXISTS vector;
