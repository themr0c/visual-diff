---
name: visual-diff-urls
description: List available documentation title URLs from both environments
arguments:
  - name: args
    description: "Optional arguments: --mode pantheon|pr, --title FILTER, --json"
    required: false
---

List the documentation titles available for comparison.

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/visual-diff urls $ARGUMENTS
```
