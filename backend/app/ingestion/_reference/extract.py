"""RapidOCR boxes + geometry -> rows.json. Usage: extract.py BENCH_DIR  (OCR on crops/<id>@2x.png)"""
import sys, re, json, cv2, numpy as np
from rapidocr_onnxruntime import RapidOCR

B = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else "rows.json"
ocr = RapidOCR()

STD = ["onoff_torque_in_lbs","onoff_torque_nm","onoff_duty_cycle_pct","cycles_per_hour","mod_torque_in_lbs",
       "mod_torque_nm","mod_duty_cycle_pct","starts_per_hour","speed_sec_60hz","speed_sec_50hz",
       "fla_60hz_a","fla_50hz_a","lra_60hz_a","lra_50hz_a"]
META = {
 "T1_wp_110v_1ph": ("weatherproof","CSA, CE, & UKCA","110V","AC",1,"on_off_and_modulating",STD),
 "T2_wp_220v_1ph": ("weatherproof","CSA, CE, & UKCA","220V","AC",1,"on_off_and_modulating",STD),
 "T3_wp_220v_3ph": ("weatherproof","CSA, CE, & UKCA","220V","AC",3,"unspecified",
   ["output_torque_in_lbs","output_torque_nm","duty_cycle_pct","cycles_per_hour","starts_per_hour","speed_sec_60hz",
    "speed_sec_50hz","fla_60hz_a","fla_50hz_a","lra_60hz_a","lra_50hz_a"]),
 "T4_xp_24v_onoff": ("explosionproof","CSA","24V AC/DC","AC/DC",None,"on_off",
   ["onoff_torque_in_lbs","onoff_torque_nm","onoff_duty_cycle_pct","cycles_per_hour","speed_sec","fla_a","lra_a"]),
 "T5_xp_24vdc_mod": ("explosionproof","CSA","24V DC","DC",None,"modulating",
   ["mod_torque_in_lbs","mod_torque_nm","mod_duty_cycle_pct","starts_per_hour","speed_sec","fla_a","lra_a"]),
 "T6_xp_110v_1ph": ("explosionproof","CSA","110V","AC",1,"on_off_and_modulating",STD),
 "T7_xp_220v_1ph": ("explosionproof","CSA","220V","AC",1,"on_off_and_modulating",STD),
}
INT_FIELDS = {"onoff_torque_in_lbs","onoff_torque_nm","mod_torque_in_lbs","mod_torque_nm","output_torque_in_lbs","output_torque_nm"}
PN = re.compile(r"\d{3}[A-Z0-9]{3}-[A-Z0-9]{6,9}/?[A-Z]?\*?$")

def parse_num(field, raw):
    t = raw.strip().replace(" ", "")
    if re.fullmatch(r"N/?A", t, re.I): return None, None
    t = t.replace("O", "0").replace("o", "0")
    if field in INT_FIELDS and re.fullmatch(r"\d{1,2}[.,]\d{3}", t):  # OCR often reads thousands comma as '.'
        t = t.replace(".", "").replace(",", "")
    elif re.fullmatch(r"\d{1,3}(,\d{3})+", t): t = t.replace(",", "")
    if re.fullmatch(r"\d+(\.\d+)?", t): return float(t) if "." in t else int(t), None
    return None, raw

def split_gaps(vals, n):
    v = sorted(vals); gaps = sorted(range(len(v)-1), key=lambda i: v[i+1]-v[i], reverse=True)[:n-1]
    cuts = sorted((v[i]+v[i+1])/2 for i in gaps); return cuts

