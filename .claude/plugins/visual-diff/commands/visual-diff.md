---
name: visual-diff
description: Run a visual diff comparison between documentation builds
arguments:
  - name: args
    description: "Optional arguments: --mode pantheon|pr, --title FILTER, --output DIR, --headless, --env-a URL, --env-b URL"
    required: false
---

Run the visual-diff tool to compare documentation builds.

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/visual-diff diff --headless --output /tmp/visual-diff-output/ $ARGUMENTS
```

After running, read the output report at `/tmp/visual-diff-output/index.html` and provide a summary of the changes found.
