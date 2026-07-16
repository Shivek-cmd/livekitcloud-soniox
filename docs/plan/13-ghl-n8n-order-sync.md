# GHL + n8n Order Sync — Plan (CRM & follow-ups)

> **Status:** **G0 live** (n8n + GHL SMS). **G1 implemented** in `pr_071_n8n-order-placed-webhook` — enable on VPS with `N8N_SYNC_ENABLED=1`.  
> **Last updated:** 2026-07-16  
> **Goal:** Push Sierra / Clover order lifecycle events into **GoHighLevel (GHL)** via **self-hosted n8n**, so Bizbull can run **SMS follow-ups** and keep a light CRM trail.  
> **Tenant:** **Bizbull only** (single restaurant). Multi-tenant later.  
> **Priority:** Follow-ups first; CRM contact history second.  
> **Artifacts:** [`n8n/sierra-ghl-connection-stub.json`](../../n8n/sierra-ghl-connection-stub.json) · [`n8n/README.md`](../../n8n/README.md)  
> **Context:** [`09-clover-pos.md`](09-clover-pos.md) · [`12-admin-analytics-supabase.md`](12-admin-analytics-supabase.md) · [`HANDOFF.md`](../HANDOFF.md)

---

## Production readiness (Phase 0) — what “live” means today

| Layer | Status | Notes |
|-------|--------|--------|
| n8n webhook (prod) | ✅ | `https://n8n.bizbull.ai/webhook/sierra-ghl-sync` — workflow Active |
| GHL contact upsert + custom fields | ✅ | Tags + `last_order_*` fields (§7.1) |
| Multi-order SMS re-arm | ✅ | n8n removes then re-adds `order-placed` every run |
| GHL confirm SMS workflow | ✅ | Trigger: tag `order-placed` added → Send SMS |
| SMS “Delivered” in GHL Conversations | ✅ | Treat as system OK; iPhone Unknown Senders / carrier may hide message from user |
| Sierra agent auto-POST | ✅ **G1 (PR 071)** | Kill switch `N8N_SYNC_ENABLED` (default 0 on VPS until flipped) |
| Place-failed / abandoned / Clover completed | ⬜ | G1 fail path · G3 · G4 |
| Webhook HMAC / kill switch / dead-letter | ⬜ | G1 env + G5 harden |

**Production rule:** CRM/SMS must stay **fail-open** for voice. GHL “Delivered” = GHL accepted delivery to carrier; device filtering is outside our stack.

---
## 1. Problem statement

Today Sierra can place orders (log + optional Clover submit) and store call analytics in Supabase. Neither of those layers does **customer follow-up**:

- No automatic “order confirmed” / “ready for pickup” SMS
- No “finish your order?” when a call drops before place
- No lasting contact record an owner can message from a CRM
- Clover stays the kitchen/POS brain; it is not built for lifecycle marketing

**This plan adds a CRM + automation sink without putting GHL into the voice hot path.**

---

## 2. Locked product decisions (from planning discussion)

| # | Decision | Value |
|---|----------|--------|
| 1 | Primary win | **Follow-ups** (SMS/WhatsApp/email); CRM contact trail also required |
| 2 | Middleware | **Self-hosted n8n** (already available); GHL API keys ready |
| 3 | “Delivered” meaning (v1) | Clover **order completed** (not courier tracking) |
| 4 | Incomplete calls | **Yes in v1** — abandoned / no-place sessions sync to GHL for recovery follow-up |
| 5 | Tenancy | **Bizbull only** now |
| 6 | Voice path | **Fail-open** — n8n/GHL failure must never block place_order, goodbye, or hang-up |
| 7 | Analytics vs CRM | Supabase admin = ops truth; **GHL = customer automation**. Two sinks, two jobs |

---

## 3. What GHL is for (and not for)

### GHL owns
- Contact upsert (name + phone)
- Tags / custom fields for last order
- Workflows: confirm, ready/completed, abandoned recovery, later review ask
- Owner-facing CRM inbox for messaging

