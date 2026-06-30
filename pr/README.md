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

---

## Current session state

**`main` through PR 025** (`7232d48` area). **No open PRs.**

**New AI session:** read **`docs/HANDOFF.md`** first.

**Next PR number:** **026** (when starting new work).

**Deploy after pull:** `bash /opt/livekit-sarvam/scripts/vps_deploy.sh`
