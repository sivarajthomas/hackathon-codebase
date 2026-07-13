-- =============================================================================
-- OneInvoice — Application schema + sample data (BigQuery)
-- =============================================================================
-- Supports: role-based login (customer + customer-support), mandatory invoice
-- context (no LLM discovery), response traceability/evidence, per-user chat
-- history with delete, and multi-session conversations.
--
-- WHERE THE DATASET NAMES COME FROM
--   The backend reads these settings (backend/app/config.py):
--       bigquery_project      -> ${PROJECT}       (env: BIGQUERY_PROJECT; defaults to gcp_project_id)
--       bigquery_dataset      -> ${DATASET}       (env: BIGQUERY_DATASET)      -- invoice / MCP data plane
--       bigquery_app_dataset  -> ${APP_DATASET}   (env: BIGQUERY_APP_DATASET)  -- auth / chat / audit
--
--   TWO datasets, ONE project:
--     * ${APP_DATASET}: users, user_roles, conversations, messages, audit_logs
--       -> kept OUT of the MCP data plane so the BigQuery MCP never sees them
--          (and secrets like users.password_hash are never browsable via MCP).
--     * ${DATASET}: invoice_metadata (invoice-relevant, co-located with the
--       existing invoice/shipment/contract tables the MCP reads).
--   If bigquery_app_dataset is left unset, the backend falls back to
--   bigquery_dataset (single-dataset dev); in that case set ${APP_DATASET} =
--   ${DATASET} below.
--
--   PowerShell one-liner to materialise a runnable file:
--       (Get-Content oneinvoice_app_schema.sql -Raw) `
--         -replace '\$\{PROJECT\}','my-gcp-project' `
--         -replace '\$\{APP_DATASET\}','oneinvoice_app' `
--         -replace '\$\{DATASET\}','oneinvoice_data' |
--         Set-Content oneinvoice_app_schema.ready.sql
--
-- The invoice_metadata / conversations / messages rows below are synced to the
-- CSV fixtures in sample_data/** (invoice_records, shipment_transactions,
-- contract_master, dispute_cases, credit_notes). All demo invoices belong to
-- contract LOG-CON-2026-001 (customer CUST-45872) — the only contract with
-- shipments in the sample data.
-- Demo password for every seeded user: Passw0rd!
-- =============================================================================


-- =============================================================================
-- 1. DDL
-- =============================================================================

-- 1.1 users -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `${PROJECT}.${APP_DATASET}.users` (
  user_id        STRING NOT NULL,          -- logical PK (UUID / handle)
  username       STRING NOT NULL,          -- login handle, unique (enforced in app)
  display_name   STRING,
  email          STRING,
  password_hash  STRING NOT NULL,          -- bcrypt; NEVER store plaintext
  primary_role   STRING NOT NULL,          -- 'CUSTOMER' | 'CUSTOMER_SUPPORT'
  contract_ids   ARRAY<STRING>,            -- row-level-security scope
  geo            STRING,
  currency       STRING,
  is_active      BOOL NOT NULL,
  created_at     TIMESTAMP NOT NULL,
  updated_at     TIMESTAMP
)
PARTITION BY DATE(created_at)
CLUSTER BY username
OPTIONS (description = 'Application users with hashed credentials and RLS scope.');

-- 1.2 user_roles --------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `${PROJECT}.${APP_DATASET}.user_roles` (
  user_id     STRING NOT NULL,
  role        STRING NOT NULL,             -- 'CUSTOMER' | 'CUSTOMER_SUPPORT'
  granted_by  STRING,
  granted_at  TIMESTAMP NOT NULL
)
CLUSTER BY role
OPTIONS (description = 'Role grants; supports future multi-role per user.');

-- 1.3 conversations -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `${PROJECT}.${APP_DATASET}.conversations` (
  conversation_id STRING NOT NULL,         -- logical PK (UUID)
  user_id         STRING NOT NULL,
  agent           STRING NOT NULL,         -- explain|resolve|simulate|prevent
  invoice_number  STRING NOT NULL,
  as_of_date      DATE,
  title           STRING,
  message_count   INT64 NOT NULL,
  is_deleted      BOOL NOT NULL,           -- soft delete (history delete support)
  created_at      TIMESTAMP NOT NULL,
  updated_at      TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY user_id, invoice_number
OPTIONS (description = 'Per-user multi-session conversations bound to an invoice + agent.');

-- 1.4 messages ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `${PROJECT}.${APP_DATASET}.messages` (
  message_id      STRING NOT NULL,         -- logical PK (UUID)
  conversation_id STRING NOT NULL,
  user_id         STRING NOT NULL,
  invoice_number  STRING NOT NULL,
  agent           STRING NOT NULL,
  role            STRING NOT NULL,         -- 'user' | 'assistant'
  question        STRING,                  -- populated for user turns
  response        STRING,                  -- populated for assistant turns
  evidence        JSON,                    -- array of EvidenceItem (traceability)
  trace_id        STRING,
  status          STRING,                  -- pipeline status
  created_at      TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY conversation_id
OPTIONS (description = 'Individual chat turns with structured evidence attribution.');

-- 1.5 invoice_metadata --------------------------------------------------------
-- Denormalised invoice context. The chat flow reads this by invoice_number to
-- eliminate LLM-based invoice discovery (the number is user-supplied + mandatory).
CREATE TABLE IF NOT EXISTS `${PROJECT}.${DATASET}.invoice_metadata` (
  invoice_number  STRING NOT NULL,         -- logical PK
  invoice_date    DATE,
  customer_id     STRING NOT NULL,
  contract_number STRING,
  shipment_ids    ARRAY<STRING>,
  status          STRING,                  -- e.g. BLOCKED, OPEN, PAID
  dispute_reason  STRING,
  currency        STRING,
  total_amount    NUMERIC,
  source_system   STRING,                  -- 'SAP' | 'BigQuery'
  last_updated    TIMESTAMP NOT NULL
)
PARTITION BY invoice_date
CLUSTER BY customer_id, contract_number
OPTIONS (description = 'Denormalised invoice context to eliminate LLM-based discovery.');

-- 1.6 audit_logs --------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `${PROJECT}.${APP_DATASET}.audit_logs` (
  audit_id       STRING NOT NULL,          -- logical PK (UUID)
  actor_user_id  STRING NOT NULL,
  actor_role     STRING,
  action         STRING NOT NULL,          -- LOGIN, CHAT, DELETE_CONVERSATION, REVIEW, ...
  subject_type   STRING,                   -- conversation|message|invoice|finding
  subject_id     STRING,
  invoice_number STRING,
  ip_address     STRING,
  detail         JSON,
  event_time     TIMESTAMP NOT NULL
)
PARTITION BY DATE(event_time)
CLUSTER BY actor_user_id, action
OPTIONS (description = 'Append-only security & compliance audit trail.');


-- =============================================================================
-- 2. Sample data  (synced with sample_data/** CSVs; password = 'Passw0rd!')
-- =============================================================================

-- 2.1 users : 5 customers + 3 customer-support ---------------------------------
-- Customer rows mirror contract_master.csv (CustomerName/Email/ContractNumber).
-- password_hash below is a real bcrypt hash of 'Passw0rd!' (rounds=12).
INSERT INTO `${PROJECT}.${APP_DATASET}.users`
(user_id, username, display_name, email, password_hash, primary_role, contract_ids, geo, currency, is_active, created_at, updated_at)
VALUES
('u-cust-001','acme',    'ABC Industrial Manufacturing Ltd','contact1@example.com','$2b$12$ezqI9vrcE41n2gjyXphp8.2NHERmhmgkegjJ7kzhZ24kK6x2Wy0f6','CUSTOMER',        ['LOG-CON-2026-001'],'IN','INR', TRUE, TIMESTAMP '2025-01-05 09:00:00 UTC', CURRENT_TIMESTAMP()),
('u-cust-002','globex',  'XYZ Retail Pvt Ltd',              'contact2@example.com','$2b$12$ezqI9vrcE41n2gjyXphp8.2NHERmhmgkegjJ7kzhZ24kK6x2Wy0f6','CUSTOMER',        ['LOG-CON-2026-002'],'IN','INR', TRUE, TIMESTAMP '2025-01-06 09:00:00 UTC', CURRENT_TIMESTAMP()),
('u-cust-003','initech', 'Global Pharma Ltd',               'contact3@example.com','$2b$12$ezqI9vrcE41n2gjyXphp8.2NHERmhmgkegjJ7kzhZ24kK6x2Wy0f6','CUSTOMER',        ['LOG-CON-2026-003'],'IN','INR', TRUE, TIMESTAMP '2025-01-06 10:00:00 UTC', CURRENT_TIMESTAMP()),
('u-cust-004','umbrella','Sunrise Electronics',             'contact4@example.com','$2b$12$ezqI9vrcE41n2gjyXphp8.2NHERmhmgkegjJ7kzhZ24kK6x2Wy0f6','CUSTOMER',        ['LOG-CON-2026-004'],'IN','INR', TRUE, TIMESTAMP '2025-01-07 11:00:00 UTC', CURRENT_TIMESTAMP()),
('u-cust-005','hooli',   'Titan Auto Components',           'contact5@example.com','$2b$12$ezqI9vrcE41n2gjyXphp8.2NHERmhmgkegjJ7kzhZ24kK6x2Wy0f6','CUSTOMER',        ['LOG-CON-2026-005'],'IN','INR', TRUE, TIMESTAMP '2025-01-08 08:30:00 UTC', CURRENT_TIMESTAMP()),
('u-sup-001', 'ssmith',  'Sarah Smith (CS)', 'sarah@oneinvoice.com','$2b$12$ezqI9vrcE41n2gjyXphp8.2NHERmhmgkegjJ7kzhZ24kK6x2Wy0f6','CUSTOMER_SUPPORT', [],                     'US','USD', TRUE, TIMESTAMP '2025-01-02 08:00:00 UTC', CURRENT_TIMESTAMP()),
('u-sup-002', 'rkumar',  'Rahul Kumar (CS)', 'rahul@oneinvoice.com','$2b$12$ezqI9vrcE41n2gjyXphp8.2NHERmhmgkegjJ7kzhZ24kK6x2Wy0f6','CUSTOMER_SUPPORT', [],                     'IN','INR', TRUE, TIMESTAMP '2025-01-02 08:05:00 UTC', CURRENT_TIMESTAMP()),
('u-sup-003', 'mgarcia', 'Maria Garcia (CS)','maria@oneinvoice.com','$2b$12$ezqI9vrcE41n2gjyXphp8.2NHERmhmgkegjJ7kzhZ24kK6x2Wy0f6','CUSTOMER_SUPPORT', [],                     'DE','EUR', TRUE, TIMESTAMP '2025-01-02 08:10:00 UTC', CURRENT_TIMESTAMP());

-- 2.2 user_roles --------------------------------------------------------------
INSERT INTO `${PROJECT}.${APP_DATASET}.user_roles` (user_id, role, granted_by, granted_at) VALUES
('u-cust-001','CUSTOMER','system',TIMESTAMP '2025-01-05 09:00:00 UTC'),
('u-cust-002','CUSTOMER','system',TIMESTAMP '2025-01-06 09:00:00 UTC'),
('u-cust-003','CUSTOMER','system',TIMESTAMP '2025-01-06 10:00:00 UTC'),
('u-cust-004','CUSTOMER','system',TIMESTAMP '2025-01-07 11:00:00 UTC'),
('u-cust-005','CUSTOMER','system',TIMESTAMP '2025-01-08 08:30:00 UTC'),
('u-sup-001','CUSTOMER_SUPPORT','system',TIMESTAMP '2025-01-02 08:00:00 UTC'),
('u-sup-002','CUSTOMER_SUPPORT','system',TIMESTAMP '2025-01-02 08:05:00 UTC'),
('u-sup-003','CUSTOMER_SUPPORT','system',TIMESTAMP '2025-01-02 08:10:00 UTC');

-- 2.3 invoice_metadata (synced with sample_data/** CSVs) -----------------------
-- Amounts/dates from invoice_records.csv; shipment + contract from
-- shipment_transactions.csv; dispute_reason from dispute_cases.csv.
INSERT INTO `${PROJECT}.${DATASET}.invoice_metadata`
(invoice_number, invoice_date, customer_id, contract_number, shipment_ids, status, dispute_reason, currency, total_amount, source_system, last_updated)
VALUES
('INV0001', DATE '2026-03-02','CUST-45872','LOG-CON-2026-001',['SHP0001'], 'OPEN',    NULL,                                 'INR', 39350.00,'BigQuery', TIMESTAMP '2026-03-02 00:00:00 UTC'),
('INV0004', DATE '2026-03-05','CUST-45872','LOG-CON-2026-001',['SHP0004'], 'BLOCKED', 'Duplicate fuel surcharge',           'INR', 39412.16,'BigQuery', TIMESTAMP '2026-03-05 00:00:00 UTC'),
('INV0011', DATE '2026-03-12','CUST-45872','LOG-CON-2026-001',['SHP0011'], 'PAID',    'Incorrect discount not applied',     'INR', 38196.56,'BigQuery', TIMESTAMP '2026-03-12 00:00:00 UTC'),
('INV0018', DATE '2026-03-19','CUST-45872','LOG-CON-2026-001',['SHP0018'], 'BLOCKED', 'Weight billed higher than shipped',  'INR', 48056.60,'BigQuery', TIMESTAMP '2026-03-19 00:00:00 UTC'),
('INV0032', DATE '2026-03-05','CUST-45872','LOG-CON-2026-001',['SHP0032'], 'PAID',    'Express charge on standard delivery','INR', 14965.76,'BigQuery', TIMESTAMP '2026-03-05 00:00:00 UTC');

-- 2.4 conversations (multiple sessions per user, multiple agents) --------------
INSERT INTO `${PROJECT}.${APP_DATASET}.conversations`
(conversation_id, user_id, agent, invoice_number, as_of_date, title, message_count, is_deleted, created_at, updated_at)
VALUES
('cv-001','u-cust-001','explain', 'INV0001', DATE '2026-03-02','Break down INV0001 charges', 2, FALSE, TIMESTAMP '2026-03-20 10:00:00 UTC', TIMESTAMP '2026-03-20 10:05:00 UTC'),
('cv-002','u-cust-001','simulate','INV0001', DATE '2026-03-02','What if Road instead of Air', 0, FALSE, TIMESTAMP '2026-03-21 14:00:00 UTC', TIMESTAMP '2026-03-21 14:03:00 UTC'),
('cv-003','u-cust-001','resolve', 'INV0011', DATE '2026-03-12','Missing contracted discount', 2, FALSE, TIMESTAMP '2026-03-22 09:30:00 UTC', TIMESTAMP '2026-03-22 09:34:00 UTC'),
('cv-004','u-sup-001', 'prevent', 'INV0004', DATE '2026-03-05','Why was INV0004 flagged',    2, FALSE, TIMESTAMP '2026-03-06 11:00:00 UTC', TIMESTAMP '2026-03-06 11:02:00 UTC');

-- 2.5 messages (question/response pairs; assistant turns carry evidence) --------
INSERT INTO `${PROJECT}.${APP_DATASET}.messages`
(message_id, conversation_id, user_id, invoice_number, agent, role, question, response, evidence, trace_id, status, created_at)
VALUES
('m-0001','cv-001','u-cust-001','INV0001','explain','user','Break down every charge on INV0001', NULL, NULL, 't-aaa', 'completed', TIMESTAMP '2026-03-20 10:00:00 UTC'),
('m-0002','cv-001','u-cust-001','INV0001','explain','assistant', NULL, 'INV0001 totals INR 39,350.00: freight INR 27,000.00, fuel surcharge INR 1,350.00, insurance INR 10,000.00, tax INR 1,000.00.',
  JSON '[{"source_object":"invoice_metadata","record_id":"INV0001","retrieved_fields":["total_amount","status","currency"],"confidence":100,"last_updated":"2026-03-02T00:00:00Z","source_system":"BigQuery","snippet":"total_amount=39350.00; status=OPEN; currency=INR","locator":"bq://invoice_metadata/INV0001"}]',
  't-aaa','completed', TIMESTAMP '2026-03-20 10:00:04 UTC'),
('m-0003','cv-003','u-cust-001','INV0011','resolve','user','Should the missing contracted discount on INV0011 be credited?', NULL, NULL, 't-bbb','completed', TIMESTAMP '2026-03-22 09:30:00 UTC'),
('m-0004','cv-003','u-cust-001','INV0011','resolve','assistant', NULL, 'Dispute DSP-0002 confirmed the contracted discount was not applied on INV0011. Credit note CN-0001 for INR 5,729.48 was issued on 2026-03-12 against contract LOG-CON-2026-001.',
  JSON '[{"source_object":"invoice_metadata","record_id":"INV0011","retrieved_fields":["contract_number","dispute_reason","total_amount"],"confidence":98,"last_updated":"2026-03-12T00:00:00Z","source_system":"BigQuery","snippet":"contract_number=LOG-CON-2026-001; dispute_reason=Incorrect discount not applied","locator":"bq://invoice_metadata/INV0011"},{"source_object":"dispute_cases","record_id":"DSP-0002","retrieved_fields":["Status","CreditNoteAmount","ResolvedDate"],"confidence":100,"last_updated":"2026-03-12T00:00:00Z","source_system":"BigQuery","snippet":"Status=RESOLVED; CreditNoteAmount=5729.48; CreditNoteID=CN-0001","locator":"bq://dispute_cases/DSP-0002"}]',
  't-bbb','completed', TIMESTAMP '2026-03-22 09:34:00 UTC'),
('m-0005','cv-004','u-sup-001','INV0004','prevent','user','Why was INV0004 flagged?', NULL, NULL, 't-ccc','completed', TIMESTAMP '2026-03-06 11:00:00 UTC'),
('m-0006','cv-004','u-sup-001','INV0004','prevent','assistant', NULL, 'INV0004 is blocked under dispute DSP-0001 for a duplicate fuel surcharge; INR 5,911.82 is disputed and the case is UNDER_REVIEW pending reversal of the duplicate charge.',
  JSON '[{"source_object":"invoice_metadata","record_id":"INV0004","retrieved_fields":["status","dispute_reason"],"confidence":100,"last_updated":"2026-03-05T00:00:00Z","source_system":"BigQuery","snippet":"status=BLOCKED; dispute_reason=Duplicate fuel surcharge","locator":"bq://invoice_metadata/INV0004"},{"source_object":"dispute_cases","record_id":"DSP-0001","retrieved_fields":["ClaimType","DisputedAmount","Status"],"confidence":100,"last_updated":"2026-03-05T00:00:00Z","source_system":"BigQuery","snippet":"ClaimType=Duplicate Charge; DisputedAmount=5911.82; Status=UNDER_REVIEW","locator":"bq://dispute_cases/DSP-0001"}]',
  't-ccc','completed', TIMESTAMP '2026-03-06 11:02:00 UTC');

-- 2.6 audit_logs ---------------------------------------------------------------
INSERT INTO `${PROJECT}.${APP_DATASET}.audit_logs`
(audit_id, actor_user_id, actor_role, action, subject_type, subject_id, invoice_number, ip_address, detail, event_time)
VALUES
('a-0001','u-cust-001','CUSTOMER','LOGIN', NULL, NULL, NULL,'203.0.113.10', JSON '{"ua":"Chrome"}', TIMESTAMP '2026-03-20 09:59:00 UTC'),
('a-0002','u-cust-001','CUSTOMER','CHAT','message','m-0002','INV0001','203.0.113.10', JSON '{"agent":"explain"}', TIMESTAMP '2026-03-20 10:00:04 UTC'),
('a-0003','u-sup-001', 'CUSTOMER_SUPPORT','CHAT','message','m-0006','INV0004','198.51.100.7', JSON '{"agent":"prevent"}', TIMESTAMP '2026-03-06 11:02:00 UTC'),
('a-0004','u-cust-002','CUSTOMER','DELETE_CONVERSATION','conversation','cv-999', NULL,'203.0.113.55', JSON '{"reason":"user requested"}', TIMESTAMP '2026-03-23 08:00:00 UTC');
