# PR index

All PRs follow **`pr_rules.md`**: doc first → branch name matches doc → merge via GitHub.

| PR | Branch | Topic | Merged |
|----|--------|-------|--------|
| 001 | `pr_001_soniox-cloud-restaurant-agent` | LiveKit Cloud + Soniox stack | ✅ |
| 002 | `pr_002_fix-inbound-twilio-cloud` | Twilio → Cloud SIP inbound | ✅ |
| 003 | `pr_003_clover-sandbox-probe` | Clover sandbox seed + probe | ✅ |
| 004 | `pr_004_clover-menu-cache` | Menu cache + tenant | ✅ |
| 005 | `pr_005_clover-prompt-and-phone-echo` | Clover prompt + phone echo | ✅ |
| 006 | `pr_006_voice-speech-policy` | Speech policy + voice_line | ✅ |
| 007 | `pr_007_tts-speech-engine` | TTS Gurmukhi default | ✅ |
| 008 | `pr_008_tier-a-phone-latency` | Phone TurnDetector + endpointing | ✅ |
| 009 | `pr_009_voice-domain-migration` | `voice.bizbull.ai` domain migration | ✅ |
| 010 | `pr_010_web-order-plan` | Web Order-with-Sierra plan doc | ✅ |
| 011 | `pr_011_web-w1-shell` | Web W1 — tabs + 3-panel + menu + captions | ✅ |
| 012 | `pr_012_web-w2-live-order` | Web W2 — live order + hybrid cart | ✅ |
| 013 | `pr_013_web-shared-latency` | Web shared latency + Mango Kulfi TTS | ✅ |
| 014 | `pr_014_handoff-docs` | Session handoff + docs sync | ✅ |
| 015 | `pr_015_conversation-production` | Tier B conversation layer + W6 web prompt | ✅ |
| 016 | `pr_016_order-flow-phrases` | Fixed phrases, phase advance, Bizbull branding | ✅ #39–40 |
| 017 | `pr_017_echo-and-flow-hardening` | Echo filter + intent + read-back hardening | ✅ #41–42 |
| 018 | `pr_018_customer-language` | Customer language + web parity | ✅ #43 |
| 019 | `pr_019_speech-policy-mango-chole` | Mango drink English TTS + chole/bhature Gurmukhi | ✅ #44 |
| 020 | `pr_020_web-background-ambient` | Web background ambient audio | ✅ #45 |
| 021 | `pr_021_web-ambient-volume` | Custom ambience mp3 + web volume | ✅ |
| 022 | `pr_022_phone-ambient-audio` | Phone ambient (same loop) | ✅ |
| 023 | `pr_023_phone-background-speech` | BVC + phone interruption + background filter | ✅ #52–53 |
| 024 | `pr_024_natural-concise-multi-item` | Concise confirms + multi-item parse + soft drink TTS | ✅ #54–55 |
| 025 | `pr_025_pickup-confirm-no-price-readback` | Pickup STT, all-good, no price, greeting, ambient 0.2 | ✅ #56–57 |
| 026 | `pr_026_handoff-doc-sync` | HANDOFF + PR index sync post 023–025 | ✅ |
| 027 | `pr_027_admin-analytics-platform` | Admin analytics: Supabase + session capture + admin.bizbull.ai | ✅ #60 |
| 028 | `pr_028_virtual-assistant-greeting` | Virtual assistant opening greeting | ✅ #61 |
| 029 | `pr_029_auto-hangup-after-order` | Auto hang-up after successful place_order | ✅ #62 |
| 030 | `pr_030_order-flow-quality` | Strict auto-add, final confirm, phase guards | ❌ **Reverted** — see doc |
| 031 | `pr_031_voice-fillers` | Intent-based voice fillers (phone + web) | ✅ #64 |
| 032 | `pr_032_menu-match-confidence` | Cross-script confidence menu matcher + auto-add gate | ✅ #69 |
| 033 | `pr_033_voice-lines-and-aliases` | Voice lines speak customer's word + slang aliases (shikanji etc.) | ✅ #70 |
| 034 | `pr_034_indic-safe-word-matching` | Indic-safe word boundaries (allergies stuck fix) | ✅ #71 |
| 036 | `pr_036_multi-item-add-and-no-price` | Multi-item auto-add + no volunteer price on web | ⬜ **Open** |
| 054 | `claude/repo-review-ujqggd` | Checklist-driven, model-led order flow (replaces rigid checkout ladder) — retroactive doc, see note | ✅ #90 |
| 055 | `pr_055_devanagari-add-item-coverage` | Devanagari (Hindi-script) add-item phrase recognition | ✅ |
| 056 | `pr_056_category-menu-browse` | Category/family menu browse (mithai, fish, desserts) | ⬜ **Open** |
| 057 | `pr_057_item-availability-and-kol-stopword` | Item availability + ਕੋਲ/Chole false-match fix | ⬜ **Open** |
| 058 | `pr_058_voice-line-load-and-contact-capture` | Voice line load at runtime + name/phone capture + duplicate goodbye | ⬜ **Open** |
| 059 | `pr_059_web-ui-soniox-theme` | Web UI: Soniox theme, menu pills, Sierra SVG avatar, local proxy | ⬜ **Open** |

> **Note on PR 054:** merged directly via Claude Code (Sandeep Taur) without following `pr_rules.md` — no doc-first, branch name doesn't match convention. Doc created after the fact: `pr/pr_054_checklist-driven-order-flow.md`. Numbered 054 because it merged right after PR 053.
>
> This table has gaps between 036 and 054 (PRs 037–053 exist as merged branches/docs but were never added to this index) — not fixed here, out of scope for this update.

---

## Current session state (2026-06-30)

| Item | Value |
|------|--------|
| **`main` commit** | `f4837c3` — Merge PR #62 (PR 029) |
| **Deploy branch** | **`main` only** — never deploy feature branches on VPS |
| **VPS path** | `/opt/livekit-sarvam` @ `89.117.18.192` |
| **Deploy command** | `bash scripts/vps_deploy.sh` or `git reset --hard origin/main` + restart agent |

### New AI session checklist

1. Read **`docs/HANDOFF.md`** first (primary source of truth).
2. Confirm `git log -1 --oneline` on VPS matches **`f4837c3`** (or newer if PRs merged since this doc).
3. Do **not** re-implement PR 030 without reading **`pr/pr_030_order-flow-quality.md`** (reverted — lessons inside).
4. Prefer **small PRs** — one ladder step or one data fix per PR.

### Next PR numbers

| PR | Scope | Status |
|----|--------|--------|
| **032** | Menu match confidence — cross-script phonetic matcher + abstain + auto-add gate | ⬜ **Open** — `pr_032_menu-match-confidence.md` (supersedes the "strict auto-add" idea) |
| **033** | Menu aliases batch (shikanji, STT typos) + Soniox STT vocabulary biasing | ⬜ suggested |
| **034** | Code-owned allergies ladder step | ⬜ suggested |

### PR 027 components

| Component | Status |
|-----------|--------|
| Supabase schema + migration | ✅ |
| Agent `SessionRecorder` + flush on close/shutdown | ✅ |
| Admin `admin.bizbull.ai` | ✅ |
| Call recordings | ⬜ deferred |
| Quality rubric UI | ⬜ deferred |
