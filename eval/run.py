"""Ask every question in questions.json through the running prototype (/api/chat) and grade the answers.
A question passes when the answer contains one option from every `must` group, none of `mustnot`,
and (if `src` is given) cites a PERKESO page that is either listed in `src` or actually contains the required fact.
Usage: python eval/run.py [id ...]     (server must be running on :8080)
Writes eval/results/<timestamp>.json.
"""
import json, os, re, sys, time, urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
QS = json.load(open(os.path.join(HERE, "questions.json"), encoding="utf-8"))
FALLBACK = "Pembantu AI tidak tersedia"
PAGES = {p["url"]: norm_text for p in json.load(open(os.path.join(HERE, "..", "kb", "pages.json"), encoding="utf-8"))
         for norm_text in [" ".join(p["text"].lower().split())]}


def norm(s):
    return " ".join(s.lower().replace("–", "-").replace("—", "-").split())


def grade(q, ans):
    a = norm(ans)
    why = [f"tiada: {' / '.join(g)}" for g in q["must"] if not any(norm(o) in a for o in g)]
    why += [f"ada (dilarang): {x}" for x in q.get("mustnot", []) if norm(x) in a]
    cited = [PAGES.get(u.rstrip(".,)*")) for u in re.findall(r"https?://www\.perkeso\.gov\.my/\S+", ans)]
    backed = any(t and any(norm(o) in t for o in q["must"][0]) for t in cited)
    if q.get("src") and not backed and not any(s in a for s in q["src"]):
        why.append(f"sumber bukan {' / '.join(q['src'])}")
    return why


def ask(text):
    req = urllib.request.Request("http://localhost:8080/api/chat", method="POST", headers={"Content-Type": "application/json"},
                                 data=json.dumps({"messages": [{"role": "user", "content": text}]}).encode())
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read().decode("utf-8", "replace")


def main(ids):
    rows = []
    for q in [q for q in QS if not ids or q["id"] in ids]:
        t = time.time()
        try:
            ans = ask(q["q"])
        except Exception as e:
            ans = f"[ralat sambungan: {e}]"
        secs = round(time.time() - t, 1)
        why = grade(q, ans)
        mode = "fallback" if FALLBACK in ans else "error" if ans.lstrip().startswith("[") else "ai"
        rows.append({"id": q["id"], "q": q["q"], "pass": not why, "why": why, "mode": mode, "secs": secs, "answer": ans})
        print(f"{'PASS' if not why else 'FAIL'}  {q['id']:<14} {mode:<8} {secs:>5}s  {'; '.join(why)}", flush=True)
        time.sleep(2)  # free tiers rate-limit bursts
    n = sum(r["pass"] for r in rows)
    ai = [r for r in rows if r["mode"] == "ai"]
    print(f"\n{n}/{len(rows)} lulus | jawapan AI {len(ai)}/{len(rows)}, lulus {sum(r['pass'] for r in ai)}"
          f" | purata {sum(r['secs'] for r in rows) / max(len(rows), 1):.1f}s")
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    out = os.path.join(HERE, "results", datetime.now().strftime("%Y%m%d-%H%M%S") + ".json")
    json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Disimpan:", out)


if __name__ == "__main__":
    main(sys.argv[1:])
