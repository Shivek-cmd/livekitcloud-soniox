# PR Rules

These rules apply to every change made in this repo. No exceptions.

---

## Workflow

1. **Create the PR doc first** — before writing any code, create `pr/pr_NNN_<description>.md`
2. **Create the branch** — branch name must exactly match the PR doc filename (without `.md`)
   ```
   git checkout -b pr_002_add-web-frontend
   ```
3. **Write code on that branch** — never commit directly to `main`
4. **Update the PR doc as you go** — if you add/change/remove files during the PR, update the doc in the same commit
5. **Push the branch** — push to remote with the same branch name
6. **Merge to main via PR** — open a GitHub PR from the branch into `main`, then merge
7. **Never force-push main** — only exception is removing accidentally committed secrets

---

## PR Doc Format (`pr/pr_NNN_<description>.md`)

```
# PR NNN — <Title>

## Branch
`pr_NNN_<description>`

## What This PR Does
One paragraph summary.

## Files Added
### `filename.py`
What it does and key decisions.

## Files Modified
### `filename.py`
What changed and why.

## Files Deleted
List any deleted files.

## What's NOT in This PR
Scope boundaries — what was intentionally left out.

## How to Test
Commands to verify the change works.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
```

---

## Naming Convention

| Number | Format | Example |
|---|---|---|
| Branch | `pr_NNN_<kebab-case-description>` | `pr_002_add-web-frontend` |
| PR doc | `pr/pr_NNN_<kebab-case-description>.md` | `pr/pr_002_add-web-frontend.md` |

Numbers are sequential: 001, 002, 003...

---

## What Must NEVER Be Committed

- `.env` files (API keys, secrets)
- `.claude/` directory (contains MCP API keys)
- Any file containing credentials, tokens, or passwords
- Always check `.gitignore` includes these before committing

---

## Fixing Mistakes in an Open PR

If you find a bug or missing file after the branch is pushed:
1. Fix it on the **same branch**
2. Update the PR doc in the same commit to reflect the change
3. Push to the same branch — the PR updates automatically
4. Do NOT open a new PR for fixes to an open PR
