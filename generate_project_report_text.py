from pathlib import Path
import xml.etree.ElementTree as ET
from generate_project_report import build_body

ROOT = Path(__file__).resolve().parent
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
xml = '<root xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">' + build_body() + '</root>'
root = ET.fromstring(xml)
lines = []
for p in root.findall('.//w:p', NS):
    text = ''.join(t.text or '' for t in p.findall('.//w:t', NS)).strip()
    if text:
        lines.append(text)
Path(ROOT / 'supply_chain_project_report.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(ROOT / 'supply_chain_project_report.txt')
