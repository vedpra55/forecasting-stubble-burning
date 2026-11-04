# Test-season access log

Test seasons: **2025, 2026** (configs/seasons.yaml). Rule 5 in CLAUDE.md: touch them only in
Phase 6, once per final candidate, and log every touch here.

| Date | Phase | What was accessed | Why | Data read? |
|---|---|---|---|---|
| 2026-11-04 | 1 | HTTP HEAD on FIRMS yearly India CSV URLs for 2025/2026 (all sensors) | Check whether files exist and when they were last modified, for pipeline planning | No: headers only, no rows downloaded |
