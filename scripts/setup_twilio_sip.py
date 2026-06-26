"""
Point Twilio Elastic SIP Trunk origination at LiveKit Cloud (inbound calls).

Usage:
    uv run python scripts/setup_twilio_sip.py              # show current config
    uv run python scripts/setup_twilio_sip.py --apply      # update origination URI
"""
import argparse
import os
import sys

from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

TWILIO_NUMBER = os.environ.get("TWILIO_NUMBER", "+15878175156")
# LiveKit Cloud SIP host (project id prefix)
LIVEKIT_SIP_HOST = os.environ.get(
    "LIVEKIT_SIP_HOST", "5qg9858y0ak.sip.livekit.cloud"
)
# Twilio origination URI — no port; Cloud handles SIP on standard ports
CLOUD_ORIGINATION_URI = os.environ.get(
    "TWILIO_ORIGINATION_URI", f"sip:{LIVEKIT_SIP_HOST}"
)
TRUNK_NAME = os.environ.get("TWILIO_TRUNK_NAME", "parkash-liveket")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Replace origination URIs with the LiveKit Cloud SIP URI",
    )
    args = parser.parse_args()

    client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])

    trunks = [
        t for t in client.trunking.v1.trunks.list() if t.friendly_name == TRUNK_NAME
    ]
    if not trunks:
        print(f"ERROR: trunk '{TRUNK_NAME}' not found. Available trunks:")
        for t in client.trunking.v1.trunks.list():
            print(f"  - {t.friendly_name} ({t.sid})")
        return 1

    trunk = trunks[0]
    print(f"Trunk: {trunk.friendly_name} ({trunk.sid})")

    numbers = client.incoming_phone_numbers.list(phone_number=TWILIO_NUMBER)
    if numbers:
        n = numbers[0]
        print(f"Number: {n.phone_number}  trunk_sid={n.trunk_sid}")
        if n.trunk_sid != trunk.sid:
            print(
                f"WARNING: {TWILIO_NUMBER} is on trunk {n.trunk_sid}, "
                f"not {trunk.sid} ({TRUNK_NAME})"
            )
    else:
        print(f"WARNING: {TWILIO_NUMBER} not found in this Twilio account")

    orig_urls = client.trunking.v1.trunks(trunk.sid).origination_urls.list()
    print("\nCurrent origination URIs:")
    if not orig_urls:
        print("  (none)")
    for o in orig_urls:
        print(f"  {o.sip_url}  priority={o.priority}  enabled={o.enabled}")

    print(f"\nTarget LiveKit Cloud origination URI: {CLOUD_ORIGINATION_URI}")

    if not args.apply:
        print("\nDry run — pass --apply to update Twilio.")
        return 0

    for o in orig_urls:
        client.trunking.v1.trunks(trunk.sid).origination_urls(o.sid).delete()
        print(f"Deleted old origination: {o.sip_url}")

    created = client.trunking.v1.trunks(trunk.sid).origination_urls.create(
        friendly_name="LiveKit Cloud",
        sip_url=CLOUD_ORIGINATION_URI,
        priority=10,
        weight=10,
        enabled=True,
    )
    print(f"\nCreated origination: {created.sip_url} (sid={created.sid})")
    print("\nTwilio inbound calls will now route to LiveKit Cloud.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
