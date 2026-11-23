"""Snapshot pages + their assets (css/js/img/fonts) into ./site for local prototyping.
Usage: python mirror.py [url ...]      (default: homepage -> site/index.html)
       python mirror.py --kb           (every page in kb/pages.json -> site/<path>, so the widget runs on each page)
Assets already on disk are reused, so extra pages only download what they add.
"""
import hashlib, html as html_lib, json, os, re, subprocess, sys, time
from urllib.parse import urljoin, urlparse

URL = "https://www.perkeso.gov.my/"  # page being mirrored; mirror() sets it
OUT = "site"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
seen = {}


def get(url):
    # curl, not urllib: urllib's connect timed out on this host while curl gets through.
    return subprocess.run(["curl", "-sSfL4", "-m", "60", "--retry", "2", "-A", UA, "-e", URL, url],
                          capture_output=True, check=True).stdout


def local_path(url):
    p = urlparse(url)
    path = p.path.lstrip("/") or "index"
    if p.query:  # keep ?v=123 variants distinct but filesystem-safe
        root, ext = os.path.splitext(path)
        path = f"{root}_{hashlib.md5(p.query.encode()).hexdigest()[:6]}{ext}"
    path = re.sub(r'[<>:"|?*]', "_", path)
    if p.netloc == "fonts.googleapis.com":
        path += ".css"  # extensionless CSS would be served as octet-stream and ignored
    return os.path.join("assets", p.netloc, path).replace("\\", "/")


def fetch_asset(url):
    """Download asset, return path relative to OUT (or None)."""
    url = html_lib.unescape(url).split("#")[0]  # attrs carry &amp; -> real &
    if url in seen:
        return seen[url]
    seen[url] = None
    rel = local_path(url)
    if os.path.exists(os.path.join(OUT, rel)):  # fetched by an earlier run (CSS already rewritten)
        seen[url] = rel
        return rel
    try:
        data = get(url)
    except Exception as e:
        print("  skip", url, e)
        return None
    seen[url] = rel
    if rel.endswith(".css"):
        data = rewrite_css(data.decode("utf-8", "replace"), url, os.path.dirname(rel)).encode()
    full = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "wb") as f:
        f.write(data)
    print("  ok  ", rel)
    return rel


def rewrite_css(css, base, css_dir):
    def to(ref):  # css_dir "/" = CSS inline in a page: root-absolute, so pages in subfolders still resolve
        rel = fetch_asset(urljoin(base, ref))
        return ref if not rel else "/" + rel if css_dir == "/" else os.path.relpath(rel, css_dir).replace(os.sep, "/")

    def sub(m):
        ref = m.group(2).strip()
        return m.group(0) if ref.startswith("data:") else f"url({to(ref)})"
    css = re.sub(r"""url\((['"]?)([^'")]+)\1\)""", sub, css)
    return re.sub(r"""@import\s+(['"])([^'"]+)\1""", lambda m: f'@import "{to(m.group(2))}"', css)


ASSET = re.compile(r"""(<(?:link|script|img|source|video|audio|input)\b[^>]*?\s(?:href|src|data-src|poster)=)(["'])([^"']+)\2""", re.I)


def sub_attr(m):
    tag, ref = m.group(0), m.group(3)
    if ref.startswith(("data:", "javascript:", "#", "mailto:", "tel:")):
        return tag
    full_tag = m.string[m.start():m.string.find(">", m.end()) + 1]  # rel= may come after href=
    if tag.lower().startswith("<link") and not re.search(r"stylesheet|icon|preload|manifest", full_tag, re.I):
        return tag  # canonical/alternate/etc: leave as-is
    rel = fetch_asset(urljoin(URL, ref))
    return f"{m.group(1)}{m.group(2)}{'/' + rel if rel else ref}{m.group(2)}"


def srcset_ref(ref):
    rel = fetch_asset(urljoin(URL, ref))
    return "/" + rel if rel else ref


def mirror(url):
    global URL
    URL = url
    html = get(URL).decode("utf-8", "replace")

    # Strip F5/TSPD bot-defence + its obfuscated inline blobs, and third-party trackers/chat widgets.
    html = re.sub(r"<script[^>]*TSPD.*?</script>", "", html, flags=re.S | re.I)
    html = re.sub(r"<script[^>]*>\s*\(function\(\)\{\s*window\[\"loaderConfig\"\].*?</script>", "", html, flags=re.S)
    html = re.sub(r"<APM_DO_NOT_TOUCH>.*?</APM_DO_NOT_TOUCH>", "", html, flags=re.S)
    html = re.sub(r"<script[^>]*>(?:(?!</script>).)*(googletagmanager|fbq\(|quantserve|ttq\.|yellowmessenger|widget\.perkeso)(?:(?!</script>).)*</script>",
                  "", html, flags=re.S | re.I)
    html = re.sub(r"<script[^>]+src=[\"'][^\"']*(googletagmanager|connect\.facebook|quantserve|tiktok|yellowmessenger|widget\.perkeso)[^\"']*[\"'][^>]*>\s*</script>",
                  "", html, flags=re.I)

    html = ASSET.sub(sub_attr, html)
    html = re.sub(r"""srcset=(["'])([^"']+)\1""",
                  lambda m: 'srcset="' + ", ".join(
                      " ".join([srcset_ref(p.split()[0])] + p.split()[1:])
                      for p in re.split(r",\s+", m.group(2)) if p.strip()) + '"', html)  # URLs contain bare commas
    html = re.sub(r"<style[^>]*>.*?</style>", lambda m: rewrite_css(m.group(0), URL, "/"), html, flags=re.S | re.I)
    html = re.sub(r"""style=(["'])(.*?)\1""", lambda m: f"style={m.group(1)}{rewrite_css(m.group(2), URL, '/')}{m.group(1)}", html)
    # Relative site links -> absolute, so nav still works by pointing at the live site.
    html = re.sub(r"""(<a\b[^>]*?\shref=)(["'])(/[^"']*)\2""", lambda m: f"{m.group(1)}{m.group(2)}{urljoin(URL, m.group(3))}{m.group(2)}", html)

    out = os.path.join(OUT, urlparse(url).path.lstrip("/") or "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("  saved", out)


if __name__ == "__main__":
    args = sys.argv[1:]
    urls = [p["url"] for p in json.load(open("kb/pages.json", encoding="utf-8"))] if args == ["--kb"] else args or [URL]
    for i, u in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {u}")
        try:
            mirror(u)
        except subprocess.CalledProcessError as e:
            print("  failed:", e)
        time.sleep(1)  # be polite to the server
    print(f"\n{len(urls)} page(s), {sum(1 for v in seen.values() if v)} assets")
