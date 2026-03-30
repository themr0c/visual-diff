---
name: visual-diff
description: Run a visual diff and summarise changes
argument-hint: "[--mode pantheon|pr] [--title FILTER] [--output DIR] [--env-a URL] [--env-b URL]"
---

Run the visual-diff tool then summarise what changed.

```bash
scripts/visual-diff diff --output reports/ $ARGUMENTS
```

After the command completes, read `reports/summary.md` and provide a plain-language summary: how many pages changed, which books were affected, any renames or structural splits detected.