### Clover still owns
- Menu, kitchen tickets, Register, payments, order status source of truth

### Sierra / Supabase still own
- Live conversation, cart authority, call transcripts, latency QA

```
  CUSTOMER                 POS / OPS                      CRM / FOLLOW-UP
  ────────                 ─────────                      ───────────────
  Phone/Web → Sierra  →    Clover (ticket + status)
                      ↘              ↓ webhooks
                       →  n8n  ←─────┘
                              ↓
                           GHL workflows (SMS etc.)
```

---

## 4. Architecture

### Target shape

```
┌──────────────────┐     order.placed / session.ended      ┌─────────────┐
│  Sierra (VPS)    │ ───────────────────────────────────► │  n8n        │
│  agent + optional│     HTTPS POST (async, fire-forget     │  self-host  │
│  clover submit   │     + short retry)                     │             │
└────────┬─────────┘                                        │  workflows:  │
         │ submit                                           │  upsert GHL │
         ▼                                                  │  contact +  │
┌──────────────────┐     order.status (completed, …)        │  tag/SMS    │
│  Clover cloud    │ ───────────────────────────────────► │             │
└──────────────────┘     webhook (or poll fallback)         └──────┬──────┘
                                                                   │
                                                                   ▼
                                                            ┌─────────────┐
                                                            │  GoHighLevel│
                                                            │  Contact +  │
                                                            │  workflows  │
                                                            └─────────────┘
```

### Design rules (locked)

1. **Sierra stays thin** — POST a normalized JSON envelope to one n8n webhook (or few). No GHL SDK in the agent.
2. **n8n owns mapping** — GHL field IDs, tags, workflow triggers, retries, dead-letter logging.
3. **Normalized payload** — not raw Clover JSON dump into GHL.
4. **Idempotency** — same `event_id` / `clover_order_id` / `session_id` must not create duplicate contacts or duplicate SMS.
5. **Phone is the contact key** — E.164 preferred; GHL upsert by phone.
6. **PII / CASL** — Canadian SMS needs clear restaurant identity + STOP handling via GHL; capture consent assumptions in Phase G0.

---

## 5. Event model (v1)

| Event | Source | When | Why |
|-------|--------|------|-----|
| `order.placed` | Sierra | After successful `place_order` (Clover id present **or** shadow log-only) | Confirmation SMS + CRM note |
| `order.place_failed` | Sierra | Clover submit / place failed after customer intended to place | Ops + optional “we’ll call you back” |
| `session.ended` | Sierra | Call/web session closes **without** placed order | Abandoned recovery |
| `order.status_changed` | Clover → n8n | Status moves; v1 care about **completed** (+ optional open/locked) | “Ready / completed” follow-up |

### Status mapping (Bizbull v1)

| Clover signal | GHL meaning (v1) |
|---------------|------------------|
| Order created / open | Placed (if from Sierra we already fired `order.placed`) |
| Order **completed** | Treat as fulfilled / “done” (pickup picked up or delivery completed in their process) |
| Void / deleted (if available) | Tag `order-voided`; suppress review SMS |

Courier-true “delivered” is **out of scope** until a delivery integration exists.

---

## 6. Normalized payload contract (sketch)

All Sierra → n8n POSTs share a wrapper:

```json
{
  "schema_version": 1,
  "event": "order.placed",
  "event_id": "uuid-or-deterministic-key",
  "occurred_at": "2026-07-15T18:00:00Z",
  "tenant_id": "bizbull",
  "channel": "phone",
  "session_id": "livekit-room-or-recorder-id",
  "customer": {
    "name": "Gurpreet",
    "phone_e164": "+15875551234",
    "phone_raw": "5875551234"
  },
  "order": {
    "clover_order_id": "ABC123",
    "clover_submitted": true,
    "order_type": "pickup",
    "status": "placed",
    "items": [
      {"name": "Butter Chicken", "qty": 1, "price": 16.99, "note": "medium"}
    ],
    "subtotal": 16.99,
    "total": 16.99,
    "address": null,
    "allergy_note": "no nuts",
    "eta": "20-25 min"
  },
  "meta": {
    "language": "pa",
    "source": "sierra"
  }
}
```

