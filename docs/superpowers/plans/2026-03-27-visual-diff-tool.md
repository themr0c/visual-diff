# Visual Diff Tool — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap the existing `visual-diff` CLI as a Claude Code plugin (agent + slash commands) and a GitHub Action that posts PR diff comments automatically.

**Architecture:** Phase 4 adds `.claude/plugins/visual-diff/` with a plugin manifest, an agent that invokes the CLI and summarises findings, and two slash commands (`/visual-diff`, `/visual-diff-urls`). Phase 5 adds `action/action.yml` (composite GitHub Action) that mirrors the `diff --mode pr` flow and posts `summary.md` as a PR comment.

**Tech Stack:** Claude Code plugin format (JSON + Markdown), GitHub Actions composite action (YAML), `gh` CLI for PR comments.

**Spec:** `docs/superpowers/specs/2026-03-27-visual-diff-tool-design.md`

**Completed phases (do not re-implement):** Phases 1–3 are done. The CLI is fully functional with `fetch`, `compare`, `diff`, and `urls` commands. Cache is in `.cache/before/` and `.cache/after/`. Reports go to `reports/` by default.

---

## Status

| Phase | Description | Status |
| ----- | ----------- | ------ |
| 1 | Migration + self-bootstrapping | Done |
| 2 | Parallel fetch + two-phase CLI + content-only diff | Done |
| 3 | Rename/split detection + self-contained HTML report | Done |
| 4 | Claude plugin (agent + commands) | Done |
| 5 | GitHub Action for PR comments | **Next** |

---

## Files to create

```
.claude/plugins/visual-diff/
├── plugin.json                       # Plugin manifest (canonical copy)
├── agents/
│   └── visual-diff-agent.md          # Agent definition
└── commands/
    ├── visual-diff.md                # /visual-diff command
    └── visual-diff-urls.md           # /visual-diff-urls command

.claude/                              # Auto-discovered by Claude Code
├── agents/
│   └── visual-diff-agent.md          # Symlinked/copied — enables agent
└── commands/
    ├── visual-diff.md                # Enables /visual-diff slash command
    └── visual-diff-urls.md           # Enables /visual-diff-urls slash command

action/
├── action.yml                        # Composite GitHub Action
└── example-workflow.yml              # Reference workflow (not deployed here)
```

> **Note (Phase 4 as implemented):** Claude Code's plugin loading system requires explicit installation. For project-local use, components were also placed in `.claude/commands/` and `.claude/agents/` which Claude Code auto-discovers. The `.claude/plugins/visual-diff/` copy serves as canonical source. Agent frontmatter uses `model: inherit` and `color: yellow` (not `orange`) and `argument-hint:` string (not `arguments:` list).

---

## Phase 4: Claude Plugin

### Task 1: Plugin manifest

**Files:**

- Create: `.claude/plugins/visual-diff/plugin.json`

- [x] **Step 1: Create directory structure**

```bash
mkdir -p .claude/plugins/visual-diff/agents
mkdir -p .claude/plugins/visual-diff/commands
```

- [x] **Step 2: Write plugin.json**

```json
{
  "name": "visual-diff",
  "description": "Visual regression testing for Red Hat documentation builds. Compares Pantheon stage/preview or arbitrary builds and generates side-by-side diff reports.",
  "agents": ["agents/visual-diff-agent.md"],
  "commands": ["commands/visual-diff.md", "commands/visual-diff-urls.md"]
}
```

- [x] **Step 3: Verify JSON is valid**

```bash
python3 -c "import json; json.load(open('.claude/plugins/visual-diff/plugin.json')); print('OK')"
```

Expected: `OK`

- [x] **Step 4: Commit**

```bash
git add .claude/plugins/visual-diff/plugin.json
git commit -m "feat: add Claude plugin manifest"
```

---

### Task 2: Agent definition

**Files:**

- Create: `.claude/plugins/visual-diff/agents/visual-diff-agent.md`

- [x] **Step 1: Write the agent**

````markdown
---
name: visual-diff-agent
description: Runs visual regression comparisons between documentation builds. Use when the user asks to compare documentation versions, run a visual diff, check for visual regressions, or compare Pantheon stage vs preview builds.
color: orange
tools:
  - Bash
  - Read
  - Glob
  - Grep
