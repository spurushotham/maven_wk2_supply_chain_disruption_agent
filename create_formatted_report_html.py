from html import escape
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
source = ROOT / "supply_chain_project_report.txt"
output = ROOT / "supply_chain_project_report_formatted.html"

lines = source.read_text(encoding="utf-8").replace("â€™", "’").replace("â†’", "→").replace("â†“", "↓").replace("â†”", "↔").splitlines()

section_re = re.compile(r"^\d+\.\s+.+$")
subheads = {
    "Executive summary", "Core solution behavior", "Primary users and decisions",
    "Architecture components", "Ingestion and data preparation", "Data used for this problem",
    "Retrieval strategy", "Agentic process", "Frameworks and technologies",
    "Validation layers", "Known scenario examples", "Useful commands",
    "Security, privacy, and deployment considerations", "Current limitations and roadmap",
    "Repository map", "Conclusion", "Capability", "User", "Decision supported",
}

def p(text, cls=""):
    return f'<p class="{cls}">{escape(text)}</p>'

body = []
for i, line in enumerate(lines):
    if not line.strip():
        continue
    if i == 0:
        body.append(f'<h1>{escape(line)}</h1>')
    elif i == 1:
        body.append(f'<h2 class="subtitle">{escape(line)}</h2>')
    elif i == 2:
        body.append(p(line, "tagline"))
    elif section_re.match(line):
        body.append(f'<h2>{escape(line)}</h2>')
    elif line in subheads:
        body.append(f'<h3>{escape(line)}</h3>')
    elif line.startswith("Figure "):
        body.append(p(line, "caption"))
    elif line.startswith("uv ") or line.startswith("python ") or line.startswith("scripts/"):
        body.append(f'<p class="code">{escape(line)}</p>')
    elif line.startswith("Which ") or line.startswith("Whether ") or line.startswith("What is "):
        body.append(f'<p class="bullet">{escape(line)}</p>')
    else:
        body.append(p(line))

html = f'''<!doctype html><html><head><meta charset="utf-8"><style>
@page {{ size: Letter; margin: 0.7in; }}
body {{ font-family: Arial, sans-serif; color: #243447; line-height: 1.45; max-width: 760px; margin: 0 auto; }}
h1 {{ color: #174a70; font-size: 28pt; margin: 0 0 4pt; border-bottom: 3px solid #2f7da8; padding-bottom: 8pt; }}
h2 {{ color: #174a70; font-size: 17pt; margin-top: 22pt; border-bottom: 1px solid #b8cbd8; padding-bottom: 4pt; page-break-after: avoid; }}
h3 {{ color: #2f6f95; font-size: 12.5pt; margin-top: 15pt; page-break-after: avoid; }}
.subtitle {{ color: #5b6b7a; font-size: 17pt; border: 0; margin: 2pt 0; }}
.tagline {{ color: #657b8b; font-style: italic; margin-top: 3pt; }}
p {{ margin: 5pt 0 9pt; font-size: 10.5pt; }}
.bullet {{ margin-left: 18pt; }}
.bullet:before {{ content: "•  "; color: #2f7da8; font-weight: bold; }}
.code {{ font-family: Consolas, monospace; background: #f0f4f7; border-left: 4px solid #2f7da8; padding: 6pt 9pt; white-space: pre-wrap; }}
.caption {{ color: #5b6b7a; font-style: italic; text-align: center; font-size: 9pt; }}
</style></head><body>{''.join(body)}</body></html>'''
output.write_text(html, encoding="utf-8")
print(output)
