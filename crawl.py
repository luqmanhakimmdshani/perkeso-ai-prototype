"""Collect the text of PERKESO's service pages (linked from the homepage menu) into kb/pages.json.
The assistant answers only from this file. Usage: python crawl.py   (needs site/index.html from mirror.py)
"""
import html, json, os, re, subprocess, sys, time

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
BASE = "https://www.perkeso.gov.my"
# Sections worth answering from; skips old campaigns (bajet-2022, covid, karnival...) and corporate pages.
KEEP = ("/perkhidmatan-kami/", "/atas-talian/", "/hubungi-kami/", "/mengenai-kami/rujukan/tarikh-bayaran-faedah",
        "/mengenai-kami/rujukan/borang-borang", "/mengenai-kami/rujukan/belanjawan-2027", "/lindung")


def get(url):
    return subprocess.run(["curl", "-sSfL4", "-m", "60", "--retry", "2", "-A", UA, "-e", BASE + "/", url],
                          capture_output=True, check=True).stdout.decode("utf-8", "replace")


def to_text(page):
    title = re.search(r"<title>(.*?)</title>", page, re.S)
    main = re.search(r'<main id="tm-main".*?</main>', page, re.S) or re.search(r"<body.*?</body>", page, re.S)
    s = main.group(0) if main else page
    s = re.sub(r"<(script|style|nav|svg)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>|</(p|div|li|h\d|tr)>", "\n", s, flags=re.I)
    s = re.sub(r"</t[dh]>", " | ", s, flags=re.I)          # keep table cells apart (rate tables)
    s = re.sub(r"<a[^>]*href=\"([^\"]+\.pdf)\"[^>]*>(.*?)</a>", r"\2 [PDF: \1]", s, flags=re.S | re.I)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    s = re.sub(r"[ \t\xa0]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s).strip()
    return html.unescape(title.group(1)).strip() if title else "", s


if __name__ == "__main__":
    home = open("site/index.html", encoding="utf-8").read()
    urls = sorted({u.split("#")[0] for u in re.findall(r'href="(https://www\.perkeso\.gov\.my/[^"]+)"', home)
                   if any(k in u for k in KEEP) and not u.endswith(".pdf")})
    print(len(urls), "pages")

    pages = []
    for i, u in enumerate(urls, 1):
        try:
            title, text = to_text(get(u))
        except Exception as e:
            print(f"[{i}/{len(urls)}] skip {u}: {e}")
            continue
        if len(text) > 200:
            pages.append({"url": u, "title": title, "text": text})
        print(f"[{i}/{len(urls)}] {len(text):6d} chars  {u}")
        time.sleep(1)  # be polite to the server

    os.makedirs("kb", exist_ok=True)
    json.dump(pages, open("kb/pages.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nSaved {len(pages)} pages, {sum(len(p['text']) for p in pages):,} chars -> kb/pages.json")
