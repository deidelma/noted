BEGIN TRANSACTION;
DROP TABLE IF EXISTS "notes";
CREATE TABLE IF NOT EXISTS "notes" (
	"id"	INTEGER NOT NULL,
	"filename"	VARCHAR NOT NULL,
	"timestamp"	DATETIME NOT NULL,
	"body"	VARCHAR NOT NULL,
	PRIMARY KEY("id")
);
DROP TABLE IF EXISTS "keywords";
CREATE TABLE IF NOT EXISTS "keywords" (
	"id"	INTEGER NOT NULL,
	"name"	VARCHAR NOT NULL,
	PRIMARY KEY("id")
);
DROP TABLE IF EXISTS "present";
CREATE TABLE IF NOT EXISTS "present" (
	"id"	INTEGER NOT NULL,
	"name"	VARCHAR NOT NULL,
	PRIMARY KEY("id")
);
DROP TABLE IF EXISTS "speakers";
CREATE TABLE IF NOT EXISTS "speakers" (
	"id"	INTEGER NOT NULL,
	"name"	VARCHAR NOT NULL,
	PRIMARY KEY("id")
);
DROP TABLE IF EXISTS "notes_keywords";
CREATE TABLE IF NOT EXISTS "notes_keywords" (
	"note_id"	INTEGER NOT NULL,
	"meta_id"	INTEGER NOT NULL,
	FOREIGN KEY("meta_id") REFERENCES "keywords"("id"),
	FOREIGN KEY("note_id") REFERENCES "notes"("id"),
	PRIMARY KEY("note_id","meta_id")
);
DROP TABLE IF EXISTS "notes_present";
CREATE TABLE IF NOT EXISTS "notes_present" (
	"note_id"	INTEGER NOT NULL,
	"meta_id"	INTEGER NOT NULL,
	FOREIGN KEY("note_id") REFERENCES "notes"("id"),
	FOREIGN KEY("meta_id") REFERENCES "present"("id"),
	PRIMARY KEY("note_id","meta_id")
);
DROP TABLE IF EXISTS "notes_speakers";
CREATE TABLE IF NOT EXISTS "notes_speakers" (
	"note_id"	INTEGER NOT NULL,
	"meta_id"	INTEGER NOT NULL,
	FOREIGN KEY("note_id") REFERENCES "notes"("id"),
	FOREIGN KEY("meta_id") REFERENCES "speakers"("id"),
	PRIMARY KEY("note_id","meta_id")
);
DROP INDEX IF EXISTS "ix_notes_filename";
CREATE INDEX IF NOT EXISTS "ix_notes_filename" ON "notes" (
	"filename"
);
DROP INDEX IF EXISTS "ix_notes_timestamp";
CREATE INDEX IF NOT EXISTS "ix_notes_timestamp" ON "notes" (
	"timestamp"
);
DROP INDEX IF EXISTS "ix_keywords_name";
CREATE INDEX IF NOT EXISTS "ix_keywords_name" ON "keywords" (
	"name"
);
COMMIT;
