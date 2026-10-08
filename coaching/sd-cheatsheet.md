# SD Cheatsheet

Overview first; detail per topic below. Same content as the artifact (https://claude.ai/artifact/5XwCVWZiWpnrE7PZEtcwwB). Orders of magnitude, not benchmarks.

## Overview

**Fintech**
- Invariant: balance ≥ 0 · entries per transfer sum to 0
- Lock: `UPDATE accounts SET balance = balance - x WHERE id = ? AND balance >= x`
- Idempotency: `UNIQUE(user_id, idempotency_key)`
- Shard: `user_id` · cell per legal entity

**Booking**
- Invariant: booked ≤ total, every night
- Hold: `SET booked = booked + 1 WHERE … AND booked < total` (rows = nights)
- Timer race: `UPDATE … SET status = 'confirmed' WHERE status = 'held'`
- Shard: `hotel_id` / `screening_id`

**Stock**
- Invariant: 0 ≤ available ≤ quantity
- Counters: hold **avail −** · paid **qty −** · fail/expire **avail +** · restock **both +**
- Lock: order row first, then SKUs in `sku_id` order
- Shard: none at ~200 WPS · `warehouse_id`

**Outbox**
- Write: state + outbox row in **one tx**
- Relay: `FOR UPDATE SKIP LOCKED` → publish → mark sent
- Consumer: dedupe on `event_id` PK
- Kafka key: `aggregate_id` (per-entity order)

**Tech limits**
- Postgres: writes 2K easy · 10K max · reads 10–50K · 5–30 TB
- Redis: 100–200K ops/s · <1 ms · RAM
- Kafka: 100K–1M msg/s per broker
- SQS: Standard ∞ · FIFO 300/s
- S3: ∞ · $23/TB-mo · Glacier Deep $1/TB-mo, 12 h

**Latency**
- Same AZ: 0.5 ms · cross-AZ 1–2 ms
- EU ↔ EU: 15–30 ms
- EU ↔ US: 70–100 ms · EU ↔ Asia 150–250
- Rates: 1M/day ≈ 12/s · peak × 2–5
- SLA: 99.9% ≈ 8.7 h/yr · 99.99% ≈ 53 min/yr

**Legal**
- KYC: verify identity at onboarding
- AML: monitor transactions · keep 5 years
- PCI DSS: card data → tokenise
- GDPR: personal-data rights · breach 72 h
- SCC: contract for data leaving the EEA

**Encryption**
- Transit: TLS edge · mTLS internal
- Disk: KMS-managed (TDE / SSE-KMS)
- Fields: envelope: DEK per record, KEK in KMS
- Lookup: HMAC blind index
- Erase: crypto-shredding (per-user key)

---

## Fintech

### Fintech · P2P transfer / wallet ledger

Invariant: balance never below 0, and every transfer's entries sum to 0. Amounts are integers in minor units (cents), never floats.

**Schema**

```sql
accounts(
  id          uuid PK,
  user_id     uuid NOT NULL,
  currency    char(3) NOT NULL,
  balance     bigint NOT NULL CHECK (balance >= 0)  -- minor units
)

transfers(
  id              uuid PK,
  user_id         uuid NOT NULL,
  idempotency_key text NOT NULL,
  from_account    uuid, to_account uuid,
  amount          bigint CHECK (amount > 0),
  currency        char(3),
  status          text  -- pending | completed | failed
  created_at      timestamptz,
  UNIQUE (user_id, idempotency_key)   -- "unique within what?" → per user
)

ledger_entries(            -- append-only, double entry
  id          bigserial PK,
  transfer_id uuid NOT NULL,
  account_id  uuid NOT NULL,
  amount      bigint NOT NULL,      -- −debit / +credit, sum per transfer = 0
  created_at  timestamptz,
  UNIQUE (transfer_id, account_id)
)
-- index: ledger_entries(account_id, created_at DESC)  → statement / history
```

**Transfer: one transaction, same shard**

```sql
BEGIN;
INSERT INTO transfers (id, user_id, idempotency_key, from_account,
                       to_account, amount, currency, status)
VALUES (:id, :user, :key, :a, :b, :amt, 'EUR', 'pending')
ON CONFLICT (user_id, idempotency_key) DO NOTHING
RETURNING id;              -- 0 rows → retry: return the stored result

SELECT id FROM accounts WHERE id IN (:a, :b)
ORDER BY id FOR UPDATE;       -- fixed lock order → no deadlocks

UPDATE accounts SET balance = balance - :amt
WHERE id = :a AND balance >= :amt;   -- 0 rows → insufficient → ROLLBACK
UPDATE accounts SET balance = balance + :amt WHERE id = :b;

INSERT INTO ledger_entries (transfer_id, account_id, amount)
VALUES (:id, :a, -:amt), (:id, :b, :amt);
UPDATE transfers SET status = 'completed' WHERE id = :id;
INSERT INTO outbox (...) VALUES (... 'TransferCompleted' ...);
COMMIT;
```

- **Shard / partition key**: `user_id` (accounts and ledger live with their owner). Globally: a **cell per legal entity**, and the user's home cell owns their rows.
- **Cross-shard transfer**: Debit + outbox in shard A → relay → shard B: `INSERT inbound_transfers(transfer_id PK)` as dedupe + credit + ack. Compensate (refund A) only on a definitive "rejected", never on a timeout.
- **External provider (withdrawal)**: Persist `status='pending'` + the hold first, then call the provider with `transfer_id` as its idempotency key. A status checker resolves timeouts.
---

## Booking

### Booking · hotel room-nights (counted inventory) + seats variant

Invariant: booked ≤ total for every night of the stay. The hold expires after N minutes unless it's confirmed.

**Schema**

```sql
room_inventory(                 -- one row per hotel × room type × night
  hotel_id     uuid,
  room_type_id uuid,
  night        date,
  total        int NOT NULL,
  booked       int NOT NULL DEFAULT 0,
  PRIMARY KEY (hotel_id, room_type_id, night),
  CHECK (booked >= 0 AND booked <= total)
)

bookings(
  id           uuid PK,            -- client-generated = idempotency key
  user_id      uuid NOT NULL,
  hotel_id     uuid NOT NULL,
  room_type_id uuid NOT NULL,
  check_in date, check_out date,
  status       text,               -- held | confirmed | cancelled | expired
  held_until   timestamptz,
  created_at   timestamptz
)
-- index: bookings(held_until) WHERE status = 'held'   (partial, for the expiry worker)
-- index: bookings(user_id, created_at DESC)           ("my bookings")
```

**Hold · confirm · expire**

```sql
-- HOLD (one tx)
INSERT INTO bookings (id, ..., status, held_until)
VALUES (:id, ..., 'held', now() + interval '15 min')
ON CONFLICT (id) DO NOTHING;           -- retry → return existing

UPDATE room_inventory SET booked = booked + 1
WHERE hotel_id = :h AND room_type_id = :rt
  AND night >= :in AND night < :out
  AND booked < total;                 -- rows updated ≠ nights → ROLLBACK

-- CONFIRM (payment ok) — the row count decides the timer race
UPDATE bookings SET status = 'confirmed'
WHERE id = :id AND status = 'held';    -- 0 rows → expired: re-hold or refund

-- EXPIRE (worker, scaled out safely)
UPDATE bookings SET status = 'expired'
WHERE id IN (SELECT id FROM bookings
             WHERE status = 'held' AND held_until < now()
             LIMIT 100 FOR UPDATE SKIP LOCKED)
RETURNING id;   -- then booked = booked - 1 for those nights, same tx
```

**Variant · specific seats (cinema, flight)**

```sql
seats(screening_id, seat_id, status, hold_id, held_until,
      PRIMARY KEY (screening_id, seat_id))

UPDATE seats SET status = 'held', hold_id = :h,
       held_until = now() + interval '10 min'
WHERE screening_id = :s AND seat_id = ANY(:ids)
  AND (status = 'free' OR (status = 'held' AND held_until < now()))
RETURNING seat_id;          -- count ≠ len(:ids) → ROLLBACK (all or nothing)
```

**Variant · time ranges (meeting rooms, rentals)**

```sql
reservations(id, room_id, during tstzrange, status,
  EXCLUDE USING gist (room_id WITH =, during WITH &&)
  WHERE (status <> 'cancelled'))
-- the DB rejects overlapping bookings: no lock code needed,
-- the INSERT fails with exclusion_violation (23P01)
```

- **Shard / partition key**: `hotel_id` (or `screening_id`, `room_id`). Inventory and its bookings stay together, so the hold is single-shard. "My bookings" is served by a per-user projection.
- **Hot key**: A premiere or a popular hotel night is one row. Keep the transactions short, use `NOWAIT` to fail fast, or put a waiting room / queue per event in front of it.
- **Search**: Availability search is read-heavy: a cache or search index over inventory, stale by seconds is fine. The hold on the primary is authoritative.
---

## Stock

### Stock · online shop (sd-22 model, corrected)

Invariant: 0 ≤ available ≤ quantity. `quantity` = units physically in the warehouse; `available` = units free to hold.

**Schema**

```sql
skus(
  id        uuid PK,
  quantity  int NOT NULL,
  available int NOT NULL,
  CHECK (available >= 0 AND available <= quantity)
)

orders(
  id         uuid PK,          -- checkout service's order id = idempotency key
  status     text,             -- reserved | completed | failed | expired
  created_at timestamptz,
  expires_at timestamptz
)
-- index: orders(expires_at) WHERE status = 'reserved'

order_lines(
  order_id uuid REFERENCES orders,
  sku_id   uuid REFERENCES skus,
  amount   int CHECK (amount > 0),
  PRIMARY KEY (order_id, sku_id)
)

payment_results(
  payment_result_id text PK,  -- callback dedupe
  order_id uuid, outcome text, received_at timestamptz
)
```

**Counter walk: every transition**

```sql
-- HOLD (one tx, lines sorted by sku_id)
INSERT INTO orders (id, status, expires_at)
VALUES (:id, 'reserved', now() + interval '15 min')
ON CONFLICT (id) DO NOTHING;     -- 0 rows → return original response
UPDATE skus SET available = available - :n
WHERE id = :sku AND available >= :n;  -- per line; 0 rows → ROLLBACK

-- PAYMENT SUCCESS
INSERT INTO payment_results ... ON CONFLICT DO NOTHING; -- dup → stop
UPDATE orders SET status = 'completed'
WHERE id = :id AND status = 'reserved';  -- order row first; 0 rows → late path
UPDATE skus SET quantity = quantity - :n WHERE id = :sku;

-- PAYMENT FAILED / EXPIRED (worker uses SKIP LOCKED)
UPDATE orders SET status = 'failed' WHERE id = :id AND status = 'reserved';
UPDATE skus SET available = available + :n WHERE id = :sku;

-- LATE SUCCESS after expiry: try the HOLD again; if 0 rows → tell checkout "refund"

-- STAFF ADDS STOCK
UPDATE skus SET quantity = quantity + :n, available = available + :n
WHERE id = :sku;
```

- **Shard / partition key**: At ~200 holds/s: **don't shard**, one primary + standby. With several warehouses: `warehouse_id`. Only if forced: `sku_id`, but then multi-line orders cross shards (per-shard holds + saga with persisted state).
- **Read path**: Product page → cache of `available` per SKU (TTL ~1 s or invalidate on change). Stale is fine for display; the hold is authoritative.
- **Hot SKU (flash sale)**: One row ≈ hundreds of updates/s. Split into N sub-counters (`sku_id, bucket`), or queue the holds for that SKU, or use a waiting room.
---

## Outbox

### Transactional outbox + idempotent consumer

Never write "DB + queue atomically". Write the event row in the same transaction as the state change, and a relay publishes it at-least-once.

**Schema (same DB / shard as the aggregate)**

```sql
outbox(
  id             bigserial PK,
  event_id       uuid UNIQUE NOT NULL,    -- consumers dedupe on this
  aggregate_type text,                    -- 'transfer', 'order', ...
  aggregate_id   uuid NOT NULL,           -- = Kafka message key
  event_type     text,
  payload        jsonb,
  created_at     timestamptz DEFAULT now(),
  published_at   timestamptz              -- NULL = pending
)
-- index: outbox(id) WHERE published_at IS NULL   (partial)
-- cleanup: partition by day, drop old partitions

processed_events(              -- consumer side ("inbox")
  event_id     uuid PK,
  processed_at timestamptz
)
```

**Relay + consumer**

```sql
-- RELAY (N instances safe)
BEGIN;
SELECT id, event_id, aggregate_id, payload FROM outbox
WHERE published_at IS NULL
ORDER BY id LIMIT 100
FOR UPDATE SKIP LOCKED;
-- publish each to Kafka, key = aggregate_id
UPDATE outbox SET published_at = now() WHERE id = ANY(:ids);
COMMIT;   -- crash after publish, before commit → re-sent (at-least-once)

-- CONSUMER (one tx with its own side effect)
BEGIN;
INSERT INTO processed_events (event_id) VALUES (:event_id)
ON CONFLICT DO NOTHING;       -- 0 rows → duplicate → skip, ack
-- ... apply the effect ...
COMMIT;  -- then ack / commit the offset
```

- **Partition key**: Kafka key = `aggregate_id`, giving per-entity ordering (all events of one transfer/order in one partition). The outbox table lives on the aggregate's shard.
- **Alternative**: CDC (Debezium reading the WAL) instead of a polling relay: lower latency, no polling load, but more infrastructure.
- **Monitor**: Age of the oldest unpublished row, consumer lag, DLQ size.
---

## Tech limits & latency

### Tech limits · per node unless stated (orders of magnitude)

| Tech | Reads | Writes | Storage | Latency | Scale-out / note |
|---|---|---|---|---|---|
| Postgres | 10–50K QPS (indexed point reads) | <2K/s easy · 2–10K/s big box · >10K/s shard · hot row ~100s–1K/s | <5 TB · 5–30 TB · >30–50 TB · RDS max 64 TB · Aurora 128 TB | read 1–5 ms · commit 2–10 ms | Read replicas (lag ms–s), partition by time, shard by the invariant's owner. ~100s connections → PgBouncer. |
| Redis | 100–200K ops/s (≈1M with pipelining) | RAM-bound: ~25–100 GB per shard practical | < 1 ms | Cluster for more throughput or memory; HA via replica / Sentinel is a separate axis. Cache, counters, rate limits, sessions. |
| DynamoDB | 3,000 RCU / partition | 1,000 WCU / partition | Unlimited table; 10 GB per partition; item ≤ 400 KB | single-digit ms | Pure key access at any scale; a hot partition key is the limit. |
| Kafka | 100K–1M msg/s per broker (~100+ MB/s); ~10 MB/s per partition | Disk retention: TBs per broker; tiered storage to S3 | 5–20 ms end to end | Ordering per partition; scale = partitions; replay supported. Event log, CDC, high volume. |
| SQS | Standard ≈ unlimited · FIFO 300 msg/s (3,000 batched; higher in high-throughput mode) | Msg ≤ 256 KB · retention ≤ 14 days | 10–100 ms | Managed work queue; Standard = at-least-once, unordered; DLQ built in. |
| RabbitMQ | ~20–50K msg/s per node (less when persistent) | GBs; not for long retention | ~1–10 ms | Routing, per-message acks, work queues. No replay. |
| S3 | 5,500 GET/s per prefix | 3,500 PUT/s per prefix | Unlimited · object ≤ 5 TB · ~$23/TB-month | first byte 10–100 ms | Scales with more prefixes. Blobs, documents, backups, data-lake; serve via a CDN. |
| S3 Glacier | Instant Retrieval: ms · Flexible: minutes–12 h · **Deep Archive: ~12 h (48 h bulk)** | Unlimited · Deep Archive **~$1/TB-month** · min 90–180 days | ms → hours | Compliance archives (AML records 5+ years). Move data with lifecycle policies, not custom archivers. |
| Stateless API | 1–5K req/s per instance | — | 5–20 ms per hop | Horizontal behind an LB; autoscale on CPU / RPS. |

### Latency & time

| Hop | Latency |
|---|---|
| RTT same AZ | ~0.5 ms |
| RTT cross-AZ (same region) | 1–2 ms |
| **Cross-region inside Europe** | 15–30 ms |
| **EU ↔ US East** | 70–100 ms |
| EU ↔ Asia | 150–250 ms |
| Mobile ↔ edge | 50–150 ms |
| External PSP / bank API | 200 ms – 2 s |
| Sync cross-region replication | +1 RTT per commit |

| Fact | Value |
|---|---|
| 1 day | 86,400 s ≈ 10⁵ s |
| 1M / day | ≈ 12 / s |
| Peak factor | avg × 2–5 (sales × 10+) |
| 99.9% · 99.95% · 99.99% | 8 h 45 min · 4 h 20 min · 53 min per year |
| Sync vs async | Sync when the caller needs the answer to continue; async for consequences (notifications, projections, slow downstreams) |

---

## Legal & compliance

### Legal & compliance names

- **KYC Know Your Customer**: Verify who the customer is at onboarding (ID document, selfie/liveness, address) and refresh it periodically. No verified identity, no account.
- **AML Anti-Money Laundering**: Ongoing monitoring of transactions to detect and report laundering and terrorist financing: sanctions/PEP screening, limits, suspicious-activity reports. Records kept **5 years** after the relationship ends.
- **PCI DSS Payment Card Industry Data Security Standard**: Security standard for any system that stores, processes or transmits card numbers (PAN). Shrink the scope with tokenisation or the provider's hosted fields; never store the CVV.
- **GDPR General Data Protection Regulation (EU)**: Rules for personal data: a lawful basis, minimisation and purpose limitation, user rights (access, erasure, portability), breach notice within **72 h**, privacy by design. AML retention overrides erasure.
- **SCC Standard Contractual Clauses**: EU-approved contract templates that make it lawful to transfer personal data outside the EEA to a country without an adequacy decision, plus a transfer impact assessment.
- **Adequacy decision**: The EU recognises a country as equivalent (UK, Japan, the US via the Data Privacy Framework), so data can flow there without SCCs.
- **PSD2 / SCA Payment Services Directive 2 / Strong Customer Authentication**: EU payments law; SCA requires 2 of 3 factors (something you know, have, are) for payments and sensitive actions such as adding a payee.
- **Data residency**: Data stored and processed inside a given jurisdiction. In design terms: a cell per legal entity, home-region writes, failover inside the jurisdiction.
- **Safeguarding (e-money institutions)**: Customer funds are held segregated from the company's own money, so they're protected if the firm fails. That's why each legal entity keeps its own balance sheet.
---

## Encryption

### How to store encrypted data

- **In transit**: TLS 1.2+/1.3 at the edge, terminated at the LB; **mTLS** between internal services (both sides present certificates, which also proves the service's identity).
- **At rest, disk level**: Volume / TDE encryption with KMS-managed keys (RDS, EBS, S3 SSE-KMS). Protects stolen disks and backups, but not someone who can query the DB.
- **Field level, envelope encryption**: Encrypt sensitive fields in the app with a data key (DEK, AES-256-GCM). The DEK is itself encrypted by a master key (KEK) that never leaves the KMS/HSM. Store the ciphertext + the encrypted DEK + key id. Rotation re-wraps DEKs; the data isn't re-encrypted.
- **Searching encrypted fields**: Blind index: an extra column `HMAC(email, secret)` with UNIQUE, for equality lookups without decrypting.
- **Cards**: Tokenisation: a vault (in PCI scope) maps PAN → token, and the rest of the system only sees tokens.
- **Passwords**: Hash, never encrypt: argon2id / bcrypt with a salt.
- **GDPR erasure**: Crypto-shredding: a per-user key; deleting it makes their data unreadable everywhere, including backups and logs.
- **Secrets & access**: Keys and secrets in KMS / Secrets Manager / Vault, never in code. Least privilege, access logged, PII masked in logs.
**Example**

```sql
users_pii(
  user_id     uuid PK,
  email_hmac  bytea UNIQUE,   -- blind index for lookups
  email_enc   bytea,          -- AES-256-GCM ciphertext
  name_enc    bytea,
  iban_enc    bytea,
  dek_enc     bytea,          -- data key, wrapped by the KMS master key
  kek_id      text,           -- which master key wrapped it (for rotation)
  region      text            -- home cell / residency
)

-- write: dek = KMS.GenerateDataKey(kek_id)
--        email_enc = AES_GCM(dek.plain, email); dek_enc = dek.wrapped
--        discard dek.plain from memory
-- read:  dek = KMS.Decrypt(dek_enc) → decrypt fields (KMS calls are audited)
```
