"""
Make Twilio call a phone number and connect them to the LiveKit voice agent.
Usage:
    uv run python scripts/test_call.py                    # calls default number
    uv run python scripts/test_call.py +919413752688      # calls specified number
"""
import os
import sys

from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM = "+15878175156"
LIVEKIT_SIP_URI = "sip:+15878175156@lk.bizbull.ai:5060"

DEFAULT_TO = "+919413752688"


def make_call(to: str) -> str:
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    twiml = f"<Response><Dial><Sip>{LIVEKIT_SIP_URI}</Sip></Dial></Response>"

    call = client.calls.create(
        to=to,
        from_=TWILIO_FROM,
        twiml=twiml,
    )
    print(f"Calling {to}...")
    print(f"Call SID: {call.sid}")
    print(f"Status:   {call.status}")
    return call.sid


if __name__ == "__main__":
    to_number = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TO
    make_call(to_number)
