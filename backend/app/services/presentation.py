# backend/app/services/presentation.py
import html
import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class PresentationBuilder:
    def build_html(self, title: str, slides: List[Dict[str, Any]]) -> str:
        """Build a self-contained HTML slide deck."""
        slide_html = []
        for i, slide in enumerate(slides, 1):
            heading = html.escape(slide.get("title", f"Slide {i}"))
            body_lines = slide.get("body", [])
            bullets = "".join(f"<li>{html.escape(str(b))}</li>" for b in body_lines)
            slide_html.append(f"""
    <section>
      <h2>{heading}</h2>
      <ul>{bullets}</ul>
    </section>""")
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 0; }}
  section {{ min-height: 100vh; padding: 5vh 8vw; box-sizing: border-box; }}
  section:nth-child(odd) {{ background: #0f172a; color: #f8fafc; }}
  section:nth-child(even) {{ background: #f8fafc; color: #0f172a; }}
  h2 {{ font-size: clamp(1.6rem, 4vw, 3rem); }}
  li {{ font-size: clamp(1rem, 2.2vw, 1.6rem); margin: .6em 0; }}
</style>
</head>
<body>
{''.join(slide_html)}
</body>
</html>"""

    def outline(self, topics: List[str]) -> List[Dict[str, Any]]:
        """Turn topics into a default slide outline."""
        return [{"title": t, "body": []} for t in topics]
