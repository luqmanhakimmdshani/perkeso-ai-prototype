"""Local prototype server: serves the mirrored site + the AI assistant, with AI routed through OmniRoute.
Usage:  put OMNIROUTE_API_KEY (from the OmniRoute dashboard) in .env, and OMNIROUTE_MODELS (comma-separated, tried in order)
        python server.py   ->  http://localhost:8080
Needs kb/pages.json from crawl.py.
"""
import json, math, os, re, time, http.server, socketserver, urllib.error, urllib.parse, urllib.request
from collections import Counter
from datetime import date
from caruman import kira_caruman
from crawl import to_text

ROOT = os.path.dirname(os.path.abspath(__file__))
# Load .env (KEY=value lines); variables already set in the shell win.
if os.path.exists(os.path.join(ROOT, ".env")):
    for line in open(os.path.join(ROOT, ".env"), encoding="utf-8"):
        k, sep, v = line.strip().partition("=")
        if sep and not k.startswith("#") and v.strip():
            os.environ.setdefault(k.strip(), v.strip().strip('"\''))
SITE, ASSISTANT = os.path.join(ROOT, "site"), os.path.join(ROOT, "assistant")
OMNI_URL = os.environ.get("OMNIROUTE_URL", "http://localhost:20128/v1").rstrip("/")
OMNI_KEY = os.environ.get("OMNIROUTE_API_KEY", "")
# Free models are flaky (rate limits, cooldowns), so try a chain; a model that fails sits out COOLDOWN seconds.
MODELS = [m.strip() for m in os.environ.get("OMNIROUTE_MODELS", os.environ.get("OMNIROUTE_MODEL", "auto/best-free")).split(",") if m.strip()]
COOLDOWN, FIRST_TOKEN = 60, 30
DOWN = {}  # model -> monotonic time it may be tried again
INJECT = b'<link rel="stylesheet" href="/assistant/assistant.css"><script src="/assistant/assistant.js" defer></script></body>'

# ---- knowledge base: chunks + BM25 (routed models may have small context windows, so send only the relevant parts) ----
pages = json.load(open(os.path.join(ROOT, "kb", "pages.json"), encoding="utf-8"))
CHUNKS = []
for p in pages:
    buf = ""
    for line in p["text"].split("\n"):
        if len(buf) + len(line) > 1500 and buf:
            CHUNKS.append((p, buf)); buf = ""
        buf += line + "\n"
    if buf.strip():
        CHUNKS.append((p, buf))
# Light Malay stemming: "sakitnya" -> "sakit" so possessive forms still match.
tok = lambda s: [w[:-3] if w.endswith("nya") and len(w) > 5 else w for w in re.findall(r"[a-z0-9]+", s.lower())]
DOCS = [Counter(tok(p["title"] + " " + c)) for p, c in CHUNKS]
AVG = sum(sum(d.values()) for d in DOCS) / len(DOCS)
DF = Counter(t for d in DOCS for t in d)
# Common English words users type -> the Malay terms the site uses (site content is Malay).
SYN = {"accident": "kemalangan", "injury": "kecederaan", "claim": "tuntutan", "contribution": "caruman", "employer": "majikan",
       "worker": "pekerja", "foreign": "asing", "register": "pendaftaran daftar", "registration": "pendaftaran", "pension": "pencen",
       "death": "kematian", "disability": "keilatan hilang upaya", "invalidity": "keilatan", "job": "pekerjaan kerja",
       "unemployment": "kehilangan pekerjaan sip", "lost": "kehilangan", "housewife": "suri rumah", "self": "sendiri",
       "employed": "bekerja", "gig": "sendiri e-hailing", "payment": "pembayaran bayaran", "rate": "kadar", "form": "borang",
       "domestic": "domestik", "maid": "domestik", "benefit": "faedah", "benefits": "faedah", "medical": "perubatan",
       "clinic": "klinik panel", "dialysis": "dialisis", "office": "pejabat lokasi", "contact": "hubungi", "deadline": "tarikh akhir",
       "wage": "gaji upah", "salary": "gaji", "maximum": "maksimum had siling", "ceiling": "siling had", "limit": "had tempoh",
       "time": "tempoh masa", "permanent": "kekal", "disablement": "hilang upaya", "funeral": "pengurusan mayat", "amount": "amaun jumlah",
       "mandatory": "wajib", "compulsory": "wajib", "harassment": "gangguan seksual", "resign": "letak jawatan perletakan",
       "resigned": "letak jawatan perletakan", "allowance": "elaun", "monthly": "bulanan sebulan", "hotline": "talian khidmat pelanggan",
       "abroad": "luar negara malaysia", "overseas": "luar negara malaysia", "sick": "sakit", "leave": "cuti", "minimum": "minimum",
       "dies": "meninggal dunia kematian", "died": "meninggal dunia kematian", "die": "meninggal dunia kematian"}


