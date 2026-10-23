from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
lines = (ROOT / "supply_chain_project_report.txt").read_text(encoding="utf-8").replace("â€™", "’").replace("â†’", "→").replace("â†“", "↓").replace("â†”", "↔").splitlines()
out = ROOT / "supply_chain_project_report_tables.rtf"

def esc(s):
    o=[]
    for ch in s:
        if ch == "\\": o.append(r"\\")
        elif ch == "{": o.append(r"\{")
        elif ch == "}": o.append(r"\}")
        elif ord(ch) < 128: o.append(ch)
        else:
            n=ord(ch); n=n-65536 if n>32767 else n; o.append(f"\\u{n}?")
    return ''.join(o)

def para(s, size=21, color=0, after=100, bold=False, italic=False, left=0, first=0):
    flags = (r"\b" if bold else "") + (r"\i" if italic else "")
    end = (r"\i0" if italic else "") + (r"\b0" if bold else "")
    return f"\\pard\\li{left}\\fi{first}\\sa{after}\\f0\\fs{size}\\cf{color} {flags}{esc(s)}{end}\\par"

def table(rows, widths, header=True):
    result=[]
    for ri,row in enumerate(rows):
        result.append(r"\trowd\trgaph90\trleft0")
        total=0
        for w in widths:
            total += w; result.append(f"\\cellx{total}")
        for ci,value in enumerate(row):
            if ri==0 and header:
                result.append(r"\clcbpat2\clvertalt\pard\intbl\sa50\f0\fs18\cf4\b " + esc(str(value)) + r"\b0\cell")
            else:
                shade = r"\clcbpat3" if ri % 2 == 0 else r"\clcbpat1"
                result.append(shade + r"\clvertalt\pard\intbl\sa50\f0\fs18\cf0 " + esc(str(value)) + r"\cell")
        result.append(r"\row")
    return ''.join(result) + r"\pard\sa100\par"

def heading(s, level=1):
    if level == 1:
        return r"\pard\sb300\sa120\keepn\f0\fs28\cf1\b " + esc(s) + r"\b0\par"
    return r"\pard\sb220\sa80\keepn\f0\fs23\cf2\b " + esc(s) + r"\b0\par"

def is_section(s): return bool(re.match(r"^\d+\.\s+", s))

def take_table(i, headers, ncols, stop):
    rows=[headers]; i += 1
    values=[]
    while i < len(lines) and not stop(lines[i]):
        if lines[i].strip(): values.append(lines[i].strip())
        i += 1
    for j in range(0, len(values)-ncols+1, ncols): rows.append(values[j:j+ncols])
    return i, table(rows, [2300, 4100, 4000][:ncols])

rtf=[r"{\rtf1\ansi\deff0{\fonttbl{\f0 Aptos;}{\f1 Consolas;}}{\colortbl;\red255\green255\blue255;\red31\green78\blue121;\red234\green242\blue248;\red255\green255\blue255;\red36\green52\blue71;}\paperw12240\paperh15840\margl720\margr720\margt720\margb720\viewkind4"]
i=0
while i < len(lines):
    s=lines[i].strip()
    if not s: i+=1; continue
    if i==0:
        rtf.append(r"\pard\qc\sb0\sa80\f0\fs42\cf1\b " + esc(s) + r"\b0\par")
    elif i==1:
        rtf.append(r"\pard\qc\sa50\f0\fs29\cf2 " + esc(s) + r"\par")
    elif i==2:
        rtf.append(r"\pard\qc\sa220\i\f0\fs21\cf2 " + esc(s) + r"\i0\par")
    elif is_section(s):
        if s.startswith(("4.","7.","10.","12.")): rtf.append(r"\page")
        rtf.append(heading(s,1))
    elif s in {"Executive summary","Core solution behavior","Primary users and decisions","Architecture components","Ingestion and data preparation","Data used for this problem","Retrieval stages","Why the strategy is hybrid","Follow-up behavior","Reasoning policy","Tool inventory","Guardrails and failure modes","Validation layers","Known scenario examples","Useful commands","Repository map","Conclusion"} or re.match(r"^\d+\.\d+\s+",s):
        rtf.append(heading(s,2))
    elif s == "Capability":
        i,chunk=take_table(i,["Capability","Implemented behavior"],2,lambda x:is_section(x))
        rtf.append(chunk); continue
    elif s == "User":
        i,chunk=take_table(i,["User","Decision supported"],2,lambda x:is_section(x))
        rtf.append(chunk); continue
    elif s == "Layer":
        i,chunk=take_table(i,["Layer","Component","Responsibility"],3,lambda x:x=="4. Data used for this problem")
        rtf.append(chunk); continue
    elif s == "Record group":
        i,chunk=take_table(i,["Record group","Count","Examples / meaning"],3,lambda x:is_section(x))
        rtf.append(chunk); continue
    elif s == "Stage":
        i,chunk=take_table(i,["Stage","Mechanism","Why it matters"],3,lambda x:x=="Why the strategy is hybrid")
        rtf.append(chunk); continue
    elif s == "Tool":
        i,chunk=take_table(i,["Tool","Purpose"],2,lambda x:x=="8.4 Guardrails and failure modes")
        rtf.append(chunk); continue
    elif s == "Technology":
        i,chunk=take_table(i,["Technology","Role in project"],2,lambda x:is_section(x))
        rtf.append(chunk); continue
    elif s in {"Scenario","Command","Current boundary","Path"}:
        headers=[s, {"Scenario":"Expected behavior","Command":"Purpose","Current boundary":"Recommended next step","Path":"Purpose"}[s]]
        i,chunk=take_table(i,headers,2,lambda x:is_section(x))
        rtf.append(chunk); continue
    elif s.startswith("Figure "):
        rtf.append(para(s,18,2,120,italic=True)); i+=1; continue
    elif s.startswith(("uv ","python ","scripts/")):
        rtf.append(r"\pard\li360\sa70\f1\fs18\highlight2 " + esc(s) + r"\highlight0\par")
    elif s.startswith(("Which ","Whether ","What is ")):
        rtf.append(para("•  "+s,21,0,60,left=360,first=-180))
    else:
        rtf.append(para(s))
    i += 1

rtf.append("}")
out.write_text(''.join(rtf), encoding='ascii')
print(out)
