# Tools module layout

- `read_tools.py` — read-only tools (list/get/insights)
- Future:
  - `write_tools.py` — create/update/delete tools (keep disabled by default)
  - `upload_tools.py` — media uploads (keep disabled by default)

Guideline: group tools by capability, and register them from `main.py`.
