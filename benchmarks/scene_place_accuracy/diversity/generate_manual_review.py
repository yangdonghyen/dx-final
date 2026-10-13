"""Generate a local, human-only review page without changing the dataset."""
import csv
import hashlib
import html
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
WARN = {"DIV029", "DIV046", "DIV056", "DIV060", "DIV064", "DIV086", "DIV098"}

def text(value):
    return html.escape(str(value or ""))

def main():
    candidates=[]
    for line in (BASE / "manual_review_candidates.txt").read_text(encoding="utf-8").splitlines():
        if line.strip(): candidates.append(line.split("\t", 1)[0])
    places=json.loads((BASE / "places.json").read_text(encoding="utf-8"))
    manifest={r["image_id"]: r for r in csv.DictReader((BASE / "manifest.csv").open(encoding="utf-8-sig", newline=""))}
    sources={r["image_id"]: r for r in csv.DictReader((BASE / "sources.csv").open(encoding="utf-8-sig", newline=""))}
    hashes=[r["sha256"] for r in sources.values()]
    places_hash=hashlib.sha256((BASE / "places.json").read_bytes()).hexdigest()
    cards=[]
    for image_id in candidates:
        row, source=manifest[image_id], sources[image_id]
        place=places[row["place_id"]]
        en=place.get("canonical_name_en") or next((x for x in place["accepted_names"] if any("a" <= c.lower() <= "z" for c in x)), "")
        category=source.get("categories", "")
        warning = "<div class='warning'>⚠ Human review priority: possible secondary/ambiguous subject in metadata.</div>" if image_id in WARN else ""
        cards.append(f"""<article class='card'>
<h2>{text(image_id)} <span>{text(row['place_id'])}</span></h2>{warning}
<img src='{text(row['image_path'])}' alt='Manual review image {text(image_id)}' loading='lazy'>
<dl>
<dt>한국어 장소명</dt><dd>{text(place['detail_name'])}</dd>
<dt>English name</dt><dd>{text(en)}</dd>
<dt>Image file</dt><dd>{text(Path(row['image_path']).name)}</dd>
<dt>Commons source</dt><dd><a href='{text(source.get('source_page_url'))}' target='_blank' rel='noreferrer'>Open source page</a></dd>
<dt>Description</dt><dd>{text(source.get('description'))}</dd>
<dt>Categories</dt><dd>{text(category)}</dd>
<dt>Audit reason</dt><dd>{text(source.get('audit_reason'))}</dd>
<dt>License</dt><dd>{text(source.get('license'))}</dd>
</dl>
<div class='criteria'><strong>PASS</strong>: 장소 자체 또는 대표 랜드마크가 주 피사체이고, 이 사진으로 장소 인식 모델을 평가하는 것이 합리적입니다.<br>
<strong>REJECT</strong>: 차량·버스·선박, 음식·사람·동물, 박물관 내부 전시품·복제품, 인근 시설, 일반적 장면, 또는 다른 장소로 오인하기 쉬운 사진이 주 피사체입니다.</div>
</article>""")
    page=f"""<!doctype html><html lang='ko'><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Diversity Manual Review</title><style>
body{{font:16px system-ui,sans-serif;background:#f4f6f8;color:#15202b;margin:0}}header{{padding:28px;max-width:1400px;margin:auto}}h1{{margin:0 0 12px}}.stats{{background:#fff;padding:16px;border-radius:10px;line-height:1.8}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(390px,1fr));gap:18px;max-width:1400px;margin:auto;padding:0 28px 28px}}.card{{background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 5px #0002}}h2{{padding:14px 16px;margin:0;font-size:18px}}h2 span{{float:right;color:#586774;font-size:13px}}img{{display:block;width:100%;max-height:390px;object-fit:contain;background:#18232c}}dl{{padding:0 16px}}dt{{font-weight:700;margin-top:12px}}dd{{margin:3px 0;overflow-wrap:anywhere}}.criteria{{margin:16px;padding:12px;background:#eef4fa;border-radius:8px;font-size:14px;line-height:1.55}}.warning{{margin:0 16px 12px;padding:10px;background:#fff0c7;border-left:4px solid #d88900;border-radius:4px;color:#704600}}a{{color:#075fb3}}
</style><body><header><h1>Benchmark A — Diversity manual review</h1><div class='stats'>
images = {len(manifest)} · PASS = 100 · unique place_id = {len(set(r['place_id'] for r in manifest.values()))} · duplicate = {len(hashes)-len(set(hashes))}<br>current places hash = <code>{places_hash}</code><br>Review candidates: {len(candidates)}. This page is for human review only; it does not call Gemini, Kakao, or any image-analysis API.</div></header><main class='grid'>{''.join(cards)}</main></body></html>"""
    (BASE / "manual_review.html").write_text(page, encoding="utf-8")
    print("\n".join(f"{image_id}\t{places[manifest[image_id]['place_id']]['detail_name']}" for image_id in candidates))

if __name__ == "__main__": main()
