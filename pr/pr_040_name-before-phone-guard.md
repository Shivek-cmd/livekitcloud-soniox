# PR 040 — Name before phone guard

## Problem

Live call saved **`ਪਿਕਅੱਪ` (pickup) as customer name** when caller said pickup on turn 7:

- `parse_customer_name("ਪਿਕਅੱਪ")` treated single-word STT as a name.
- Name capture ran **before read-back confirmed**, skipping the real name step.
- Sierra said `"ਪਿਕਅੱਪ ਜੀ — ਫੋਨ ਨੰਬਰ ਦੱਸੋ"` instead of asking for name after order read-back.

## Fix

| Area | Change |
|------|--------|
| **Name blocklist** | `is_valid_customer_name()` rejects pickup/delivery/checkout tokens. |
| **Capture gate** | Name/phone capture only after `readback_confirmed`. |
| **Pickup intent** | PICKUP/DELIVERY turns skip name capture — ladder handles read-back. |
| **ORDER_TYPE ladder** | `is_likely_pickup_stt()` triggers read-back on Punjabi pickup phrases. |
| **Invalid name in cart** | Cleared before phone; asks real name via `phrase_name_for_order`. |
| **ready_to_place** | Rejects invalid names so pickup cannot complete an order. |

## Checkout order (enforced)

1. Allergies → pickup/delivery  
2. Read-back + "All good?"  
3. **Name**  
4. **Phone**  
5. Place order  

## Deploy

```bash
cd /opt/livekit-sarvam && git fetch origin && git checkout main && git reset --hard origin/main && uv sync && systemctl restart restaurant-agent
```

## Test plan

- [ ] Say pickup at ORDER_TYPE → English read-back, then name question (not phone)
- [ ] Single word "ਪਿਕਅੱਪ" / "pickup" never saved as name
- [ ] Real name `ਨਾਮ ਮera ਸ਼ਿਵੇਕ ਹੈ` → saved → phone asked
- [ ] Order cannot place with name = pickup