### `session.ended` (abandoned) extras

```json
{
  "event": "session.ended",
  "outcome": "abandoned",
  "had_items_in_cart": true,
  "cart_snapshot": { "...": "optional items if any" },
  "customer": { "name": null, "phone_e164": null }
}
```

Rules:

- Emit abandoned only if useful for follow-up: prefer **phone known** OR **cart nonempty**. Pure browse with no identity can be dropped or logged only (decide in G1).
- `event_id` must be stable for retries (e.g. `order.placed:{clover_order_id}` or `session.ended:{session_id}`).

---

## 7. GHL object model (v1)

| GHL object | Use |
|------------|-----|
| **Contact** | Upsert by phone; name when known |
| **Tags** | See §7.1 Phase 0 |
| **Custom fields** | See §7.1 Phase 0 |
| **Note** or conversation | Optional later |
| **Workflows** | See Phase G2–G3 |

### 7.1 Phase 0 locked schema (live) — no “sierra” naming

**Tags**

| Tag | Tag id | When |
|-----|--------|------|
| `voice-order` | `cX6DnXwqmNK9oNOeo8m3` | Phone or web (voice agent) |
| `order-placed` | `cA1CImWSioJRyyMFYCnN` | Successful place |
| `pickup` | `ESw93ZUUrLF3DNVzajU8` | Pickup (already existed) |
| `delivery` | `e69VOpV1maet8VPvq8IV` | Delivery |

**Contact custom fields**

| Name | Field id | fieldKey | Type |
|------|----------|----------|------|
| `last_order_id` | `0QK5vxB5ntrYG44o33Gn` | `contact.last_order_id` | TEXT |
| `last_order_type` | `nl3jIwfxyUgQHPRlbGZl` | `contact.last_order_type` | TEXT |
| `last_order_status` | `Q59Rb7F84BNHvrL1gzOJ` | `contact.last_order_status` | TEXT |
| `last_order_total` | `IeLzeT4I8xitx3Jvk9mQ` | `contact.last_order_total` | NUMERICAL |
| `last_order_summary` | `FyLZbBVUDD9TzY7LXlm4` | `contact.last_order_summary` | LARGE_TEXT |
| `last_channel` | `UUqkRGbEl5HjS5Sd2eIz` | `contact.last_channel` | TEXT |

n8n upsert should set custom fields by **id** (or fieldKey per GHL API) and apply tags by **name**.

Avoid inventing a full “orders database” inside GHL in v1 — custom fields + notes + tags are enough for follow-ups.

---

## 8. Workflows

| Workflow | Trigger | Actions | Status |
|----------|---------|---------|--------|
| **W-Place** | `order.placed` → n8n | Upsert contact → custom fields → re-arm `order-placed` → apply tags → GHL SMS workflow | ✅ Phase 0 |
| **W-Fail** | `order.place_failed` | Upsert if phone → tag `order-failed` → optional owner alert | ⬜ G1 |
| **W-Abandoned** | `session.ended` abandoned | Upsert if phone → tag `order-abandoned` → delayed recovery SMS | ⬜ G3 |
| **W-Completed** | Clover status completed | Update fields/tags → thank-you / ready SMS | ⬜ G4 |

### 8.1 Confirmation SMS — locked & verified

| Item | Decision |
|------|----------|
| Channel | GHL SMS |
| Approach | **Option A** — GHL Workflow (not n8n Conversations API) |
| Trigger | Tag **`order-placed`** added |
| Multi-order | n8n **DELETE** `order-placed` then **POST** tags again every sync |
| Verified | PowerShell → prod webhook → GHL Conversations shows SMS **Delivered** |
| Device note | If GHL says Delivered but iPhone silent → Unknown Senders / Focus / carrier — not a workflow bug |

### Follow-up throttle rules (plan defaults — tune live)

