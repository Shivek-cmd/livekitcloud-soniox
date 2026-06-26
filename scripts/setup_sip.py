"""
Configure LiveKit SIP inbound trunk and dispatch rule for the restaurant agent.
Run once after initial deployment or to reset SIP configuration.

Usage:
    uv run python scripts/setup_sip.py
"""
import asyncio

from dotenv import load_dotenv
from livekit.api import LiveKitAPI
from livekit.protocol.agent_dispatch import RoomAgentDispatch
from livekit.protocol.room import RoomConfiguration
from livekit.protocol.sip import (
    CreateSIPDispatchRuleRequest,
    CreateSIPInboundTrunkRequest,
    DeleteSIPDispatchRuleRequest,
    ListSIPDispatchRuleRequest,
    ListSIPInboundTrunkRequest,
    SIPDispatchRule,
    SIPDispatchRuleIndividual,
    SIPInboundTrunkInfo,
)

load_dotenv()

LIVEKIT_URL = "ws://localhost:7880"
LIVEKIT_API_KEY = "devkey"
LIVEKIT_API_SECRET = "7fb987483e9c463c7777ea7e9a97e4bde86bcaa5"
TWILIO_NUMBER = "+15878175156"


async def main():
    async with LiveKitAPI(url=LIVEKIT_URL, api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET) as lk:
        # Check if trunk already exists for this number
        trunks = await lk.sip.list_inbound_trunk(ListSIPInboundTrunkRequest())
        trunk_id = None
        for t in trunks.items:
            if TWILIO_NUMBER in t.numbers:
                trunk_id = t.sip_trunk_id
                print(f"Trunk already exists: {trunk_id}")
                break

        if not trunk_id:
            trunk = await lk.sip.create_inbound_trunk(
                CreateSIPInboundTrunkRequest(
                    trunk=SIPInboundTrunkInfo(
                        name="Twilio Restaurant Line",
                        numbers=[TWILIO_NUMBER],
                    )
                )
            )
            trunk_id = trunk.sip_trunk_id
            print(f"Trunk created: {trunk_id}")

        # Remove any existing dispatch rules for this trunk
        rules = await lk.sip.list_dispatch_rule(ListSIPDispatchRuleRequest())
        for r in rules.items:
            if trunk_id in r.trunk_ids:
                await lk.sip.delete_dispatch_rule(
                    DeleteSIPDispatchRuleRequest(sip_dispatch_rule_id=r.sip_dispatch_rule_id)
                )
                print(f"Deleted existing rule: {r.sip_dispatch_rule_id}")

        # Create dispatch rule with auto agent dispatch
        rule = await lk.sip.create_dispatch_rule(
            CreateSIPDispatchRuleRequest(
                name="Restaurant Agent Dispatch",
                trunk_ids=[trunk_id],
                rule=SIPDispatchRule(
                    dispatch_rule_individual=SIPDispatchRuleIndividual(
                        room_prefix="phone-",
                    )
                ),
                room_config=RoomConfiguration(
                    agents=[RoomAgentDispatch(agent_name="restaurant-agent")]
                ),
            )
        )
        print(f"Dispatch rule created: {rule.sip_dispatch_rule_id}")
        print("\nSIP configured:")
        print(f"  Trunk:  {trunk_id} → {TWILIO_NUMBER}")
        print(f"  Rule:   {rule.sip_dispatch_rule_id} → phone-* rooms → agent auto-dispatch")


asyncio.run(main())
