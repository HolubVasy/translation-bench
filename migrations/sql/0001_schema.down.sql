-- Undo 0001_schema.up.sql (AB#300).
--
-- CASCADE takes the foreign keys with each table, so the order below is for
-- a reader, not for the database. IF EXISTS makes a half applied upgrade
-- undoable too.
--
-- No BEGIN or COMMIT: Alembic runs the revision in one transaction.

DROP TABLE IF EXISTS payments CASCADE;
DROP TABLE IF EXISTS payment_statuses CASCADE;
DROP TABLE IF EXISTS payment_providers CASCADE;
DROP TABLE IF EXISTS payment_provider_kinds CASCADE;
DROP TABLE IF EXISTS scores CASCADE;
DROP TABLE IF EXISTS findings CASCADE;
DROP TABLE IF EXISTS finding_kinds CASCADE;
DROP TABLE IF EXISTS run_outputs CASCADE;
DROP TABLE IF EXISTS runs CASCADE;
DROP TABLE IF EXISTS run_statuses CASCADE;
DROP TABLE IF EXISTS run_kinds CASCADE;
DROP TABLE IF EXISTS run_types CASCADE;
DROP TABLE IF EXISTS session_criteria CASCADE;
DROP TABLE IF EXISTS criteria CASCADE;
DROP TABLE IF EXISTS session_tools CASCADE;
DROP TABLE IF EXISTS sessions CASCADE;
DROP TABLE IF EXISTS session_statuses CASCADE;
DROP TABLE IF EXISTS language_pairs CASCADE;
DROP TABLE IF EXISTS languages CASCADE;
DROP TABLE IF EXISTS prompts CASCADE;
DROP TABLE IF EXISTS tool_roles CASCADE;
DROP TABLE IF EXISTS tools CASCADE;
DROP TABLE IF EXISTS vendors CASCADE;
DROP TABLE IF EXISTS vendor_kinds CASCADE;
DROP TABLE IF EXISTS vendor_types CASCADE;
DROP TABLE IF EXISTS segments CASCADE;
DROP TABLE IF EXISTS segmentations CASCADE;
DROP TABLE IF EXISTS segment_kinds CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS document_formats CASCADE;
DROP TABLE IF EXISTS users CASCADE;
