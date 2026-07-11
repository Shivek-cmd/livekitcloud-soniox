"""Thin shim over the hybrid agent worker (restaurant/agent/worker.py).

The filename and agent_name="restaurant-agent" are load-bearing: systemd runs
`python agent.py start` (deploy/restaurant-agent.service) and
scripts/setup_sip.py dispatches on the agent name. Everything else lives in
restaurant.agent.*.
"""

from restaurant.agent.worker import entrypoint, run

__all__ = ["entrypoint", "run"]

if __name__ == "__main__":
    run()
