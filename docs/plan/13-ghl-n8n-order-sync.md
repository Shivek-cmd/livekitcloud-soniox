# GHL + n8n Order Sync — Plan (CRM & follow-ups)

> **Status:** **G0+G1+G2b live** (Sierra → n8n → GHL contact + Voice Orders opp + confirm SMS via **Opportunity Created**). **Next:** G3 abandoned / G4 completed.  
> **Last updated:** 2026-07-17  
> **Goal:** Push Sierra / Clover order lifecycle into **GoHighLevel (GHL)** via **self-hosted n8n** so Bizbull can run **automations** (SMS and stage-based workflows). Contacts hold identity; **opportunities** hold per-order automation state.  
> **Tenant:** **Bizbull only** (single restaurant). Multi-tenant later.  
> **Priority:** Automations first (not an owner pipeline dashboard).  
> **Doc rule:** Any plan change (now or later) is written here **before** build; status tables updated when shipped.  
> **Artifacts:** [`n8n/sierra-ghl-connection-stub.json`](../../n8n/sierra-ghl-connection-stub.json) · [`n8n/README.md`](../../n8n/README.md) · [`pr/pr_071_n8n-order-placed-webhook.md`](../../pr/pr_071_n8n-order-placed-webhook.md) · [`pr/pr_072_ghl-opportunity-on-place.md`](../../pr/pr_072_ghl-opportunity-on-place.md)  
> **Context:** [`09-clover-pos.md`](09-clover-pos.md) · [`12-admin-analytics-supabase.md`](12-admin-analytics-supabase.md) · [`HANDOFF.md`](../HANDOFF.md)

---

## Production readiness — what “live” means today

| Layer | Status | Notes |
|-------|--------|--------|
| n8n webhook (prod) | ✅ | `https://n8n.bizbull.ai/webhook/sierra-ghl-sync` — workflow Active |
| GHL contact upsert + custom fields | ✅ | Tags + `last_order_*` fields (§7.1) |
| Multi-order SMS | ✅ **Option B** | Confirm SMS on **Opportunity Created** + Allow multiple opportunities |
| GHL confirm SMS workflow | ✅ **Option B** | Trigger: **Opportunity Created** + In Pipeline `Voice Orders` |
| SMS “Delivered” in GHL Conversations | ✅ | Device filtering may hide SMS; GHL Delivered = stack OK |
| Sierra agent auto-POST | ✅ **G1 (PR 071)** | VPS: `N8N_SYNC_ENABLED=1` + webhook URL |
| **GHL Opportunities / pipeline** | ✅ **G2b (PR 072)** | Multi-order: one opp + one SMS each — verified |
| Abandoned / Clover completed | ⬜ | G3 · G4 (create/move opportunities) |
| Webhook HMAC / idempotency / dead-letter | ⬜ | G5 |

**Production rule:** CRM/SMS/opp sync must stay **fail-open** for voice. GHL “Delivered” = accepted by carrier path; device filtering is outside our stack.

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
| 1 | Primary win | **Automations** (SMS + stage triggers); CRM contact trail supports that |
| 2 | Middleware | **Self-hosted n8n** → GHL APIs / workflows |
| 3 | “Delivered” meaning (v1) | Clover **order completed** (not courier tracking) |
| 4 | Incomplete calls | **Yes** — abandoned sync when phone + cart nonempty (G3) |
| 5 | Tenancy | **Bizbull only** now |
| 6 | Voice path | **Fail-open** — n8n/GHL failure never blocks place_order / goodbye / hang-up |
| 7 | Analytics vs CRM | Supabase admin = ops truth; **GHL = customer automations** |
| 8 | Pipeline purpose | **Automation hooks**, not an owner-facing kitchen board (v1) |
| 9 | Opportunities | **One opportunity per order** (repeat customers get many opps, one contact) |
| 10 | Confirm SMS trigger | **Opportunity Created** + In Pipeline `Voice Orders`. Tag `order-placed` labeling only. Allow multiple opportunities ON. |
| 11 | Place failed (Clover error) | **No opportunity** in v1 (log / optional later `Lost`) |
| 12 | Doc discipline | Update **this plan** whenever scope/phases change — before coding |

---

## 3. What GHL is for (and not for)

### GHL owns
- Contact upsert (name + phone) + last-order fields
- Tags for fast triggers (confirm SMS today)
- **Opportunities / `Voice Orders` pipeline** for per-order automation stages (§7.2)
- Workflows: confirm, abandoned recovery, completed/review
- Messaging inbox (SMS)