def search(query, budget=24000):
    """Rank chunks with BM25, then return whole pages (best first): short pages in full, long ones as their best 3 chunks.
    Page-level results stop one big page (the FAQ) from filling every slot. Returns [(page, text)]."""
    q = tok(query)
    q += [w for t in q for w in tok(SYN.get(t, ""))]
    N = len(DOCS)
    scores = []
    for i, d in enumerate(DOCS):
        n = sum(d.values()); s = 0.0
        for t in set(q):
            if t in d:
                idf = math.log(1 + (N - DF[t] + 0.5) / (DF[t] + 0.5))
                s += idf * d[t] * 2.2 / (d[t] + 1.2 * (0.25 + 0.75 * n / AVG))
        scores.append(s)
    order = [i for i in sorted(range(N), key=scores.__getitem__, reverse=True) if scores[i] > 0]
    out, used, seen = [], 0, set()
    for i in order:
        p = CHUNKS[i][0]
        if p["url"] in seen:
            continue
        seen.add(p["url"])
        text = p["text"]
        if len(p["text"]) > 8000:  # best 3 chunks of a long page, in page order
            best = sorted([j for j in order if CHUNKS[j][0] is p][:3])
            text = "\n...\n".join(CHUNKS[j][1] for j in best)
        if used + len(text) > budget and out:
            continue
        out.append((p, text)); used += len(text)
        if len(out) == 6:
            break
    return out


INDEX = "\n".join(f"- {p['title']}: {p['url']}" for p in pages)
SYSTEM = f"""Anda ialah Pembantu PERKESO, pembantu maya di laman web Pertubuhan Keselamatan Sosial (PERKESO) Malaysia.
Tarikh hari ini: {date.today():%d %B %Y}.

Peraturan:
- Jawab HANYA berdasarkan petikan <laman> yang diberi dalam mesej sistem terakhir. Jika jawapan tiada di situ, katakan anda tidak pasti dan cadangkan pengguna hubungi PERKESO (Maklumat Hubungan / Chatbot Hanna / kaunter) - jangan meneka.
- Jangan sekali-kali mengira caruman pekerja bergaji sendiri; gunakan fungsi kira_caruman, dan nyatakan ia anggaran (jadual rasmi guna jalur gaji).
- Sesetengah kandungan laman mungkin lama; utamakan maklumat terkini (cth. LINDUNG 24 Jam mulai 1 Jun 2026).
- Jawab dalam bahasa yang digunakan pengguna (Bahasa Melayu, English, atau campuran). Ringkas, mesra, mudah difahami. Gunakan senarai bernombor untuk langkah-langkah.
- Akhiri jawapan yang berdasarkan laman dengan satu baris "Sumber:" diikuti URL penuh laman yang digunakan (satu atau dua).
- Jangan minta nombor kad pengenalan, kata laluan atau maklumat peribadi sensitif. Untuk semakan status peribadi, arahkan ke portal yang betul.

Senarai semua laman (untuk pautan):
{INDEX}"""

TOOLS = [{"type": "function", "function": {
    "name": "kira_caruman",
    "description": "Anggar caruman bulanan PERKESO (Akta 4, SIP/Akta 800, LINDUNG 24 Jam) untuk seorang pekerja bergaji. "
                   "Gunakan untuk SEMUA soalan jumlah caruman pekerja bergaji. Panggil sekali bagi setiap pekerja/kategori. "
                   "Bukan untuk pekerja sendiri (Akta 789) atau suri rumah (Akta 838).",
    "parameters": {
        "type": "object",
        "properties": {
            "gaji": {"type": "number", "description": "Gaji bulanan dalam RM"},
            "kategori": {"type": "string", "enum": ["tempatan", "asing"],
                         "description": "tempatan = warganegara/PR (termasuk pembantu rumah tempatan); asing = pekerja asing (termasuk pembantu rumah asing)"},
            "umur_60_ke_atas": {"type": "boolean", "description": "true jika pekerja berumur 60 tahun ke atas"},
            "lindung24": {"type": "boolean", "description": "Pekerja tempatan yang menyertai LINDUNG 24 Jam (sukarela). Abaikan untuk pekerja asing."},
        },
        "required": ["gaji", "kategori", "umur_60_ke_atas"],
    }}}]


