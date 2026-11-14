-- Translator interview: the whole schema, thirty-one tables (AB#300).
--
-- The main version of this schema is the owner's draw.io file. The wiki page
-- "Translator interview diagrams" follows it and explains every rule below.
--
-- Two rules shape the whole file:
--   Nothing is overwritten. A new cut, a new run, a new score is a new row.
--   Every enumeration is a reference table, never a string in the row that
--   uses it. Reference tables all look the same: id, name, description,
--   comment, created_at.
--
-- Deletion follows the document. Deleting a document takes its cuts,
-- segments, sessions, runs, outputs, findings and scores with it, because a
-- visitor who asks for their data to be gone means all of it. Payments are
-- the exception: the rows stay for accounting with their session links set
-- to null, so money is still countable and no text survives.

-- There is no BEGIN or COMMIT here on purpose: Alembic runs the whole
-- revision in one transaction, and a second one nested inside would fight it.

-- ---------------------------------------------------------------- people --

CREATE TABLE users (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    google_sub  text NOT NULL UNIQUE,
    email       text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------- documents --

CREATE TABLE document_formats (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL UNIQUE,
    description text NOT NULL DEFAULT '',
    comment     text NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE documents (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    format_id   uuid NOT NULL REFERENCES document_formats (id),
    file_name   text NOT NULL,
    mime_type   text NOT NULL,
    file_bytes  bytea NOT NULL,
    size_bytes  integer NOT NULL CHECK (size_bytes >= 0),
    sha256      text NOT NULL,
    char_count  integer NOT NULL CHECK (char_count >= 0),
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX documents_user_id_idx ON documents (user_id);

-- ---------------------------------------------------------------- pieces --

CREATE TABLE segment_kinds (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL UNIQUE,
    description text NOT NULL DEFAULT '',
    comment     text NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- One cut of one document by one tool. version is the ordinal of the cut
-- inside its document: 1, 2, 3.
CREATE TABLE segmentations (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    tool_id     uuid NOT NULL,
    version     integer NOT NULL CHECK (version > 0),
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, version)
);

-- position is the ordinal of the piece through the whole cut, unique inside
-- it. struct_code is an address inside the document, such as S2-p3, and is
-- not a key.
CREATE TABLE segments (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    segmentation_id uuid NOT NULL
                    REFERENCES segmentations (id) ON DELETE CASCADE,
    struct_code     text NOT NULL,
    segment_kind_id uuid NOT NULL REFERENCES segment_kinds (id),
    position        integer NOT NULL CHECK (position > 0),
    content         text NOT NULL,
    UNIQUE (segmentation_id, position)
);

CREATE INDEX segments_segmentation_id_idx ON segments (segmentation_id);

-- ----------------------------------------------------------------- tools --

CREATE TABLE vendor_types (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL UNIQUE,
    description text NOT NULL DEFAULT '',
    comment     text NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE vendor_kinds (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_type_id uuid NOT NULL REFERENCES vendor_types (id),
    name           text NOT NULL UNIQUE,
    description    text NOT NULL DEFAULT '',
    comment        text NOT NULL DEFAULT '',
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE vendors (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_kind_id uuid NOT NULL REFERENCES vendor_kinds (id),
    name           text NOT NULL UNIQUE,
    description    text NOT NULL DEFAULT '',
    comment        text NOT NULL DEFAULT '',
    created_at     timestamptz NOT NULL DEFAULT now()
);

-- One exact tool. A row never changes: a new model version or a new effort
-- level is a new row, so an old run always points at what really ran.
CREATE TABLE tools (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id      uuid NOT NULL REFERENCES vendors (id),
    model          text NOT NULL,
    version        text NOT NULL,
    effort         text NOT NULL DEFAULT '',
    price_in_usd   numeric(12, 6) NOT NULL DEFAULT 0
                   CHECK (price_in_usd >= 0),
    price_out_usd  numeric(12, 6) NOT NULL DEFAULT 0
                   CHECK (price_out_usd >= 0),
    created_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (vendor_id, model, version, effort)
);

ALTER TABLE segmentations
    ADD CONSTRAINT segmentations_tool_id_fkey
    FOREIGN KEY (tool_id) REFERENCES tools (id);

CREATE TABLE tool_roles (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL UNIQUE,
    description text NOT NULL DEFAULT '',
    comment     text NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- The method is the prompts, so the prompts are stored. A row is never
-- edited: a changed template is a new row with the next version for its
-- role. The link is to the role, not to the run kind, because a judge gets
-- the same prompt in a calibrate run as in a judge run.
CREATE TABLE prompts (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id     uuid NOT NULL REFERENCES tool_roles (id),
    version     integer NOT NULL CHECK (version > 0),
    text        text NOT NULL,
    description text NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (role_id, version)
);

-- ------------------------------------------------------------- languages --

CREATE TABLE languages (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code        text NOT NULL UNIQUE,
    name        text NOT NULL,
    description text NOT NULL DEFAULT '',
    comment     text NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Not a list of what is offered: every language is offered. This is the
-- record of which pairs have been benchmarked and when. Empty at launch, so
-- every pair reads as not benchmarked. A repeated benchmark is a new row,
-- which is why the pair itself is not unique.
CREATE TABLE language_pairs (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_language_id uuid NOT NULL REFERENCES languages (id),
    target_language_id uuid NOT NULL REFERENCES languages (id),
    benchmarked_at     timestamptz,
    description        text NOT NULL DEFAULT '',
    created_at         timestamptz NOT NULL DEFAULT now(),
    CHECK (source_language_id <> target_language_id)
);

-- ------------------------------------------------------------- sessions --

CREATE TABLE session_statuses (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL UNIQUE,
    description text NOT NULL DEFAULT '',
    comment     text NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- A session hangs on one cut, not on a document: the document is read
-- through the cut, so there is no second copy of that fact to drift.
CREATE TABLE sessions (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    segmentation_id    uuid NOT NULL
                       REFERENCES segmentations (id) ON DELETE CASCADE,
    source_language_id uuid NOT NULL REFERENCES languages (id),
    target_language_id uuid NOT NULL REFERENCES languages (id),
    status_id          uuid NOT NULL REFERENCES session_statuses (id),
    report_opened_at   timestamptz,
    pay_clicked_at     timestamptz,
    created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX sessions_user_id_idx ON sessions (user_id);
CREATE INDEX sessions_segmentation_id_idx ON sessions (segmentation_id);

-- The set of tools is frozen here at the start of the session. The blind
-- code is the only name a model ever sees, and it is dealt per session, so
-- M2 is not the same model twice.
CREATE TABLE session_tools (
    session_id uuid NOT NULL REFERENCES sessions (id) ON DELETE CASCADE,
    tool_id    uuid NOT NULL REFERENCES tools (id),
    role_id    uuid NOT NULL REFERENCES tool_roles (id),
    blind_code text NOT NULL,
    PRIMARY KEY (session_id, tool_id, role_id),
    UNIQUE (session_id, blind_code)
);

CREATE TABLE criteria (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL UNIQUE,
    description text NOT NULL DEFAULT '',
    comment     text NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- The criteria are frozen the same way the tools are, so an old session
-- still shows what it was judged on after the list changes.
CREATE TABLE session_criteria (
    session_id   uuid NOT NULL REFERENCES sessions (id) ON DELETE CASCADE,
    criterion_id uuid NOT NULL REFERENCES criteria (id),
    PRIMARY KEY (session_id, criterion_id)
);

-- ------------------------------------------------------------------ runs --

CREATE TABLE run_types (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL UNIQUE,
    description text NOT NULL DEFAULT '',
    comment     text NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE run_kinds (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_type_id uuid NOT NULL REFERENCES run_types (id),
    name        text NOT NULL UNIQUE,
    description text NOT NULL DEFAULT '',
    comment     text NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE run_statuses (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL UNIQUE,
    description text NOT NULL DEFAULT '',
    comment     text NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- One tool doing one job. request and response keep the exact exchange;
-- prompt_id names the template version behind it, and is empty for a script
-- run, which has no prompt. A run is queued before the tool is called, so
-- started_at is empty while the row already exists. A failed run keeps its
-- row and the repeat is a new run.
CREATE TABLE runs (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   uuid NOT NULL REFERENCES sessions (id) ON DELETE CASCADE,
    tool_id      uuid NOT NULL REFERENCES tools (id),
    role_id      uuid NOT NULL REFERENCES tool_roles (id),
    prompt_id    uuid REFERENCES prompts (id),
    input_run_id uuid REFERENCES runs (id) ON DELETE CASCADE,
    run_kind_id  uuid NOT NULL REFERENCES run_kinds (id),
    round        integer NOT NULL DEFAULT 1 CHECK (round > 0),
    status_id    uuid NOT NULL REFERENCES run_statuses (id),
    request      jsonb,
    response     jsonb,
    tokens_in    integer CHECK (tokens_in >= 0),
    tokens_out   integer CHECK (tokens_out >= 0),
    cost_usd     numeric(12, 6) CHECK (cost_usd >= 0),
    latency_ms   integer CHECK (latency_ms >= 0),
    started_at   timestamptz,
    finished_at  timestamptz,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX runs_session_id_idx ON runs (session_id);
CREATE INDEX runs_input_run_id_idx ON runs (input_run_id);

-- Not a copy of the segments: the text one run produced for one segment.
-- Two translators give two rows with the same segment_id, which is what
-- puts them side by side on screen.
CREATE TABLE run_outputs (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id     uuid NOT NULL REFERENCES runs (id) ON DELETE CASCADE,
    segment_id uuid NOT NULL REFERENCES segments (id) ON DELETE CASCADE,
    content    text NOT NULL,
    UNIQUE (run_id, segment_id)
);

CREATE INDEX run_outputs_segment_id_idx ON run_outputs (segment_id);

-- ------------------------------------------------- findings and scores --

CREATE TABLE finding_kinds (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL UNIQUE,
    description text NOT NULL DEFAULT '',
    comment     text NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- judge_run_id is the run that made the remark, a judge or a checking
-- script. target_run_id is the run whose output was judged. The code checks
-- that the first is of type evaluation and the second of type translation.
CREATE TABLE findings (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    judge_run_id  uuid NOT NULL REFERENCES runs (id) ON DELETE CASCADE,
    target_run_id uuid NOT NULL REFERENCES runs (id) ON DELETE CASCADE,
    segment_id    uuid NOT NULL REFERENCES segments (id) ON DELETE CASCADE,
    kind_id       uuid NOT NULL REFERENCES finding_kinds (id),
    detail        jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX findings_target_run_id_idx ON findings (target_run_id);
CREATE INDEX findings_segment_id_idx ON findings (segment_id);

-- One number per judge run, per translation run, per criterion, with the
-- judge's own reason. A second judging is a new judge run with its own
-- rows; the old rows stay.
CREATE TABLE scores (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    judge_run_id  uuid NOT NULL REFERENCES runs (id) ON DELETE CASCADE,
    target_run_id uuid NOT NULL REFERENCES runs (id) ON DELETE CASCADE,
    criterion_id  uuid NOT NULL REFERENCES criteria (id),
    score         integer NOT NULL CHECK (score BETWEEN 0 AND 10),
    rationale     text NOT NULL DEFAULT '',
    UNIQUE (judge_run_id, target_run_id, criterion_id)
);

CREATE INDEX scores_target_run_id_idx ON scores (target_run_id);

-- -------------------------------------------------------------- payments --

CREATE TABLE payment_provider_kinds (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL UNIQUE,
    description text NOT NULL DEFAULT '',
    comment     text NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE payment_providers (
    id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name    text NOT NULL UNIQUE,
    kind_id uuid NOT NULL REFERENCES payment_provider_kinds (id)
);

CREATE TABLE payment_statuses (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL UNIQUE,
    description text NOT NULL DEFAULT '',
    comment     text NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- One payment unlocks two things: the full report of an existing session,
-- and one new session. There is no is_paid flag anywhere; a session is paid
-- when a successful payment points at it from either column.
--
-- provider_payment_id is the provider's own id for this payment, not ours,
-- and it is unique so the same callback arriving twice cannot grant two
-- sessions. amount_usd is what was charged, received_usd what landed after
-- the fee. The session links are set to null when a session is deleted, so
-- the money stays countable and no text survives.
CREATE TABLE payments (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    provider_id         uuid NOT NULL REFERENCES payment_providers (id),
    unlocked_session_id uuid REFERENCES sessions (id) ON DELETE SET NULL,
    granted_session_id  uuid REFERENCES sessions (id) ON DELETE SET NULL,
    provider_payment_id text NOT NULL UNIQUE,
    amount_usd          numeric(12, 2) NOT NULL CHECK (amount_usd >= 0),
    received_usd        numeric(12, 2) CHECK (received_usd >= 0),
    status_id           uuid NOT NULL REFERENCES payment_statuses (id),
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX payments_user_id_idx ON payments (user_id);
CREATE INDEX payments_unlocked_session_id_idx
    ON payments (unlocked_session_id);
CREATE INDEX payments_granted_session_id_idx ON payments (granted_session_id);