rows_out = []; log = {}; refills = []; cell_log = []  # cell_log: raw text + min OCR confidence per cell, for flag_cells.py
for tid, (enc, cert, volt, cur, ph, svc, fields) in META.items():
    img_path = f"{B}/inputs/crops/{tid}@2x.png"
    res, _ = ocr(img_path)
    boxes = [dict(x0=b[0][0], y0=b[0][1], x1=b[2][0], y1=b[2][1], t=t, c=float(c)) for b, t, c in res]
    for b in boxes: b["cx"] = (b["x0"]+b["x1"])/2; b["cy"] = (b["y0"]+b["y1"])/2
    pns = sorted([b for b in boxes if PN.search(b["t"].replace(" ", ""))], key=lambda b: b["cy"])
    pn_right = max(b["x1"] for b in pns)
    # motor power column from header word "Motor"/"Watts"
    mh = [b for b in boxes if b["t"] in ("Motor", "Watts", "Power") and b["cx"] > pn_right]
    mx0 = min(b["x0"] for b in mh); mx1 = max(b["x1"] for b in mh)
    data = [b for b in boxes if b["x0"] > pn_right and b["cy"] > pns[0]["cy"]-25 and b["cx"] < mx0-10]
    pitch = np.median(np.diff([p["cy"] for p in pns]))
    # column clustering
    cuts = split_gaps([b["cx"] for b in data if re.search(r"\d|N/?A", b["t"])], len(fields))
    def col(b): return sum(b["cx"] > c for c in cuts)
    # motor-power groups from horizontal rules in the motor column strip
    g = cv2.imread(img_path, 0); sx0 = int(mx0)-15; sx1 = int(mx1)+15
    strip = g[:, sx0:sx1]
    frac = (strip < 225).mean(1)
    ys = [y for y in range(int(pns[0]["cy"]-pitch), g.shape[0]) if frac[y] > 0.8]
    lines = []
    for y in ys:
        if lines and y - lines[-1][-1] <= 2: lines[-1].append(y)
        else: lines.append([y])
    lines = [np.mean(l) for l in lines if len(l) <= 6]
    lines = [l for l in lines if l > pns[0]["cy"]-pitch/2]
    bounds = lines
    def group_of(y): return sum(y > l for l in bounds)
    power = [b for b in boxes if b["cx"] > mx0-10 and b["cy"] > pns[0]["cy"]-pitch/2 and b["t"] not in ("Watts",)]
    gp = {}
    for b in power: gp.setdefault(group_of(b["cy"]), []).append(b)
    log[tid] = dict(rows=len(pns), cuts=[round(c) for c in cuts], rules=[round(l) for l in bounds], pitch=round(float(pitch)))
    for i, p in enumerate(pns):
        raw = p["t"].replace(" ", ""); star = raw.endswith("*") or "*" in raw
        pn = raw.replace("*", "")
        pn = re.sub(r"(?<=-)[A-Z0-9]+(?=/)", lambda m: m.group(0).replace("O", "0"), pn)
        row = dict(table_id=tid, part_number=pn, csa_certified=not star, enclosure=enc, certifications=cert, voltage=volt,
                   current_type=cur, phase=ph, service=svc)
        for f in ["onoff_torque_in_lbs","onoff_torque_nm","onoff_duty_cycle_pct","cycles_per_hour","mod_torque_in_lbs","mod_torque_nm",
                  "mod_duty_cycle_pct","starts_per_hour","output_torque_in_lbs","output_torque_nm","duty_cycle_pct","speed_sec_60hz",
                  "speed_sec_50hz","speed_sec","fla_60hz_a","fla_50hz_a","fla_a","lra_60hz_a","lra_50hz_a","lra_a","motor_power_w"]:
            row[f] = None
        row["row_index"] = i+1; row["unparsed"] = {}
        # cells for this row: nearest part-number row within 0.5 pitch (or N/A boxes spanning)
        cells = {}
        for b in data:
            if abs(b["cy"]-p["cy"]) <= pitch*0.5 and not b["t"].endswith("/A") and b is not p:
                cells.setdefault(col(b), []).append(b)
        for ci, f in enumerate(fields):
            bs = sorted(cells.get(ci, []), key=lambda b: b["x0"]); refilled = False
            if not bs:
                allempty = not any(cells.get(k) for k in range(len(fields)))
                if allempty: continue  # whole row is an N/A block
                lo = cuts[ci-1] if ci > 0 else (pn_right+5); hi = cuts[ci] if ci < len(cuts) else (mx0-12)
                y0 = int(p["cy"]-pitch*0.45); y1 = int(p["cy"]+pitch*0.45)
                crop = cv2.copyMakeBorder(g[max(y0,0):y1, int(lo):int(hi)], 20, 20, 30, 30, cv2.BORDER_CONSTANT, value=255)
                crop = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
                r2, _ = ocr(cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR))
                if not r2: continue
                bs = [dict(t=" ".join(t for _, t, _ in r2), x0=0, c=min(float(c) for _, _, c in r2))]
                refills.append((tid, i+1, f, bs[0]["t"])); refilled = True
            raw = " ".join(b["t"] for b in bs)
            v, un = parse_num(f, raw)
            row[f] = v
            if un is not None: row["unparsed"][f] = un
            cell_log.append(dict(table_id=tid, part_number=pn, field=f, raw=raw, conf=min(b["c"] for b in bs), refill=refilled))
        # power
        pb = gp.get(group_of(p["cy"]), [])
        if pb:
            raw = " ".join(b["t"] for b in pb); v, un = parse_num("motor_power_w", raw)
            row["motor_power_w"] = v
            if un is not None: row["unparsed"]["motor_power_w"] = un
            cell_log.append(dict(table_id=tid, part_number=pn, field="motor_power_w", raw=raw,
                                 conf=min(b["c"] for b in pb), refill=False))
        rows_out.append(row)
json.dump({"candidate": "E_paddle_rapidocr", "run": 1, "rows": rows_out}, open(OUT, "w"), indent=1)
json.dump(cell_log, open("cells.json", "w"), indent=1)
log["refills"] = refills
json.dump(log, open("geom_log.json", "w"), indent=1)
print(json.dumps(log))