def run_tool(call):
    try:  # model-supplied arguments are untrusted: parse and validate before running
        a = json.loads(call["function"]["arguments"] or "{}")
        out = kira_caruman(float(a["gaji"]), a["kategori"], bool(a.get("umur_60_ke_atas")), a.get("lindung24"))
    except Exception as e:
        out = {"ralat": f"input tidak sah: {e}"}
    return {"role": "tool", "tool_call_id": call["id"], "content": json.dumps(out, ensure_ascii=False)}


class ModelError(Exception):
    pass


def omni_stream(messages, model, tools, idle_limit=FIRST_TOKEN):
    """POST /chat/completions with stream=true; yields parsed SSE chunks.
    OmniRoute sends keepalive chunks while it hunts for a working upstream, so the socket timeout never fires:
    give up after idle_limit seconds without real output."""
    req = urllib.request.Request(f"{OMNI_URL}/chat/completions", method="POST",
        data=json.dumps({"model": model, "messages": messages, "stream": True, "max_tokens": 4000, **({"tools": tools} if tools else {})}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {OMNI_KEY}"})
    with urllib.request.urlopen(req, timeout=idle_limit) as r:
        last = time.monotonic()
        for line in r:
            line = line.decode("utf-8", "replace").strip()
            if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                continue
            chunk = json.loads(line[5:])
            if chunk.get("error"):  # upstream failures arrive inside the stream
                err = chunk["error"]
                raise ModelError(err.get("message", str(err)) if isinstance(err, dict) else str(err))
            if chunk.get("model") == "keepalive":
                if time.monotonic() - last > idle_limit:
                    raise ModelError(f"tiada jawapan dalam {idle_limit} saat")
                continue
            last = time.monotonic()
            yield chunk


def round_once(msgs, write, model, tools):
    """One model turn. Streams text; returns accumulated tool calls (possibly empty)."""
    calls = {}
    for chunk in omni_stream(msgs, model, tools):
        if not chunk.get("choices"):
            continue
        d = chunk["choices"][0].get("delta") or {}
        if d.get("content"):
            write(d["content"])
        for tc in d.get("tool_calls") or []:  # tool-call arguments arrive in pieces
            c = calls.setdefault(tc.get("index", 0), {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
            c["id"] = tc.get("id") or c["id"]
            f = tc.get("function") or {}
            c["function"]["name"] += f.get("name") or ""
            c["function"]["arguments"] += f.get("arguments") or ""
    return [calls[i] for i in sorted(calls)]


def format_caruman(results):
    """Plain answer from calculator output, used when the model fails after the tool ran."""
    out = []
    for r in results:
        if "butiran" not in r:
            continue
        rows = "\n".join(f"- {b['skim']}: majikan RM{b['majikan']:.2f}, pekerja RM{b['pekerja']:.2f}" for b in r["butiran"])
        out.append(f"{rows}\n**Jumlah sebulan: majikan RM{r['jumlah_majikan']:.2f}, pekerja RM{r['jumlah_pekerja']:.2f}**\n{r['nota']}\nSumber: {r['sumber']}")
    return "\n\n".join(out)


def model_round(msgs, write, tools):
    """Run one turn on the first model in the chain that works. Returns tool calls, or None if every model failed."""
    for m in MODELS:
        if DOWN.get(m, 0) > time.monotonic():
            continue
        sent, held = [], []
        def w(t):  # hold the first 200 chars: some free models print fake tool calls instead of answering
            if sent:
                sent.append(t); return write(t)
            held.append(t)
            if len("".join(held)) >= 200:
                release()
        def release():
            text = "".join(held); held.clear()
            if FAKE_TOOL.search(text):
                raise ModelError("panggilan alat palsu dalam teks")
            if text:
                sent.append(text); write(text)
        try:
            calls = round_once(msgs, w, m, tools)
            release()
            if not calls and not "".join(sent).strip():
                raise ModelError("jawapan kosong")
            print(f"[chat] {m} ok", flush=True)
            return calls
        except (ModelError, TimeoutError, urllib.error.URLError, ValueError) as e:
            DOWN[m] = time.monotonic() + COOLDOWN
            print(f"[chat] {m} failed: {str(e)[:150]}", flush=True)
            if "".join(sent).strip():  # text already reached the user: can't restart on another model
                write("\n[Jawapan terputus. Sila cuba lagi.]")
                return []
    return None


FAKE_TOOL = re.compile(r"tool_call|tool_code|<\|", re.I)


# Wage questions are answered by code, not left to the model: free models often ignore tools.
AMOUNT = re.compile(r"(?:rm|gaji|salary|wage|upah|pendapatan)\D{0,15}?(\d[\d,]*(?:\.\d+)?)", re.I)
def auto_caruman(q):
    if not re.search(r"carum|contribut|potong|deduct|socso|perkeso", q, re.I):
        return []
    kat = "asing" if re.search(r"asing|foreign|migrant", q, re.I) else "tempatan"
    tua = bool(re.search(r"\b(6\d|[7-9]\d)\s*(tahun|years?|y/?o)|60 tahun ke atas|(above|over) 60|warga emas", q, re.I))
    l24 = True if kat == "tempatan" and re.search(r"lindung\s*24|24\s*jam|24.hour", q, re.I) else None
    out = []
    for a in AMOUNT.findall(q)[:3]:
        gaji = float(a.replace(",", ""))
        if gaji >= 100:
            out.append({"gaji": gaji, "kategori": kat, "umur_60_ke_atas": tua, "lindung24": bool(l24), **kira_caruman(gaji, kat, tua, l24)})
    return out


def fallback(hits, tool_results, write):
    """Every model failed: answer with what code and the site already know, never an empty bubble."""
    if tool_results:
        write(format_caruman(tool_results) + "\n\n(Pembantu AI tidak tersedia; angka di atas dikira terus oleh kalkulator.)")
        return
    write("Pembantu AI tidak tersedia buat masa ini. Berikut maklumat berkaitan daripada laman PERKESO:\n")
    seen = set()
    for p, c in hits:
        if p["url"] in seen or len(seen) == 3:
            continue
        seen.add(p["url"])
        write(f"\n**{p['title']}**\n{' '.join(c.split())[:280]}…\n{p['url']}\n")
    write("\nBantuan lanjut: Talian Khidmat Pelanggan 1-300-22-8000.")


def chat(history, write):
    """history: [{role, content:str}] from the browser. Streams text to write()."""
    convo = [{"role": m["role"], "content": str(m["content"])[:4000]} for m in history[-20:]
             if m.get("role") in ("user", "assistant") and m.get("content")]
    if not convo or convo[-1]["role"] != "user":
        return write("[Tiada soalan.]")
    users = [m["content"] for m in convo if m["role"] == "user"]
    hits = search(" ".join(users[-2:]))
    context = "\n\n".join(f'<laman url="{p["url"]}" tajuk="{p["title"]}">\n{c}</laman>' for p, c in hits) or "(tiada petikan berkaitan)"
    msgs = [{"role": "system", "content": SYSTEM}, *convo[:-1],
            {"role": "system", "content": "Petikan laman yang berkaitan dengan soalan terkini:\n\n" + context}, convo[-1]]
    tool_results = auto_caruman(convo[-1]["content"])
    if tool_results:
        msgs.insert(-1, {"role": "system", "content": "Keputusan kalkulator kira_caruman (dikira oleh kod; guna angka ini tepat-tepat, "
                         "jangan kira semula, dan nyatakan andaian kategori/umur/LINDUNG 24 Jam kepada pengguna):\n"
                         + json.dumps(tool_results, ensure_ascii=False)})
    for _ in range(5):  # tool-round cap
        tool_calls = model_round(msgs, write, None if tool_results else TOOLS)
        if tool_calls is None:
            return fallback(hits, tool_results, write)
        if not tool_calls:
            return
        msgs.append({"role": "assistant", "content": None, "tool_calls": tool_calls})
        results = [run_tool(c) for c in tool_calls]
        msgs += results
        tool_results += [json.loads(r["content"]) for r in results]
        write("\n\n")


BASE = "https://www.perkeso.gov.my"
TEXT = {}  # local page file -> (title, text), extracted on first use


def page_file(path):
    """Mirrored HTML file for a site path ("/" -> index.html), or None. Confined to SITE; never an asset."""
    rel = urllib.parse.unquote(path.split("?")[0]).lstrip("/") or "index.html"
    f = os.path.realpath(os.path.join(SITE, rel))
    ok = f.startswith(os.path.realpath(SITE) + os.sep) and f.endswith(".html") and not rel.startswith("assets/")
    return f if ok and os.path.isfile(f) else None


# Links to pages we mirrored stay on the prototype; the rest still go to the live site.
LINK = re.compile(r'href="https://www\.perkeso\.gov\.my(/[^"#?]*)')
LANGS = {"ms": "Bahasa Melayu", "en": "English", "zh": "中文 (Mandarin, tulisan ringkas)", "ta": "தமிழ் (Tamil)",
         "id": "Bahasa Indonesia", "bn": "বাংলা (Bengali)", "ne": "नेपाली (Nepali)", "my": "မြန်မာ (Myanmar)"}
# Malaysian IC (YYMMDD-PB-####) and other long digit runs: never forward them to a third-party model.
PII = re.compile(r"\b\d{6}-?\d{2}-?\d{4}\b|\b\d{10,}\b")


def generate(system, user, write):
    """Single-turn, no-tool generation on the model chain. Returns False if every model failed."""
    return model_round([{"role": "system", "content": system}, {"role": "user", "content": user}], write, None) is not None


def explain(path, lang, write):
    f = page_file(str(path))
    if not f:
        return write("[Laman tidak dikenali.]")
    if f not in TEXT:
        TEXT[f] = to_text(open(f, encoding="utf-8").read())
    title, text = TEXT[f]
    url = BASE + "/" + os.path.relpath(f, SITE).replace(os.sep, "/").removesuffix("index.html")
    name = LANGS.get(lang, LANGS["ms"])
    system = f"""Anda menerangkan laman web PERKESO kepada orang awam dalam bahasa: {name}. Tarikh hari ini: {date.today():%d %B %Y}.
Peraturan:
- Kandungan penuh laman sudah diberi dalam <laman>; jangan cuba membuka pautan. Guna HANYA kandungan itu - jangan tambah fakta, amaun, tarikh atau syarat yang tiada di situ.
- Kekalkan nama khas dalam bentuk asal (cth. LINDUNG 24 Jam, Borang 34, Portal ASSIST, PERKESO).
- Bahasa mudah, ayat pendek. Tiada jadual.
Format (tajuk bahagian dalam {name}, ditebalkan dengan **):
1. Ringkasan: 2-3 ayat - laman ini tentang apa dan untuk siapa.
2. Apa yang perlu anda buat: langkah bernombor (jika laman tiada langkah, nyatakan ke mana pergi seterusnya).
3. Perkara penting: senarai pendek tarikh akhir, kadar, syarat atau pengecualian."""
    # ponytail: long pages (FAQ, Pekerja Asing) are cut at 12k chars; switch to search() chunks if answers miss the tail.
    if not generate(system, f'<laman tajuk="{title}">\n{text[:12000]}\n</laman>', write):
        write("Pembantu AI tidak tersedia buat masa ini. Petikan laman:\n\n" + " ".join(text.split())[:600] + "…")
    write(f"\n\nSumber: {url}")


def checklist(card, situasi, write):
    card = card if isinstance(card, dict) else {}
    situasi = PII.sub("[dibuang]", str(situasi))[:1000].strip()
    if not situasi:
        return write("[Sila ceritakan situasi anda.]")
    facts = json.dumps({k: card.get(k) for k in ("t", "tag", "tarikh", "layak", "tidak", "faedah", "langkah", "borang", "nota")},
                       ensure_ascii=False)[:6000]
    context = "\n\n".join(f'<laman url="{p["url"]}">\n{c}</laman>' for p, c in search(card.get("t", "") + " " + situasi, budget=8000))
    system = f"""Anda menyediakan senarai semak tuntutan PERKESO yang diperibadikan. Tarikh hari ini: {date.today():%d %B %Y}.
Peraturan:
- Guna HANYA fakta dalam <faedah> dan <laman>. Jangan cipta borang, dokumen, amaun, tarikh atau portal.
- Borang: sebut hanya borang dalam senarai "borang". Dokumen sokongan: sebut hanya yang dinyatakan dalam fakta; selebihnya tulis "ikut senarai semak borang".
- Jika situasi tidak sepadan dengan faedah ini, atau kelayakan tidak jelas, katakan dengan jelas dan cadangkan semak di kaunter PERKESO.
- Jangan minta nombor kad pengenalan atau maklumat peribadi.
- Jawab dalam bahasa yang digunakan pengguna. Tiada jadual.
Format (tajuk ditebalkan dengan **):
**Ringkasan kes** - 1-2 ayat.
**Langkah anda** - bernombor; setiap langkah nyatakan siapa (anda / majikan / doktor / waris).
**Borang & dokumen** - setiap item bermula dengan "[ ] ".
**Tarikh penting** - tarikh akhir yang berkaitan; jika tiada dalam fakta, tulis "Sahkan dengan PERKESO".
**Perlu disahkan** - perkara yang tidak pasti."""
    user = f"<faedah>\n{facts}\n</faedah>\n\n{context}\n\nSituasi pengguna:\n{situasi}"
    if not generate(system, user, write):
        write("Pembantu AI tidak tersedia buat masa ini. Sila guna langkah dan borang dalam kad di atas.")


class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        if path.startswith("/assistant/"):
            return os.path.join(ASSISTANT, os.path.basename(path.split("?")[0]))
        p = super().translate_path(path)
        if not os.path.exists(p):  # mirror.py keeps %20 etc. literally in asset file names
            raw = super().translate_path(path.replace("%", "%25"))
            p = raw if os.path.exists(raw) else p
        return p

    def end_headers(self):
        if self.path.startswith("/assistant/"):  # widget changes often; stop browsers serving a stale copy
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self):
        f = page_file(self.path)
        if f:
            html = LINK.sub(lambda m: f'href="{m.group(1)}' if page_file(m.group(1)) else m.group(0), open(f, encoding="utf-8").read())
            body = html.encode().replace(b"</body>", INJECT, 1)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def do_POST(self):
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except ValueError:
            return self.send_error(400, "bad json")
        if self.path == "/api/caruman":
            try:
                body = json.dumps(kira_caruman(float(data["gaji"]), data["kategori"], bool(data.get("umur_60_ke_atas")),
                                               data.get("lindung24"))).encode()
            except (KeyError, ValueError, TypeError) as e:
                return self.send_error(400, str(e))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            return self.wfile.write(body)
        streams = {"/api/chat": lambda w: chat(data.get("messages", []), w),
                   "/api/explain": lambda w: explain(data.get("path", ""), data.get("lang"), w),
                   "/api/checklist": lambda w: checklist(data.get("card") or {}, data.get("situasi", ""), w)}
        if self.path in streams:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            def write(t):
                self.wfile.write(t.encode()); self.wfile.flush()
            try:
                streams[self.path](write)
            except urllib.error.HTTPError as e:
                detail = e.read()[:300].decode("utf-8", "replace")
                write({401: "\n[Ralat: kunci API OmniRoute tidak sah atau tiada (OMNIROUTE_API_KEY).]",
                       429: "\n[Ralat: terlalu banyak permintaan, cuba sebentar lagi.]"}.get(e.code, f"\n[Ralat OmniRoute {e.code}: {detail}]"))
            except (urllib.error.URLError, TimeoutError):
                write(f"\n[Ralat: OmniRoute tidak dapat dihubungi di {OMNI_URL}. Adakah ia sedang berjalan?]")
            return
        self.send_error(404)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if not OMNI_KEY:
        print("Warning: OMNIROUTE_API_KEY not set - chat will fail if OmniRoute requires a key.")
    os.chdir(SITE)  # SimpleHTTPRequestHandler serves from cwd
    with socketserver.ThreadingTCPServer(("127.0.0.1", 8080), Handler) as s:
        s.daemon_threads = True
        print(f"Serving http://localhost:8080  ({len(pages)} pages, {len(CHUNKS)} chunks, models={",".join(MODELS)} via {OMNI_URL})")
        s.serve_forever()
