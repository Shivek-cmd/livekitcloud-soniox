# Coding Conventions

**Analysis Date:** 2026-07-14

## Naming Patterns

**Files:**
- Python modules: `snake_case.py` (e.g., `menu_provider.py`, `customer_info.py`)
- TypeScript: `camelCase.tsx` for components, `camelCase.ts` for utilities (e.g., `useCart.tsx`, `api.ts`)
- React components: `PascalCase.tsx` (e.g., `OrderPanel.tsx`, `SierraPanel.tsx`)

**Functions:**
- Python: `snake_case` with type hints (e.g., `def extract_dish_query(text: str) -> str | None`)
- Private Python functions: `_prefixed_snake_case` (e.g., `_strip_availability_phrases()`, `_get_cache()`)
- TypeScript: `camelCase` (e.g., `performRpc()`, `signOut()`)
- React hooks: `useXxx` pattern (e.g., `useCart()`, `useTheme()`, `useRoomContext()`)

**Variables:**
- Python: `snake_case` (e.g., `_cache`, `_cache_loaded`, `normalized`)
- TypeScript: `camelCase` (e.g., `isLight`, `theme`, `connected`)
- Constants in Python: `UPPER_CASE` when module-level (e.g., `_INDIC_NUMERAL_MAP`, `_PHONEISH`)

**Types:**
- Python: Type hints inline in signatures or via `from __future__ import annotations` (e.g., `str | None`, `list[str]`)
- TypeScript: `interface` for object contracts or `type` for unions (e.g., `interface Props`, `type Tab = 'order' | 'store'`)
- TypeScript: `PascalCase` for interface/type names (e.g., `CartApi`, `OrderState`, `CachedMenuItem`)

## Code Style

**Formatting:**
- Python: No explicit formatter configured; code appears to follow PEP 8 conventions manually
- TypeScript: No prettier/eslint config found; appears to use IDE defaults; consistent 2-space indentation observed

**Linting:**
- Python: No linting config found (.flake8, .pylintrc, ruff.toml); linting is not enforced
- TypeScript: tsconfig.json enforces `"strict": true`, which enables:
  - `"noEmit": true` — no JavaScript output, type-check only
  - `"strict": true` — all strict type checks enabled

**TypeScript strictness:**
- `"target": "ES2020"` — modern syntax support
- `"strict": true` — mandatory type safety
- `"isolatedModules": true` — each file is independently transpilable

## Import Organization

**Order (Python):**
```python
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from restaurant.menu import find_item as static_find_item
from restaurant.text_match import indic_word_re, word_bounded
```

1. `__future__` imports
2. Standard library (`logging`, `os`, `re`, `pathlib`)
3. Third-party (none explicitly in observed code)
4. Local imports (`from restaurant.*`)

**Order (TypeScript):**
```typescript
import { useEffect, useState } from 'react'
import '@livekit/components-styles'
import { useRoomContext } from '@livekit/components-react'
import type { OrderState } from '../lib/api'
import { OrderWithSierra } from './components/OrderWithSierra'
```

1. React/framework imports
2. CSS/style imports
3. Type imports (after `import` keyword)
4. Component/utility imports (relative paths)

**Path Aliases:**
- TypeScript imports use relative paths (`../lib/api`, `../components/`)
- No path aliases configured in tsconfig.json

## Error Handling

**Python Patterns:**
- Silent fallback with logging: `except Exception: logger.exception("message")`
- Example: `restaurant/menu_provider.py:46-48` catches load failures and falls back to static menu
- Graceful degradation typical: if Clover menu fails, use static fallback

**TypeScript Patterns:**
- Silent error suppression in event handlers: `catch { /* ignore */ }`
- Example: `web/src/App.tsx:14,23` ignores localStorage errors
- Promise rejection handling: `.catch(() => { /* handler or silent */ })`
- Error throwing for critical paths: `if (!resp.ok) throw new Error('Failed to get token')`
  - Used for auth failures (`web/src/lib/api.ts:78`)
  - Used for resource loading failures

**Error propagation:**
- Python: Exceptions propagate up; logged at catch points
- TypeScript: Errors in React event handlers typically swallowed; uncaught promise rejections not prevented

## Logging

**Framework:** Python uses standard `logging` module

**Patterns:**
- One logger per module: `logger = logging.getLogger("module-name")`
  - Examples: `"menu-provider"`, `"session-config"`, `"llm-warmup"`
- Three levels used:
  - `logger.info()` — initialization, successful operations (`"Loaded Clover menu cache: %d items"`)
  - `logger.warning()` — fallbacks, missing resources (`"Menu cache missing at %s"`)
  - `logger.exception()` — error cases with traceback (`"Failed to load Clover menu cache"`)
- No log-level filtering configuration detected; relies on root logger defaults

**TypeScript:** No logging framework used; only console available via browser

## Comments

**When to Comment:**
- Module docstrings (triple-quoted) explain context and PR references (e.g., `"""PR 032 — cross-script confidence menu matching + auto-add gate."""`)
- Inline comments clarify complex logic, especially with non-ASCII text or multi-step algorithms
- Example: `restaurant/customer_info.py:10` explains Indic numerals → ASCII conversion with a comment
- Function docstrings for public APIs; private functions often lack docstrings if purpose is clear from name and type hints

**JSDoc/TSDoc:**
- Python: No JSDoc; relies on type hints and docstrings
- TypeScript: Not consistently used; observed in React hooks but not required
  - Example: `web/src/hooks/useCart.tsx:17` uses JSDoc-style comments: `/** Latest order state from the agent, or null before the first sync. */`

## Function Design

**Size:** Functions are concise; most range 10–40 lines
- Example: `extract_phone_digits()` in `restaurant/customer_info.py` is ~15 lines
- Larger functions break into steps with helper functions (e.g., `menu_provider.py` uses `_strip_availability_phrases()`, `_item_candidates_from_text()`)

**Parameters:** 
- Python: Use of dataclasses (`@dataclass`) for grouped parameters (e.g., `CachedMenuItem`, `CartItem`)
- TypeScript: Props passed as single object destructured in function params (e.g., `function OrderPanel({ connected }: Props)`)
- Limit to 3–5 direct parameters; group related params

**Return Values:**
- Python: Type-hinted returns (e.g., `-> str | None`, `-> dict`, `-> tuple[str, list[dict]]`)
- TypeScript: Strongly typed (e.g., `Promise<CartRpcResult>`, `Promise<OrderState>`)
- Nullable returns common where data may not exist (e.g., `extract_phone_digits()` returns `None` if invalid)

## Module Design

**Exports:**
- Python: Public functions not prefixed with `_`; private helpers prefixed with `_`
- TypeScript: `export function` for public, no prefix convention for private (relies on file organization)
- React: Components exported as default or named export
  - Example: `export default function Layout()` in `admin/src/components/Layout.tsx`
  - Example: `export function OrderPanel()` in `web/src/components/OrderPanel.tsx`

**Barrel Files:**
- No barrel exports (`index.ts` re-exporting multiple modules) observed in web/admin
- Direct imports from specific files (e.g., `import { OrderWithSierra } from './components/OrderWithSierra'`)

---

*Convention analysis: 2026-07-14*
