-- Series 76 schema. Idempotent: safe to run on every startup. Postgres 16, no extensions.
-- Identifiers are lowercase snake_case so they never need quoting.

-- One row per source table in the PDF: title plus the footnotes kept as section metadata.
CREATE TABLE IF NOT EXISTS catalog_tables (
    table_id text PRIMARY KEY,
    title    text NOT NULL,
    notes    jsonb NOT NULL DEFAULT '[]'
);

-- One row per part number. Typed columns (not a JSON blob) because the
-- recommendation filters (torque, voltage, enclosure, ...) run in SQL.
-- Columns mirror the pydantic Actuator model.
CREATE TABLE IF NOT EXISTS actuators (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    part_number   text NOT NULL UNIQUE,  -- natural key; UNIQUE is the upsert conflict target
    table_id      text NOT NULL REFERENCES catalog_tables (table_id),
    csa_certified boolean NOT NULL DEFAULT true,  -- false for part numbers printed with '/A*'
    enclosure     text NOT NULL CHECK (enclosure IN ('weatherproof', 'explosionproof')),
    certifications text NOT NULL,
    voltage       text NOT NULL,         -- as printed: '110V', '220V', '24V AC/DC', '24V DC'
    current_type  text NOT NULL CHECK (current_type IN ('AC', 'DC', 'AC/DC')),
    phase         smallint CHECK (phase IN (1, 3)),  -- NULL for 24V tables
    service       text NOT NULL CHECK (service IN
                    ('on_off_and_modulating', 'on_off', 'modulating', 'unspecified')),

    -- Measurements are numeric (exact decimals, as printed), never float. All nullable:
    -- N/A rows and tables lacking a column (e.g. no 50 Hz in 24V) store NULL.
    onoff_torque_in_lbs  numeric,
    onoff_torque_nm      numeric,
    onoff_duty_cycle_pct numeric CHECK (onoff_duty_cycle_pct BETWEEN 0 AND 100),
    cycles_per_hour      numeric,
    mod_torque_in_lbs    numeric,
    mod_torque_nm        numeric,
    mod_duty_cycle_pct   numeric CHECK (mod_duty_cycle_pct BETWEEN 0 AND 100),
    starts_per_hour      numeric,
    output_torque_in_lbs numeric,
    output_torque_nm     numeric,
    duty_cycle_pct       numeric CHECK (duty_cycle_pct BETWEEN 0 AND 100),
    speed_sec_60hz       numeric,
    speed_sec_50hz       numeric,
    speed_sec            numeric,
    fla_60hz_a           numeric,
    fla_50hz_a           numeric,
    fla_a                numeric,
    lra_60hz_a           numeric,
    lra_50hz_a           numeric,
    lra_a                numeric,
    motor_power_w        numeric,

    row_index  integer,                  -- position within the source table
    -- false for the N/A rows. Derived by Postgres from the 21 measurement columns,
    -- so it can never drift from them (a partial UPDATE recomputes it).
    has_data   boolean GENERATED ALWAYS AS (num_nonnulls(
                   onoff_torque_in_lbs, onoff_torque_nm, onoff_duty_cycle_pct, cycles_per_hour,
                   mod_torque_in_lbs, mod_torque_nm, mod_duty_cycle_pct, starts_per_hour,
                   output_torque_in_lbs, output_torque_nm, duty_cycle_pct,
                   speed_sec_60hz, speed_sec_50hz, speed_sec,
                   fla_60hz_a, fla_50hz_a, fla_a, lra_60hz_a, lra_50hz_a, lra_a,
                   motor_power_w) > 0) STORED,
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Planned search filter: voltage + enclosure + service (equality, in this order).
CREATE INDEX IF NOT EXISTS actuators_voltage_enclosure_service_idx
    ON actuators (voltage, enclosure, service);
-- Prefix search (LIKE '764%'); a plain btree cannot serve LIKE unless the DB uses the C collation.
CREATE INDEX IF NOT EXISTS actuators_part_number_prefix_idx
    ON actuators (part_number text_pattern_ops);
-- FK index (Postgres does not create one automatically).
CREATE INDEX IF NOT EXISTS actuators_table_id_idx ON actuators (table_id);

CREATE TABLE IF NOT EXISTS sessions (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),  -- built in since PG13
    user_id    text,                     -- NULL until login exists
    title      text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
-- "Recent conversations" listing, optionally per user.
CREATE INDEX IF NOT EXISTS sessions_updated_at_idx ON sessions (updated_at DESC);
CREATE INDEX IF NOT EXISTS sessions_user_updated_idx ON sessions (user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES sessions (id) ON DELETE CASCADE,
    role       text NOT NULL CHECK (role IN ('user', 'assistant')),
    content    text NOT NULL,
    products   jsonb NOT NULL DEFAULT '[]',  -- structured product data shown by the app
    trace      jsonb NOT NULL DEFAULT '[]',  -- tool-call trace for the Debug screen
    created_at timestamptz NOT NULL DEFAULT now()
);
-- Serves the FK (cascade deletes, joins) and loading a conversation in order.
CREATE INDEX IF NOT EXISTS messages_session_created_idx ON messages (session_id, created_at);

-- ---------------------------------------------------------------------------
-- Sprint 8: login (D-43) and per-session turn lock (D-46). Idempotent like the rest.

-- Test users are seeded by app.auth.seed at startup (never plain-text passwords).
-- id is text (a UUID string) so it matches sessions.user_id, which has been text since Sprint 4.
CREATE TABLE IF NOT EXISTS users (
    id            text PRIMARY KEY DEFAULT gen_random_uuid()::text,
    email         text NOT NULL UNIQUE CHECK (email = lower(email)),
    password_hash text NOT NULL,          -- argon2 (pwdlib); never the password
    role          text NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'developer')),
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- Opaque bearer tokens: only the SHA-256 of the token is stored, so a DB dump
-- cannot be replayed. Deleting a row is logout; expired rows are ignored.
CREATE TABLE IF NOT EXISTS auth_tokens (
    token_hash text PRIMARY KEY,          -- hex sha256 of the token the client holds
    user_id    text NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS auth_tokens_user_id_idx ON auth_tokens (user_id);

-- Sessions created before login have user_id NULL and stay invisible to every user.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'sessions_user_id_fkey') THEN
        ALTER TABLE sessions ADD CONSTRAINT sessions_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE;
    END IF;
END $$;

-- Turn lock (D-46): set while a turn runs, cleared in `finally`; stale after 2 minutes.
-- A column instead of an advisory lock so no connection is held during the LLM call (D-32).
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS busy_since timestamptz;
