import random
import string
from datetime import datetime

# In-memory store — replace with DB in Phase 2
_reservations: dict = {}

MAX_PARTY = 10
CAPACITY_PER_SLOT = 50

VALID_TIMES = [
    "11:00", "11:30", "12:00", "12:30", "13:00", "13:30",
    "14:00", "14:30", "18:00", "18:30", "19:00", "19:30",
    "20:00", "20:30", "21:00", "21:30",
]


def check_availability(date: str, time: str, party_size: int) -> tuple[bool, str]:
    if party_size > MAX_PARTY:
        return False, f"Maximum party size is {MAX_PARTY}."
    if time not in VALID_TIMES:
        times_str = ", ".join(VALID_TIMES)
        return False, f"Invalid time. Available slots: {times_str}"
    booked = sum(
        r["party_size"] for r in _reservations.values()
        if r["date"] == date and r["time"] == time
    )
    if booked + party_size > CAPACITY_PER_SLOT:
        return False, f"Sorry, {time} on {date} is full. Please choose another time."
    return True, "Available"


def book(date: str, time: str, party_size: int, name: str, phone: str) -> dict:
    ref = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    record = {
        "ref": ref,
        "date": date,
        "time": time,
        "party_size": party_size,
        "name": name,
        "phone": phone,
        "booked_at": datetime.now().isoformat(),
    }
    _reservations[ref] = record
    return record
