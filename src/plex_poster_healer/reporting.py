from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Template

from plex_poster_healer.models import ScanRecord

HTML_TEMPLATE = Template(
    """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Plex Poster Healer Report</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 2rem; background: #f5f5f5; color: #222; }
    table { width: 100%; border-collapse: collapse; background: white; }
    th, td { padding: 0.75rem; border-bottom: 1px solid #ddd; vertical-align: top; }
    th { text-align: left; background: #111; color: white; }
    code { background: #eee; padding: 0.1rem 0.3rem; }
  </style>
</head>
<body>
  <h1>Plex Poster Healer Report</h1>
  <p>Generated at {{ generated_at }}</p>
  <table>
    <thead>
      <tr>
        <th>Title</th>
        <th>Library</th>
        <th>Type</th>
        <th>Status</th>
        <th>Failure Reason</th>
        <th>Replacement</th>
      </tr>
    </thead>
    <tbody>
      {% for row in rows %}
      <tr>
        <td>{{ row.title }}</td>
        <td>{{ row.library }}</td>
        <td>{{ row.item_type }}</td>
        <td>{{ row.status }}</td>
        <td>{{ ", ".join(row.reasons) }}</td>
        <td>{{ row.replacement_source or "n/a" }}{% if row.replacement_path %}<br><code>{{ row.replacement_path }}</code>{% endif %}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</body>
</html>"""
)


class ReportWriter:
    def __init__(self, reports_dir: Path) -> None:
        self.reports_dir = reports_dir

    def write(self, action: str, rows: list[ScanRecord]) -> tuple[Path, Path]:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        json_path = self.reports_dir / f"{action}-{stamp}.json"
        html_path = self.reports_dir / f"{action}-{stamp}.html"
        payload = {
            "generated_at": stamp,
            "action": action,
            "items": [asdict(row) for row in rows],
        }
        json_path.write_text(json.dumps(payload, indent=2))
        html_path.write_text(
            HTML_TEMPLATE.render(generated_at=stamp, rows=rows),
            encoding="utf-8",
        )
        return json_path, html_path