- Confirm SMS: once per successful n8n sync (re-arm pattern); avoid double-fire only if we add idempotency key later (G5)
- Max **1** abandoned SMS per phone per **48h** (G3)
- No abandoned SMS if `order.placed` already for same session
- Completed SMS only if contact exists and order not voided (G4)

---

## 9. Implementation phases

Work **phase by phase**. Code changes use `pr/pr_rules.md` (doc first → branch = doc name).

### Phase G0 — Setup, CRM sync, confirm SMS — ✅ DONE (2026-07-16)

**Done when:** prod webhook upserts contact + fields + tags; GHL SMS workflow fires; multi-order re-arm works.

| Item | Status |
|------|--------|
| GHL Location `uc3GK4buCjDTCkedqWyy` | ✅ |
| n8n Header Auth (PIT) | ✅ — never commit token |
| Tags + custom fields (§7.1) | ✅ |
| Importable workflow + sticky notes | ✅ [`n8n/sierra-ghl-connection-stub.json`](../../n8n/sierra-ghl-connection-stub.json) |
| Prod URL Active | ✅ `https://n8n.bizbull.ai/webhook/sierra-ghl-sync` |
| Confirm SMS (tag → GHL workflow) | ✅ Delivered in Conversations |
| Re-arm for repeat orders | ✅ remove → re-add `order-placed` |

### Phase G1 — Sierra → n8n (production voice path) — ✅ **PR 071**

**Done when:** real phone/web `place_order` POSTs the normalized envelope without PowerShell.

- ✅ `restaurant/integrations/n8n_webhook.py` — async POST, timeout, **never raise**
- ✅ Called from `place_order` after successful place
- ✅ Env: `N8N_SYNC_ENABLED` (default 0), `N8N_WEBHOOK_ORDERS_URL`, optional `N8N_WEBHOOK_SECRET`
- ✅ Unit tests: `tests/test_n8n_webhook.py` + place_order wiring
- Branch/doc: `pr/pr_071_n8n-order-placed-webhook.md`

**Ops:** keep `N8N_SYNC_ENABLED=0` on VPS until first live call reviewed, then set `1`.

### Phase G2 — Confirm SMS polish — ✅ mostly done in G0

- GHL workflow already live; copy edits stay in GHL UI
- Optional: quiet hours, STOP footer tweak, Canadian from-number check for CA callers

### Phase G3 — Abandoned `session.ended` — ⬜

- Emit on session end without place (phone required)
- Tag `order-abandoned` + delayed SMS + 48h throttle

### Phase G4 — Clover completed → GHL — ⬜

- Clover status webhook → n8n → update `last_order_status` + tag `order-completed` → SMS

### Phase G5 — Harden (production grade) — ⬜

- HMAC/shared secret on webhook
- Idempotency on `event_id` / `clover_order_id` (no double SMS on retry)
- n8n error → Slack/email dead-letter
- Optional Supabase `crm_sync_events` mirror
- Kill switches per event type

---

## 9.1 Roadmap snapshot (what a full production system still needs)

```
DONE (G0)     n8n ← PowerShell/manual     → GHL contact + SMS
NEXT (G1)     Sierra place_order          → n8n (same webhook)
THEN (G3)     Abandoned calls             → recovery SMS
THEN (G4)     Clover completed            → done/thanks SMS
THEN (G5)     Auth, idempotency, alerts   → restaurant-grade ops
```

Pickup vs delivery, phone vs web, repeat same-day orders: **handled in G0 data model** once G1 wires Sierra.

---
## 10. Suggested PR / doc naming (when we implement)

| Phase | Likely artifact |
|-------|-----------------|
| G0 | Doc updates + n8n export notes in this plan |
| G1 | `pr/pr_070_n8n-order-placed-webhook.md` (number confirm at start) |
| G2 | Mostly n8n + GHL config (doc checklist in plan) |
| G3 | `pr/pr_071_n8n-session-abandoned.md` |
| G4 | `pr/pr_072_clover-status-to-n8n.md` (+ Caddy route if needed) |
| G5 | Hardening PR or ops notes in `vps-config.md` |