---

You are a visual diff specialist for Red Hat documentation. Your job is to run visual comparisons between documentation builds and summarise the results in plain language.

## Running the tool

The CLI is at `scripts/visual-diff` (relative to the repo root). It is self-bootstrapping — running it directly handles the venv.

Default (Pantheon stage vs preview, requires VPN):

```bash
scripts/visual-diff diff --output reports/
```

With a title filter:

```bash
scripts/visual-diff diff --output reports/ --title "audit"
```

PR mode (two arbitrary builds, no VPN needed):

```bash
scripts/visual-diff diff --mode pr --env-a PATH_OR_URL --env-b PATH_OR_URL --output reports/
```

## After running

Read `reports/summary.md` and report:

1. Counts: changed / renamed / split / new / removed / identical
2. Which books were affected (title names)
3. Any structural changes (splits and renames are especially notable)
4. For changed pages, note the change percentage if high (>20%)

Do NOT try to render or open `reports/index.html` in a browser. Read `reports/summary.md` — it has everything needed for a plain-language summary.

## Rules

- Always use `--output reports/` unless the user specifies otherwise
- If the user mentions specific book titles, add `--title "keyword"` (repeatable)
- If the user asks for a URL list instead of a diff, run `scripts/visual-diff urls` instead
````

- [x] **Step 2: Verify the file is valid Markdown with correct frontmatter**

```bash
python3 -c "
content = open('.claude/plugins/visual-diff/agents/visual-diff-agent.md').read()
assert content.startswith('---'), 'Missing frontmatter'
assert 'name: visual-diff-agent' in content, 'Missing name'
assert 'tools:' in content, 'Missing tools'
print('OK')
"
```

Expected: `OK`

- [x] **Step 3: Commit**

```bash
git add .claude/plugins/visual-diff/agents/visual-diff-agent.md
git commit -m "feat: add visual-diff Claude agent"
```

---

### Task 3: Slash commands

**Files:**

- Create: `.claude/plugins/visual-diff/commands/visual-diff.md`
- Create: `.claude/plugins/visual-diff/commands/visual-diff-urls.md`

- [x] **Step 1: Write /visual-diff command**

````markdown
---
name: visual-diff
description: Run a visual diff comparison between documentation builds and summarise the results
arguments:
  - name: args
    description: "Optional: --mode pantheon|pr, --title FILTER, --output DIR, --env-a URL, --env-b URL"
    required: false
---

Run the visual-diff tool then summarise what changed.

```bash
scripts/visual-diff diff --output reports/ $ARGUMENTS
```

After the command completes, read `reports/summary.md` and provide a plain-language summary: how many pages changed, which books were affected, any renames or structural splits detected.
````

- [x] **Step 2: Write /visual-diff-urls command**

````markdown
---
name: visual-diff-urls
description: List available documentation title URLs from both environments
arguments:
  - name: args
    description: "Optional: --mode pantheon|pr, --title FILTER, --json, --env-a URL, --env-b URL"
    required: false
---

List the documentation titles available for comparison.

```bash
scripts/visual-diff urls $ARGUMENTS
```
````

- [x] **Step 3: Verify both files exist and have frontmatter**

```bash
python3 -c "
for f in ['.claude/plugins/visual-diff/commands/visual-diff.md',
          '.claude/plugins/visual-diff/commands/visual-diff-urls.md']:
    content = open(f).read()
    assert content.startswith('---'), f'{f}: missing frontmatter'
    assert 'name:' in content, f'{f}: missing name'
    print(f, 'OK')
"
```

Expected: both files print `OK`

- [x] **Step 4: Verify full plugin structure**

```bash
find .claude/plugins/visual-diff -type f | sort
```

Expected:

```text
.claude/plugins/visual-diff/agents/visual-diff-agent.md
.claude/plugins/visual-diff/commands/visual-diff-urls.md
.claude/plugins/visual-diff/commands/visual-diff.md
.claude/plugins/visual-diff/plugin.json
```

- [x] **Step 5: Commit**

