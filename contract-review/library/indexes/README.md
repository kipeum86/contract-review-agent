# Local Library Indexes

This directory is reserved for generated local index files.

The JSON files produced here may contain clause text or metadata derived from
locally ingested library assets, so they are intentionally ignored by git.
Rebuild them from approved local assets when needed:

```bash
python3 .claude/skills/index-manager/scripts/build-index.py rebuild
```