Numbers are placeholders — pick next free PR number when coding starts.

---

## 11. Out of scope (v1)

- Multi-tenant GHL / per-restaurant n8n routing
- Real courier delivery tracking
- Payments / card links inside GHL
- Replacing Supabase admin analytics
- Full GHL “opportunities pipeline” UI redesign
- Putting Clover OAuth UI inside Sierra

---

## 12. What we need from you (before / during G0)

Please gather these so Phase G0 can close without blocking:

### A. GoHighLevel
1. **Location / sub-account** name used for Bizbull  
2. **Private Integration token** (or OAuth) with scopes to: contacts upsert, tags, notes, workflows/custom fields as needed  
3. Confirmation of preferred channel for v1 follow-ups: **SMS vs WhatsApp vs both**  
4. From-number / messaging readiness already verified in GHL  
5. OK to create the custom fields + tags listed in §7 (or send a screenshot of existing fields to reuse)

### B. n8n (self-hosted)
1. **Public HTTPS base URL** for webhooks (e.g. `https://n8n.yourdomain.com`)  
2. Confirmation VPS / Sierra can reach it (firewall / allowlist)  
3. Preferred auth: shared secret header vs Basic Auth vs n8n webhook token  
4. Optional: export folder or naming convention for workflow JSON backups in-repo (or keep workflows only in n8n)

### C. Clover (for Phase G4, can wait until G1–G2 done)
1. Whether **order webhooks** are enabled for this merchant / app  
2. Sample payload for order create / update / complete (sandbox ok)  
3. How staff mark an order **completed** today (Register button flow) so we match reality

### D. Product copy / compliance
1. Draft SMS templates you like (confirm, abandoned, completed) — or ask us to propose English + short Punjabi mix  
2. Business name for SMS header / CASL-style footer preference  
3. Abandoned delay (suggestion: **30–60 minutes**) and quiet hours (e.g. no SMS 10pm–9am local)

### E. Environments
1. Do you want a **GHL test contact / test tag** first (`sierra-test`) before real customers? (Recommended: yes)  
2. Should production Sierra use `N8N_SYNC_ENABLED=0` until W-Place is verified? (Recommended: yes)

---

## 13. Success criteria

### Phase 0 (met)
- [x] Placed-order test → GHL contact + last-order fields within ~30s  
- [x] Confirm SMS path (tag → GHL workflow); Conversations shows **Delivered**  
- [x] Repeat sync re-arms `order-placed` (no manual tag delete)  
- [x] No-phone → skip GHL, still HTTP 200  

### Full v1 (remaining)
- [ ] Live Sierra `place_order` → same n8n webhook (G1)  
- [ ] Abandoned session with phone → recovery follow-up (G3)  
- [ ] Clover **completed** → GHL update + optional SMS (G4)  
- [ ] Webhook auth + idempotency + error alerts (G5)  
- [ ] n8n/GHL outage never breaks Sierra place + hang-up (prove under G1 kill switch)  

---

## 14. Resolved / open questions

| # | Question | Resolution |
|---|----------|------------|
| 1 | Abandoned with no phone? | **Skip GHL** (Phase 0); optional owner alert later |
| 2 | Shadow Clover (`CLOVER_SUBMIT_ORDERS=0`)? | Still sync `order.placed`; `last_order_id` may be session id |
| 3 | SMS via GHL workflow vs n8n API? | **GHL workflow** (Option A) ✅ |
| 4 | Supabase crm_sync_events? | Defer to G5; n8n executions enough for G0–G1 |
| 5 | Naming “sierra” in tags/fields? | **No** — use `voice-order`, `order-placed`, `last_order_*` |

---
## 15. Doc map

| Doc | Role |
|-----|------|
| **This file** | Plan + phases + asks |
| `09-clover-pos.md` | POS submit / webhooks background |
| `12-admin-analytics-supabase.md` | Do not merge responsibilities into GHL |
| `vps-config.md` | Will gain n8n env vars at G1 |
| `pr/pr_rules.md` | Doc-first PRs when code starts |