```bash
git add .claude/plugins/visual-diff/commands/
git commit -m "feat: add /visual-diff and /visual-diff-urls slash commands"
```

---

## Phase 5: GitHub Action

### Task 4: Action definition

**Files:**

- Create: `action/action.yml`

- [ ] **Step 1: Create action directory**

```bash
mkdir -p action
```

- [ ] **Step 2: Write action.yml**

```yaml
name: 'Visual Diff'
description: 'Compare documentation builds visually and post results as PR comment'

inputs:
  github-token:
    description: 'GitHub token for posting PR comments'
    required: true
  output-dir:
    description: 'Output directory for diff results'
    required: false
    default: '/tmp/visual-diff-output'

runs:
  using: 'composite'
  steps:
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.12'

    - name: Install dependencies
      shell: bash
      run: |
        pip install -q -r ${{ github.action_path }}/../requirements.txt
        ${{ github.action_path }}/../venv/bin/playwright install chromium
      env:
        PLAYWRIGHT_BROWSERS_PATH: /tmp/pw-browsers

    - name: Run visual diff
      shell: bash
      run: |
        python ${{ github.action_path }}/../scripts/visual-diff diff \
          --mode pr \
          --output ${{ inputs.output-dir }}
      env:
        GITHUB_BASE_REF: ${{ github.base_ref }}
        GITHUB_EVENT_NUMBER: ${{ github.event.number }}
        PLAYWRIGHT_BROWSERS_PATH: /tmp/pw-browsers

    - name: Post PR comment
      if: github.event_name == 'pull_request' || github.event_name == 'pull_request_target'
      shell: bash
      run: |
        SUMMARY="${{ inputs.output-dir }}/summary.md"
        if [ ! -f "$SUMMARY" ]; then
          echo "No summary.md found — skipping comment."
          exit 0
        fi
        gh pr comment ${{ github.event.number }} \
          --repo ${{ github.repository }} \
          --body-file "$SUMMARY"
      env:
        GH_TOKEN: ${{ inputs.github-token }}
```

- [ ] **Step 3: Validate YAML syntax**

```bash
python3 -c "import yaml; yaml.safe_load(open('action/action.yml')); print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add action/action.yml
git commit -m "feat: add GitHub Action for visual diff PR comments"
```

---

### Task 5: Example workflow

**Files:**

- Create: `action/example-workflow.yml`

This is a reference file to copy into `red-hat-developers-documentation-rhdh/.github/workflows/`. It is not deployed in this repo.

- [ ] **Step 1: Write example-workflow.yml**

```yaml
# Reference workflow — copy to .github/workflows/visual-diff.yml in the docs repo.
name: Visual Diff

on:
  pull_request_target:
    branches: [main, 'rhdh-1.**', 'release-1.**']

concurrency:
  group: visual-diff-${{ github.event.number }}
  cancel-in-progress: true

jobs:
  visual-diff:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
    steps:
      - name: Checkout PR content
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.ref }}
          repository: ${{ github.event.pull_request.head.repo.full_name }}

      - name: Checkout trusted build scripts from base branch
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.base.ref }}
          path: trusted-scripts
          sparse-checkout: build/scripts

      - name: Build PR docs
        run: trusted-scripts/build/scripts/build-ccutil.sh -b "pr-${{ github.event.number }}"

      - name: Run visual diff and post comment
        uses: themr0c/visual-diff@main
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

- [ ] **Step 2: Validate YAML syntax**

```bash
python3 -c "import yaml; yaml.safe_load(open('action/example-workflow.yml')); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add action/example-workflow.yml
git commit -m "docs: add example GitHub Actions workflow for visual diff"
```

---

## Self-review

**Spec coverage:**

| Spec requirement | Task |
| ---------------- | ---- |
| Plugin manifest with name, description, agents, commands | Task 1 |
| Agent triggers, tools, runs CLI, summarises report | Task 2 |
| `/visual-diff` command runs `diff` with args | Task 3 |
| `/visual-diff-urls` command runs `urls` with args | Task 3 |
| Composite GitHub Action with Python setup, playwright, diff run, PR comment | Task 4 |
| Example workflow using `pull_request_target` + trusted build scripts | Task 5 |

All spec requirements are covered. No placeholders present.
