#!/usr/bin/env python3
"""Convert REPORT.md to a readable UTF-8 PDF."""

from pathlib import Path

import markdown
from weasyprint import HTML


def main() -> None:
    base_dir = Path(__file__).resolve().parents[1]
    md_path = base_dir / "REPORT.md"
    pdf_path = base_dir / "REPORT.pdf"

    md_content = md_path.read_text(encoding="utf-8")
    html_body = markdown.markdown(
        md_content,
        extensions=["tables", "fenced_code", "toc"],
    )

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Lab 5 Protocol: Microservices with Consul</title>
  <style>
    @page {{ size: A4; margin: 16mm; }}
    body {{
      font-family: "DejaVu Sans", "Noto Sans", Arial, sans-serif;
      font-size: 10.5pt;
      line-height: 1.42;
      color: #1f2937;
    }}
    h1, h2, h3 {{ color: #0f3d91; page-break-after: avoid; }}
    h1 {{ border-bottom: 2px solid #0f3d91; padding-bottom: 6px; }}
    p, li {{ orphans: 3; widows: 3; }}
    table {{ width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 9pt; }}
    th, td {{ border: 1px solid #9ca3af; padding: 5px; vertical-align: top; }}
    th {{ background: #e5edff; }}
    code {{ font-family: "DejaVu Sans Mono", "Courier New", monospace; font-size: 0.92em; }}
    pre {{
      background: #f6f8fa;
      border: 1px solid #d0d7de;
      padding: 8px;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 8.5pt;
      page-break-inside: avoid;
    }}
    a {{ color: #0f3d91; }}
  </style>
</head>
<body>
{html_body}
</body>
</html>"""

    HTML(string=html_doc, base_url=str(base_dir)).write_pdf(str(pdf_path))
    print(f"OK: {pdf_path} ({pdf_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()

