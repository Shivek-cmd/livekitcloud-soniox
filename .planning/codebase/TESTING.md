# Testing Patterns

**Analysis Date:** 2026-07-14

## Test Framework

**Runner:**
- pytest (Python)
- No TypeScript/JavaScript testing framework configured

**Config:**
- No `pytest.ini`, `setup.cfg`, or `pyproject.toml` pytest config section found
- Uses pytest defaults: discovers `test_*.py` files in `tests/` directory

**Assertion Library:**
- Python: pytest's built-in assertions (no external library)

**Run Commands:**
```bash
pytest                    # Run all tests in tests/
pytest tests/test_eou_watchdog.py  # Run specific test file
pytest -v                # Verbose output
pytest -k keyword        # Run tests matching keyword
```

## Test File Organization

**Location:**
- All Python tests co-located in `/tests/` directory (not alongside source)
- TypeScript: No tests found in `web/` or `admin/` directories

**Naming:**
- Pattern: `test_*.py` (e.g., `test_menu_match.py`, `test_agent_place_order.py`)
- Matches pytest auto-discovery convention

**Structure:**
```
tests/
├── test_menu_match.py          # Menu matching + auto-add gate regression (PR 032)
├── test_agent_place_order.py   # Hard gate, shadow mode, Clover submit
├── test_eou_watchdog.py        # End-of-utterance watchdog (PR 067)
├── test_voice_stack.py         # Voice pipeline initialization
├── test_agent_tools.py         # Agent tool invocations
├── test_session_vad.py         # Voice activity detection
├── test_phone_echo.py          # Echo cancellation filtering
├── test_phone_background.py    # Background noise filtering
├── [... 20+ more test files ...]
└── __pycache__/
```

**Current coverage:** 27 test files covering agent behavior, menu matching, voice processing, order submission, and edge cases.

## Test Structure

**Suite Organization:**
```python
"""PR 032 — cross-script confidence menu matching + auto-add gate.

Regression anchor: live call 2026-07-02 where "ਮਿਕਸ ਪਕੌੜਾ ਪਲੈਟਰ" resolved to
Punjabi Fish Curry because the courtesy verb ਕਰ substring-matched ਕਰੀ (curry)
while the real item's Gurmukhi spelling variants scored zero.
"""

import pytest

from restaurant import menu_provider
from restaurant.clover.match import MatchIndex, content_tokens, phonetic_key

def _item(iid, name, speak_as, voice_line, aliases, price=1000):
    return CachedMenuItem(...)

def _cache(items=None) -> MenuCache:
    items = items or [_item(...), _item(...), ...]
    return MenuCache(...)

def test_priority_ranking():
    """Test that phonetic matches score above substring matches."""
    cache = _cache([...])
    # assertions
```

**Patterns:**
- Docstring at module level explains test purpose and regression anchor (links to live incident)
- Helper classes for test doubles prefixed with `_Fake` (e.g., `_FakeSession`, `_FakeTenant`)
- Helper functions prefixed with `_` for test data builders (e.g., `_item()`, `_cache()`)
- No setUp/tearDown; fixtures used instead

## Mocking

**Framework:** pytest fixtures + manual `monkeypatch`

**Patterns:**
```python
@pytest.fixture()
def agent(monkeypatch) -> RestaurantAgent:
    monkeypatch.setattr(menu_provider, "extract_dish_query", lambda text: None)
    # ... setup agent
    return agent
```

**Test double example:**
```python
class _FakeSession:
    def __init__(self):
        self.said: list[tuple[str, bool]] = []
    
    @property
    def current_speech(self):
        return None
    
    async def say(self, text, allow_interruptions=True):
        self.said.append((text, allow_interruptions))
        return _FakeSpeechHandle()
```

**What to Mock:**
- External dependencies: menu provider, LLM calls, session state
- I/O operations: speech synthesis, order submission
- Async operations wrapped in fake futures

**What NOT to Mock:**
- Menu matching logic (business-critical; test real behavior)
- Phone number parsing (regression-prone; test with real examples)
- Text normalization (language-specific; test with live samples)

## Fixtures and Factories

**Test Data:**
```python
def _item(iid, name, speak_as, voice_line, aliases, price=1000):
    return CachedMenuItem(
        clover_item_id=iid,
        name=name,
        speak_as=speak_as,
        voice_line=voice_line,
        speech_mode="gurmukhi",
        price_cents=price,
        veg=True,
        available=True,
        category_id="",
        category_name="Test",
        aliases=aliases,
    )
```

**Location:**
- Test data builders defined as module-level `_functions()` within each test file
- No shared fixtures directory; fixtures are test-specific
- Session helpers defined as `_FakeSession` class within test module

## Coverage

**Requirements:** No coverage target enforced; no coverage tooling configured

**View Coverage:**
- Not configured; can run `pytest --cov` if pytest-cov installed

## Test Types

**Unit Tests:**
- Scope: Individual functions and classes
- Approach: Direct function calls with mocked dependencies
- Example: `test_menu_match.py` tests phonetic matching in isolation
- No isolation — many tests interact with real regex patterns and data structures

**Integration Tests:**
- Scope: Agent behavior with mocked session/LLM
- Approach: Instantiate `RestaurantAgent`, call methods, inspect session state
- Example: `test_agent_place_order.py` tests order placement with fake session
- Realistic interaction: monkeypatch replaces external APIs but keeps business logic intact

**E2E Tests:**
- Status: Not present
- No end-to-end tests running full call flow with real infrastructure

## Common Patterns

**Async Testing:**
```python
def run(coro):
    return asyncio.run(coro)

async def test_async_operation():
    result = await async_function()
    assert result == expected
```

**Fixture Usage:**
```python
@pytest.fixture()
def agent(monkeypatch) -> RestaurantAgent:
    monkeypatch.setattr(menu_provider, "extract_dish_query", lambda text: None)
    # ... setup
    return agent

def test_something(agent):
    # agent is injected
    agent.some_method()
```

**Event Simulation:**
```python
class _FakeSession:
    def __init__(self):
        self._handlers = {}
    
    def on(self, name):
        def _register(fn):
            self._handlers[name] = fn
            return fn
        return _register
    
    def emit(self, name, **fields):
        if name in self._handlers:
            self._handlers[name](SimpleNamespace(**fields))

session = _FakeSession()
# Simulate user speaking
session.user_speaks()
# Simulate STT final transcript
session.final("one samosa")
# Verify side effects
assert session.commits == [(expected_timeout, expected_flush)]
```

**Assertion on Behavior:**
- Tests record method calls and state changes, then assert them
- Example: `session.commits`, `session.clear_calls`, `session.said` track calls to agent methods
- No explicit assertion helpers; direct list/dict/value assertions

**Parameter-driven Tests:**
```python
@pytest.mark.parametrize("input,expected", [
    ("one samosa", {"clover_item_id": "SAMOSA", ...}),
    ("ਸਮੋਸਾ", {"clover_item_id": "SAMOSA", ...}),
])
def test_cross_script_match(input, expected):
    # test with multiple inputs
```

---

*Testing analysis: 2026-07-14*