### Clover still owns
- Menu, kitchen tickets, Register, payments, order status source of truth

### Sierra / Supabase still own
- Live conversation, cart authority, call transcripts, latency QA

```
  CUSTOMER                 POS / OPS                      CRM / AUTOMATION
  ────────                 ─────────                      ────────────────
  Phone/Web → Sierra  →    Clover (ticket + status)
                      ↘              ↓ webhooks
                       →  n8n  ←─────┘
                              ↓
                           GHL contact + opportunity stages
                              ↓
                           GHL workflows (SMS / later stage triggers)
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
                                                            │  Opportunity│
                                                            │  + workflows │
                                                            └─────────────┘
```

### Design rules (locked)

1. **Sierra stays thin** — POST a normalized JSON envelope to one n8n webhook (or few). No GHL SDK in the agent.
2. **n8n owns mapping** — GHL field IDs, tags, **opportunities/stages**, workflow triggers, retries, dead-letter logging.
3. **Normalized payload** — not raw Clover JSON dump into GHL.
4. **Idempotency** — same `event_id` / `clover_order_id` / `session_id` must not create duplicate contacts, duplicate SMS, or duplicate opportunities (G5 hardens).
5. **Phone is the contact key** — E.164 preferred; GHL upsert by phone.
6. **One opportunity per order** — pipeline stages drive automations; not an owner kitchen board.
7. **PII / CASL** — Canadian SMS needs clear restaurant identity + STOP handling via GHL.

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

- Emit abandoned only if useful for follow-up: **phone known** AND **cart nonempty** (locked §7.2 / G3). Pure browse with no identity → skip GHL.
- `event_id` must be stable for retries (e.g. `order.placed:{clover_order_id}` or `session.ended:{session_id}`).

---

## 7. GHL object model (v1)

| GHL object | Use |
|------------|-----|
| **Contact** | Who the customer is (phone key); `last_order_*` snapshot |
| **Tags** | Fast automation triggers (§7.1) — confirm SMS today |
| **Custom fields** | Last-order facts on the contact (§7.1) |
| **Opportunity** | **One per order** — stage = automation hook (§7.2) |
| **Pipeline** | `Voice Orders` — stages for workflows, not staff board (§7.2) |
| **Workflows** | Tag-based (live) + stage-based (as opps ship) |

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

n8n upsert sets custom fields by **id** and applies tags by **name**.

### 7.2 Opportunities + pipeline — G2b (IDs locked)

**Why:** Tags/SMS cover “message now.” Opportunities cover **per-order journey** so GHL workflows can fire on **stage enter** (abandoned nudge, completed/review) without overloading the contact.

**Pipeline:** `Voice Orders` · id `wCQVOwUah69xD6KHFrsi` · location `uc3GK4buCjDTCkedqWyy`

| Stage | Stage id | When set | Automation intent |
|-------|----------|----------|-------------------|
| `Abandoned` | `ed4e4d7b-7a77-4e86-9c98-5a4204a046ac` | G3: session ended, no place, **phone + cart nonempty** | Delayed recovery SMS / wait |
| `Placed` | `a6c71988-47c0-4f13-8a2b-40b784a9a72f` | On `order.placed` (G2b): create **or** move Abandoned→Placed | Confirm SMS via **Opportunity Created** (Option B) |
| `Completed` | `35a07d49-4524-48b3-96c7-a89b679618f7` | G4: Clover order completed | Thanks / review ask |
| `Lost` | `c86cd5f9-b078-4487-8e64-19c963a92250` | Optional later (void / abandoned never recovered) | Suppress further SMS |

**Opportunity custom fields**

| Name | Field id | fieldKey | Type |
|------|----------|----------|------|
| `event_id` | `ebYtqePmkjxB2BFjaEtJ` | `opportunity.event_id` | TEXT |
| `clover_order_id` | `mqQZGfXEM7Ixbfcpbeej` | `opportunity.clover_order_id` | TEXT |
| `session_id` | `urTkDJuILkxhG4942CmU` | `opportunity.session_id` | TEXT |
| `order_summary` | `zH1m3iD6sNuy8y22uqMa` | `opportunity.order_summary` | LARGE_TEXT |

**Rules (production):**

