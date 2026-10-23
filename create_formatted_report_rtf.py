from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
src = ROOT / "supply_chain_project_report.txt"
out = ROOT / "supply_chain_project_report_formatted.rtf"
lines = src.read_text(encoding="utf-8").replace("â€™", "’").replace("â†’", "→").replace("â†“", "↓").replace("â†”", "↔").splitlines()

def rtf_text(s: str) -> str:
    result = []
    for ch in s:
        if ch == "\\": result.append(r"\\")
        elif ch == "{": result.append(r"\{")
        elif ch == "}": result.append(r"\}")
        elif ord(ch) < 128: result.append(ch)
        else:
            n = ord(ch)
            if n > 32767: n -= 65536
            result.append(f"\\u{n}?")
    return "".join(result)

section = re.compile(r"^\d+\.\s+.+$")
subheads = {"Executive summary", "Core solution behavior", "Primary users and decisions", "Architecture components", "Ingestion and data preparation", "Data used for this problem", "Retrieval strategy", "Agentic process", "Frameworks and technologies", "Validation layers", "Known scenario examples", "Useful commands", "Security, privacy, and deployment considerations", "Current limitations and roadmap", "Repository map", "Conclusion"}
out_parts = [r"{\rtf1\ansi\deff0{\fonttbl{\f0 Aptos;}{\f1 Consolas;}}\paperw12240\paperh15840\margl900\margr900\margt900\margb900\viewkind4"]
for i, line in enumerate(lines):
    if not line.strip():
        continue
    txt = rtf_text(line)
    if i == 0:
        out_parts.append(r"\pard\qc\sb0\sa100\f0\fs40\cf1\b " + txt + r"\b0\par")
    elif i == 1:
        out_parts.append(r"\pard\qc\sa80\f0\fs28\cf2 " + txt + r"\par")
    elif i == 2:
        out_parts.append(r"\pard\qc\sa240\i\f0\fs22\cf3 " + txt + r"\i0\par")
    elif section.match(line):
        out_parts.append(r"\pard\sb300\sa100\keepn\f0\fs28\cf1\b " + txt + r"\b0\par")
    elif line in subheads:
        out_parts.append(r"\pard\sb220\sa80\keepn\f0\fs23\cf2\b " + txt + r"\b0\par")
    elif line.startswith("uv ") or line.startswith("python ") or line.startswith("scripts/"):
        out_parts.append(r"\pard\li360\sb40\sa80\f1\fs18\highlight1 " + txt + r"\highlight0\par")
    elif line.startswith("Which ") or line.startswith("Whether ") or line.startswith("What is "):
        out_parts.append(r"\pard\li360\fi-180\sa60\f0\fs21 \u8226?  " + txt + r"\par")
    elif line.startswith("Figure "):
        out_parts.append(r"\pard\qc\sa120\i\f0\fs18\cf3 " + txt + r"\i0\par")
    else:
        out_parts.append(r"\pard\sa100\f0\fs21\cf0 " + txt + r"\par")
out_parts.append("}")
out.write_text("".join(out_parts), encoding="ascii")
print(out)