1. **One opportunity per order** — never reuse an open opp for a later place on the same contact (unless same-session Abandoned→Placed move below).  
2. **Contact still upserted** every place; opp is additional.  
3. **Match keys** on opp custom fields (above).  
4. **Monetary value** = order `total`.  
5. **Name format:** `{order_type} · {first_name} · {summary}` truncated (e.g. `pickup · Aman · 1x Butter Chicken`).  
6. **Confirm SMS:** trigger = opportunity enters **`Placed`** (decision #10 / §8.1). Tag `order-placed` is labeling only.  
7. **Place failed:** no opportunity in v1.  
8. **Abandoned:** opportunity only if phone **and** cart has items (G3).

**Same-session Abandoned→Placed (implemented in n8n G2b):** when `order.placed` arrives with `session_id`, if an open `Abandoned` opp exists for that contact+session, **move it to `Placed`** and update value/summary; else **create** new `Placed`.

**Not in scope for pipeline v1:** owner dashboard UX, kitchen “In progress / Ready” micro-stages, multi-pipeline per channel.

---

## 8. Workflows

| Workflow | Trigger | Actions | Status |
|----------|---------|---------|--------|
| **W-Place** | `order.placed` → n8n | Upsert contact → fields → tags → create/move opp **Placed** | ✅ G0/G1 + G2b |
| **W-Place-Opp** | same `order.placed` | Opportunity → stage `Placed` (§7.2) | ✅ verified (multi-order) |
| **W-Confirm-SMS** | GHL: **Opportunity Created** / Voice Orders | Send confirm SMS (one execution per opportunity) | ✅ Option B verified |
| **W-Fail** | `order.place_failed` | Optional note; **no opp** v1 | ⬜ later |
| **W-Abandoned** | `session.ended` abandoned | Tag + opp `Abandoned` + delayed SMS | ⬜ G3 |
| **W-Completed** | Clover completed | Opp → `Completed` + contact fields + SMS | ⬜ G4 |

### 8.1 Confirmation SMS — Option B (Opportunity Created)

| Item | Decision |
|------|----------|
| Channel | GHL SMS |
| Approach | **GHL Workflow** |
| Trigger | **Opportunity Created** + filter **In Pipeline** = `Voice Orders` |
| Multi-order | **Allow multiple opportunities** ON (one SMS per opp / order) |
| Also enable | **Allow re-entry** ON |
| Do **not** use (for confirm) | Tag `order-placed`; Opportunity Changed; Opportunity Status Changed; Stale |
| Later (G3 move only) | Optional 2nd trigger: **Pipeline Stage Changed** → stage `Placed` (Abandoned→Placed) |
| Tags still applied | `voice-order`, `order-placed`, `pickup`/`delivery` — labeling only |
| Copy | Keep existing text; optionally use opp custom field `order_summary` |
| Device note | Phone filtering ≠ workflow failure |

**GHL setup checklist (Option B):**

1. Open existing confirm SMS workflow (or clone it).
2. **Pause** / remove the old trigger **Tag added → `order-placed`**.
3. Add trigger: **Opportunity Created** → filter **In Pipeline** = **Voice Orders**.  
   (Do not use Opportunity Changed / Status Changed / Stale for confirm.)  
4. Confirm settings: **Allow re-entry** ON, **Allow multiple opportunities** ON.
5. Keep **Send SMS** action (same message is fine).
6. Publish / make Active. Disable any duplicate old tag-based confirm workflow.
7. Test with a new PowerShell order → expect SMS every place.

### Follow-up throttle rules

- Confirm SMS: **once per opportunity** (Placed stage enter); stronger idempotency in G5
- Max **1** abandoned SMS per phone per **48h** (G3)
- No abandoned SMS if same session already placed
- Completed SMS only if opp/contact exists and not voided (G4)

---

## 9. Implementation phases

Code changes: `pr/pr_rules.md`. **Update this file when a phase starts or ships.**

### Phase G0 — ✅ DONE
Contact + tags + fields + confirm SMS + re-arm.

### Phase G1 — ✅ DONE (PR 071 / #111)
Sierra `place_order` → n8n; VPS `N8N_SYNC_ENABLED=1`.

### Phase G2 — ✅ mostly done in G0
SMS copy / quiet hours optional.

### Phase G2b — Opportunities on place — ✅ **DONE (PR 072)**

**Done when:** each `order.placed` creates a GHL opportunity in `Voice Orders` / `Placed` + confirm SMS via Opportunity Created (multi-order verified).

- [x] Create pipeline + stages in GHL (`Voice Orders` — §7.2)
- [x] Opp custom fields: `event_id`, `clover_order_id`, `session_id`, `order_summary`
- [x] Extend n8n after contact/tags → search Abandoned / create or move Placed
- [x] Fail-open on opp API errors (`neverError`)
- [x] Write pipeline/stage/field IDs into §7.2
- [x] Re-import workflow in n8n + attach credentials
- [x] Live test: multi-order → multiple opps + SMS (Option B)

### Phase G3 — Abandoned — ⬜
Phone + cart nonempty → tag + opp `Abandoned` + delayed SMS; same-session place → move to `Placed` (§7.2).

### Phase G4 — Clover completed — ⬜
Find opp by `clover_order_id` → `Completed` + SMS.

### Phase G5 — Harden — ⬜
HMAC, idempotency, dead-letter, optional Supabase mirror.

---

## 9.1 Roadmap snapshot

```
DONE  G0/G1   Sierra → n8n → GHL contact + tags
DONE  G2b     Opportunity Placed + confirm SMS (Opportunity Created)
NEXT  G3      Abandoned → opp + recovery SMS
THEN  G4      Clover completed → opp Completed + SMS
THEN  G5      Auth, idempotency, alerts
```

---

## 10. Suggested PR / doc naming

| Phase | Likely artifact |
|-------|-----------------|
| G0/G1 | ✅ `pr_071_n8n-order-placed-webhook` (#111) |
| G2b | ✅ `pr/pr_072_ghl-opportunity-on-place.md` |
| G3 | `pr/pr_073_n8n-session-abandoned.md` |
| G4 | `pr/pr_074_clover-status-to-n8n.md` |
| G5 | Hardening / `vps-config.md` |

---

## 11. Out of scope (v1)

- Multi-tenant GHL / per-restaurant n8n routing
- Real courier delivery tracking
- Payments / card links inside GHL
- Replacing Supabase admin analytics
- Owner-facing pipeline UX / kitchen micro-stages
- Clover OAuth UI inside Sierra

---

## 12. Inputs already gathered (G0/G1)

| Item | Status |
|------|--------|
| GHL location + PIT in n8n | ✅ |
| n8n `https://n8n.bizbull.ai` | ✅ |
| SMS channel working | ✅ |
| Confirm SMS workflow on opp **Created** / Voice Orders | ✅ Option B |
| VPS `N8N_SYNC_ENABLED=1` + webhook URL | ✅ |
| Pipeline / opportunity custom fields in GHL | ✅ §7.2 |

**Still useful before G4:** Clover order webhook sample + how staff mark completed.

---

## 13. Success criteria

### Met (G0/G1/G2b)
- [x] Place → GHL contact + fields + tags  
- [x] Opportunity Created → confirm SMS (Option B); multi-order verified  
- [x] One opp per order in Voice Orders / Placed  
- [x] Live Sierra → n8n on VPS  
- [x] No-phone skip; fail-open  

### Remaining (v1)
- [x] Opportunity on each place (`Placed`) + multi-order SMS — **G2b** ✅  
- [ ] Abandoned → opp + recovery SMS — **G3**  
- [ ] Clover completed → opp `Completed` + SMS — **G4**  
- [ ] HMAC / idempotency / alerts — **G5**  

---

## 14. Resolved / open questions

| # | Question | Resolution |
|---|----------|------------|
| 1 | Abandoned with no phone? | **Skip GHL** |
| 2 | Abandoned with phone, empty cart? | **Skip opp** — require cart nonempty |
| 3 | Shadow Clover? | Still sync `order.placed` |
| 4 | SMS via workflow vs n8n API? | **GHL workflow** ✅ — trigger now **opp Placed** (was tag) |
| 5 | Switch SMS to opportunity? | **Yes — Option B** (§8.1): **Opportunity Created** / Voice Orders |
| 6 | One opp per order? | **Yes** ✅ |
| 7 | Pipeline for owner board? | **No** — automation only v1 |
| 8 | Place failed → opp? | **No** v1 |
| 9 | Supabase crm_sync_events? | Defer G5 |
| 10 | Doc updates? | **Always** update this plan before/when shipping |

---

## 15. Doc map

| Doc | Role |
|-----|------|
| **This file** | Source of truth for GHL/n8n plan + status |
| `n8n/README.md` | Import / credential / test webhook |
| `pr/pr_071_n8n-order-placed-webhook.md` | G1 ship record |
| `pr/pr_072_ghl-opportunity-on-place.md` | G2b ship record |
| `09-clover-pos.md` | POS / webhooks |
| `12-admin-analytics-supabase.md` | Ops analytics ≠ GHL |
| `vps-config.md` | `N8N_*` env on VPS |
| `pr/pr_rules.md` | Doc-first PRs |
