#!/usr/bin/env python3
"""
paper_catch.py —— 统一的会议论文 PDF 链接收集 + 下载脚本

两阶段设计：
  1) collect  : 只负责「拿到每篇论文的 PDF 链接」，输出 links/<conf>.json (+ .txt)
                不需要下载权限，任何能上网的机器都可以跑。
  2) download : 读取 links/<conf>.json，真正下载 PDF。
                开放获取的（USENIX / CVF / NeurIPS ...）直接 requests 下载；
                需要权限的（ACM DL / IEEE Xplore）用 Selenium 浏览器下载，
                放到有机构权限（校园网 / 已登录）的电脑上执行。

链接来源（collect 的 source）：
  usenix : 解析 usenix.org 的 technical-sessions 页面 → 每篇 presentation 页 → PDF
  dblp   : 通过 DBLP API 拿整本 proceedings 的 DOI（ACM / IEEE 通用，不需要权限）
           10.1145/* → https://dl.acm.org/doi/pdf/<doi>
           10.1109/* → https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber=<n>
  page   : 解析在线网页或本地保存的 HTML（ACM 目录页、IEEE 目录页、会议 program 页、
           CVF / NeurIPS / IJCAI 列表页，或者自定义正则）

常用示例：
  python paper_catch.py list
  python paper_catch.py collect nsdi25
  python paper_catch.py collect sigcomm24
  python paper_catch.py collect infocom24
  python paper_catch.py collect asplos25 --page https://www.asplos-conference.org/asplos2025/program.html
  python paper_catch.py collect eurosys25 --page ./eurosys25_html/
  python paper_catch.py download links/sigcomm24.json --profile-dir ./chrome_profile
  python paper_catch.py run osdi25            # collect + download 一步完成
"""

import argparse
import csv
import datetime
import http.cookiejar
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_LINKS_DIR = SCRIPT_DIR / "links"
DEFAULT_PDF_ROOT = SCRIPT_DIR.parent / "conference_pdf"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA}

# ============================================================================
# 会议注册表
#   source=usenix : usenix 为 usenix.org 上的会议前缀（nsdi25 里的 nsdi）
#   source=dblp   : dblp 为 DBLP 的 series 路径，prefix 为该会议 toc 文件名前缀
#                   （同一年有多卷时，如 asplos2024-1/-2/-3，会自动全部找出）
#   source=page   : page 为列表页 URL 模板，parser 为页面解析器
# 不在表里的会议也能用：collect 时手动给 --usenix / --dblp / --page 即可。
# ============================================================================
CONFERENCES = {
    # ---------------- USENIX（开放获取，直接下载） ----------------
    "nsdi":    {"source": "usenix", "usenix": "nsdi",  "area": "network"},
    "osdi":    {"source": "usenix", "usenix": "osdi",  "area": "system"},
    "atc":     {"source": "usenix", "usenix": "atc",   "area": "system"},
    "fast":    {"source": "usenix", "usenix": "fast",  "area": "system/storage"},
    "uss":     {"source": "usenix", "usenix": "usenixsecurity", "area": "security"},

    # ---------------- ACM（DBLP 拿 DOI，浏览器下载） ----------------
    "sigcomm":    {"source": "dblp", "dblp": "conf/sigcomm",    "prefix": "sigcomm",    "area": "network"},
    "mobicom":    {"source": "dblp", "dblp": "conf/mobicom",    "prefix": "mobicom",    "area": "network/mobile"},
    "mobisys":    {"source": "dblp", "dblp": "conf/mobisys",    "prefix": "mobisys",    "area": "mobile"},
    "sensys":     {"source": "dblp", "dblp": "conf/sensys",     "prefix": "sensys",     "area": "iot"},
    "imc":        {"source": "dblp", "dblp": "conf/imc",        "prefix": "imc",        "area": "network/measurement"},
    "hotnets":    {"source": "dblp", "dblp": "conf/hotnets",    "prefix": "hotnets",    "area": "network"},
    "conext":     {"source": "dblp", "dblp": "conf/conext",     "prefix": "conext",     "area": "network"},
    "sosp":       {"source": "dblp", "dblp": "conf/sosp",       "prefix": "sosp",       "area": "system"},
    "eurosys":    {"source": "dblp", "dblp": "conf/eurosys",    "prefix": "eurosys",    "area": "system"},
    "asplos":     {"source": "dblp", "dblp": "conf/asplos",     "prefix": "asplos",     "area": "system/arch"},
    "socc":       {"source": "dblp", "dblp": "conf/cloud",      "prefix": "socc",       "area": "cloud"},
    "middleware": {"source": "dblp", "dblp": "conf/middleware", "prefix": "middleware", "area": "system"},
    "ppopp":      {"source": "dblp", "dblp": "conf/ppopp",      "prefix": "ppopp",      "area": "parallel"},
    "hpdc":       {"source": "dblp", "dblp": "conf/hpdc",       "prefix": "hpdc",       "area": "hpc"},
    "isca":       {"source": "dblp", "dblp": "conf/isca",       "prefix": "isca",       "area": "arch"},
    "micro":      {"source": "dblp", "dblp": "conf/micro",      "prefix": "micro",      "area": "arch"},
    "sc":         {"source": "dblp", "dblp": "conf/sc",         "prefix": "sc",         "area": "hpc"},
    "www":        {"source": "dblp", "dblp": "conf/www",        "prefix": "www",        "area": "web"},
    "ccs":        {"source": "dblp", "dblp": "conf/ccs",        "prefix": "ccs",        "area": "security"},

    # ---------------- IEEE（DBLP 拿 DOI → arnumber，浏览器下载） ----------------
    "infocom": {"source": "dblp", "dblp": "conf/infocom", "prefix": "infocom", "area": "network"},
    "icnp":    {"source": "dblp", "dblp": "conf/icnp",    "prefix": "icnp",    "area": "network"},
    "icdcs":   {"source": "dblp", "dblp": "conf/icdcs",   "prefix": "icdcs",   "area": "distributed"},
    "iwqos":   {"source": "dblp", "dblp": "conf/iwqos",   "prefix": "iwqos",   "area": "network"},
    "secon":   {"source": "dblp", "dblp": "conf/secon",   "prefix": "secon",   "area": "network"},
    "hpca":    {"source": "dblp", "dblp": "conf/hpca",    "prefix": "hpca",    "area": "arch"},
    "dsn":     {"source": "dblp", "dblp": "conf/dsn",     "prefix": "dsn",     "area": "dependability"},
    "ipdps":   {"source": "dblp", "dblp": "conf/ipdps",   "prefix": "ipdps",   "area": "parallel"},
    "sp":      {"source": "dblp", "dblp": "conf/sp",      "prefix": "sp",      "area": "security"},

    # ---------------- 开放获取的列表页 ----------------
    "cvpr":    {"source": "page", "page": "https://openaccess.thecvf.com/CVPR{yyyy}?day=all", "parser": "cvf",     "area": "cv"},
    "iccv":    {"source": "page", "page": "https://openaccess.thecvf.com/ICCV{yyyy}?day=all", "parser": "cvf",     "area": "cv"},
    "neurips": {"source": "page", "page": "https://proceedings.neurips.cc/paper_files/paper/{yyyy}", "parser": "neurips", "area": "ml"},
    "ijcai":   {"source": "page", "page": "https://www.ijcai.org/proceedings/{yyyy}/", "parser": "ijcai", "area": "ai"},
}

# 需要机构权限 / 有反爬（Cloudflare）的域名 → 默认走浏览器
BROWSER_DOMAINS = ("dl.acm.org", "ieeexplore.ieee.org", "doi.org", "link.springer.com")


# ============================================================================
# 通用工具
# ============================================================================
def log(msg):
    print(msg, flush=True)


def parse_conf(name):
    """'sigcomm24' / 'sigcomm2024' / 'SIGCOMM-2024' → ('sigcomm', 2024)"""
    m = re.fullmatch(r"([a-zA-Z]+)[-_]?(\d{2}|\d{4})", name.strip())
    if not m:
        raise SystemExit(f"无法解析会议名 '{name}'，应形如 sigcomm24 或 sigcomm2024")
    series, year = m.group(1).lower(), int(m.group(2))
    if year < 100:
        year += 2000
    return series, year


def safe_filename(s, maxlen=150):
    s = re.sub(r'[\\/*?:"<>|\r\n\t]', "", s)
    s = re.sub(r"\s+", "_", s.strip())
    return s[:maxlen].rstrip("._") or "paper"


def new_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    adapter = requests.adapters.HTTPAdapter(max_retries=3)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s


def fetch_text(session, url, retries=3, timeout=30):
    last = None
    for i in range(retries):
        try:
            r = session.get(url, timeout=timeout)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"获取失败 {url}: {last}")


def read_page(session, src):
    """src 可以是 URL、本地 HTML 文件或包含 HTML 的目录；返回 [(base_url, html_text)]"""
    if re.match(r"https?://", src):
        return [(src, fetch_text(session, src))]
    p = Path(src)
    if p.is_dir():
        files = sorted(x for x in p.rglob("*.htm*") if "_files" not in x.parent.name)
    elif p.exists():
        files = [p]
    else:
        raise SystemExit(f"找不到页面：{src}")
    return [("", f.read_text(encoding="utf-8", errors="ignore")) for f in files]


def make_entry(url, title="", pid="", method=None, doi="", fallbacks=None, **extra):
    host = urlparse(url).netloc
    if method is None:
        method = "browser" if any(host.endswith(d) for d in BROWSER_DOMAINS) else "requests"
    e = {"id": pid, "title": title.strip(), "url": url, "method": method}
    if doi:
        e["doi"] = doi
    if fallbacks:
        e["fallbacks"] = fallbacks
    e.update({k: v for k, v in extra.items() if v})
    return e


# ============================================================================
# DOI → PDF 链接
# ============================================================================
def doi_to_entry(doi, title=""):
    doi = doi.strip()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.I)
    if doi.startswith("10.1145/"):
        return make_entry(f"https://dl.acm.org/doi/pdf/{doi}", title,
                          pid=doi.split("/", 1)[1], doi=doi, publisher="acm")
    if doi.startswith("10.1109/"):
        arn = doi.rsplit(".", 1)[-1]
        if arn.isdigit() and len(arn) >= 6:
            return make_entry(f"https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber={arn}&ref=",
                              title, pid=arn, doi=doi, publisher="ieee")
    # 其他出版社 / 老式 DOI：交给浏览器跟随 doi.org 跳转
    return make_entry(f"https://doi.org/{doi}", title,
                      pid=safe_filename(doi.split("/", 1)[-1]), doi=doi, publisher="other")


def ieee_arnumber_entry(arn, title=""):
    return make_entry(f"https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber={arn}&ref=",
                      title, pid=str(arn), publisher="ieee")


# ============================================================================
# Source 1: USENIX
# ============================================================================
def collect_usenix(session, usenix_prefix, year, args):
    conf = f"{usenix_prefix}{year % 100:02d}"
    base = f"https://www.usenix.org/conference/{conf}/technical-sessions"
    log(f"[usenix] 解析 {base}")
    soup = BeautifulSoup(fetch_text(session, base), "html.parser")

    talks = {}
    for a in soup.select(f'a[href*="/conference/{conf}/presentation/"]'):
        url = urljoin(base, a["href"]).split("#")[0].split("?")[0]
        title = a.get_text(" ", strip=True)
        if url not in talks or (title and not talks[url]):
            talks[url] = title
    log(f"[usenix] 共 {len(talks)} 个 presentation 页面")

    def guess_pdfs(slug):
        # 与旧脚本相同的几种文件名规律，作为兜底
        cands = [f"https://www.usenix.org/system/files/{conf}-{slug}.pdf",
                 f"https://www.usenix.org/system/files/{conf}-{slug.replace('-', '_')}.pdf",
                 f"https://www.usenix.org/system/files/{conf}-{slug.split('-')[0]}.pdf"]
        return list(dict.fromkeys(cands))

    def one(item):
        url, title = item
        slug = url.rstrip("/").split("/")[-1]
        if args.fast:
            c = guess_pdfs(slug)
            return make_entry(c[0], title, pid=f"{conf}-{slug}", method="requests", fallbacks=c[1:])
        try:
            psoup = BeautifulSoup(fetch_text(session, url), "html.parser")
        except RuntimeError as e:
            log(f"  [!] {e}，改用猜测的链接")
            c = guess_pdfs(slug)
            return make_entry(c[0], title, pid=f"{conf}-{slug}", method="requests", fallbacks=c[1:])
        pdf = None
        node = psoup.select_one(".field-name-field-final-paper-pdf a[href$='.pdf']")
        if node:
            pdf = urljoin(url, node["href"])
        else:
            for a in psoup.select("a[href$='.pdf']"):
                h = a["href"]
                if "/system/files/" in h and conf in h and not re.search(r"slides|poster|appendix", h, re.I):
                    pdf = urljoin(url, h)
                    break
        if not pdf:
            return None  # keynote / panel 等没有论文
        if not title:
            h1 = psoup.select_one("h1")
            title = h1.get_text(" ", strip=True) if h1 else slug
        return make_entry(pdf, title, pid=Path(urlparse(pdf).path).stem, method="requests")

    results = [None] * len(talks)
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(one, it): i for i, it in enumerate(talks.items())}
        for n, f in enumerate(as_completed(futs), 1):
            results[futs[f]] = f.result()
            if n % 20 == 0:
                log(f"  ... {n}/{len(talks)}")
    return [e for e in results if e]  # 保持官网上的顺序


# ============================================================================
# Source 2: DBLP（ACM / IEEE 通用）
# ============================================================================
DBLP_API = "https://dblp.org/search/publ/api"


def dblp_find_tocs(session, series_path, prefix, year):
    """在 DBLP 会议索引页里找出当年的所有卷，如 asplos2024-1 / -2 / -3"""
    idx_url = f"https://dblp.org/db/{series_path}/index.html"
    html = fetch_text(session, idx_url)
    pat = re.compile(rf"db/{re.escape(series_path)}/({re.escape(prefix)}{year}(?:-\d+)?)\.html")
    names = sorted(set(pat.findall(html)))
    return [f"db/{series_path}/{n}.bht" for n in names]


def dblp_query_toc(session, toc):
    hits, first = [], 0
    while True:
        params = {"q": f"toc:{toc}:", "h": 1000, "f": first, "format": "json"}
        for i in range(4):
            try:
                r = session.get(DBLP_API, params=params, timeout=60)
                if r.status_code == 429:
                    time.sleep(10 * (i + 1))
                    continue
                r.raise_for_status()
                break
            except requests.RequestException:
                time.sleep(3 * (i + 1))
        else:
            raise RuntimeError(f"DBLP 查询失败: {toc}")
        res = r.json()["result"]["hits"]
        batch = res.get("hit", [])
        hits.extend(h["info"] for h in batch)
        total = int(res.get("@total", 0))
        first += len(batch)
        if not batch or first >= total:
            return hits


def page_count(pages):
    m = re.fullmatch(r"(?:\d+:)?(\d+)\s*-\s*(?:\d+:)?(\d+)", str(pages or "").strip())
    return int(m.group(2)) - int(m.group(1)) + 1 if m else None


def collect_dblp(session, series_path, prefix, year, args):
    tocs = args.dblp_toc or dblp_find_tocs(session, series_path, prefix, year)
    if not tocs:
        raise SystemExit(f"[dblp] 在 https://dblp.org/db/{series_path}/ 没找到 {prefix}{year} 的卷，"
                         f"可用 --dblp-toc db/{series_path}/xxx.bht 手动指定")
    entries, skipped = [], 0
    for toc in tocs:
        infos = dblp_query_toc(session, toc)
        log(f"[dblp] {toc}: {len(infos)} 条记录")
        for info in infos:
            if info.get("type") == "Editorship":
                continue
            title = re.sub(r"\.$", "", info.get("title", ""))
            n = page_count(info.get("pages"))
            if args.min_pages and n is not None and n < args.min_pages:
                skipped += 1
                continue
            doi = info.get("doi")
            ees = info.get("ee") or []
            ees = [ees] if isinstance(ees, str) else ees
            if not doi:
                doi = next((re.sub(r"^https?://doi\.org/", "", x) for x in ees if "doi.org/" in x), None)
            if doi:
                entries.append(doi_to_entry(doi, title))
                continue
            # 没 DOI 时尝试 ee 中的 ieeexplore document 链接
            arn = next((re.search(r"ieeexplore\.ieee\.org/document/(\d+)", x).group(1)
                        for x in ees if re.search(r"ieeexplore\.ieee\.org/document/\d+", x)), None)
            if arn:
                entries.append(ieee_arnumber_entry(arn, title))
            elif ees:
                entries.append(make_entry(ees[0], title, pid=safe_filename(title, 60)))
    if skipped:
        log(f"[dblp] 过滤掉 {skipped} 篇页数 < {args.min_pages} 的短文（poster/demo/front matter），"
            f"不想过滤请加 --min-pages 0")
    return entries


# ============================================================================
# Source 3: 页面解析（在线 URL / 本地保存的 HTML）
# ============================================================================
DOI_RE = re.compile(r"(10\.\d{4,9}/[^\s\"'<>?#&]+)")


def is_paper_doi(doi):
    """ACM 论文 DOI 形如 10.1145/3718958.3750468（整本 proceedings 为 10.1145/3718958）；
    IEEE 论文 DOI 以 arnumber 结尾（整本为 10.1109/INFOCOM52122.2024）"""
    if doi.count("/") != 1:
        return False
    prefix, suffix = doi.split("/")
    if prefix == "10.1145":
        return re.fullmatch(r"\d+\.\d+", suffix) is not None
    if prefix == "10.1109":
        return re.search(r"\.\d{6,}$", suffix) is not None
    return True


def guess_title(a):
    """链接文字不像标题（如 'PDF'、图标）时，到所在行 / 块里找第一段足够长的文字"""
    text = a.get_text(" ", strip=True)
    if len(text) >= 20 and not text.lower().startswith(("http", "doi", "10.")):
        return text
    node = a
    for _ in range(4):
        node = node.parent
        if node is None or node.name in ("body", "table", "tbody", "ul", "ol"):
            break
        for st in node.stripped_strings:
            if len(st) >= 20 and not st.lower().startswith(("http", "doi", "10.")):
                return st
    return ""


def parse_links_auto(base, soup):
    """自动识别 ACM / IEEE / doi.org 链接（ACM 目录页、IEEE 目录页、会议 program 页都适用）"""
    entries, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base, a["href"]) if base else a["href"]
        if href.startswith("/doi/"):
            href = "https://dl.acm.org" + href
        m_ieee = re.search(r"ieeexplore\.ieee\.org/(?:stamp/stamp\.jsp\?.*?arnumber=|stampPDF/getPDF\.jsp\?.*?arnumber=|document/)(\d+)", href)
        if m_ieee:
            key = ("ieee", m_ieee.group(1))
            if key not in seen:
                seen.add(key)
                entries.append(ieee_arnumber_entry(m_ieee.group(1), guess_title(a)))
            continue
        if "dl.acm.org/doi/" in href or "doi.org/10." in href:
            if "/doi/proceedings/" in href or "/doi/book/" in href:
                continue
            m = DOI_RE.search(href)
            if not m:
                continue
            doi = m.group(1).rstrip("/.")
            if not is_paper_doi(doi):  # 跳过整本 proceedings / 书 / 附件的 DOI
                continue
            key = ("doi", doi.lower())
            if key not in seen:
                seen.add(key)
                entries.append(doi_to_entry(doi, guess_title(a)))
    # 标题：ACM 目录页里 h5.issue-item__title 里的链接就是论文页
    titles = {}
    for h in soup.select(".issue-item__title a[href], h3.issue-item__title a[href]"):
        m = DOI_RE.search(h["href"])
        if m:
            titles[m.group(1).lower()] = h.get_text(" ", strip=True)
    for h in soup.select("xpl-issue-results-item h2 a[href], .result-item h2 a[href]"):
        m = re.search(r"/document/(\d+)", h["href"])
        if m:
            titles[m.group(1)] = h.get_text(" ", strip=True)
    for e in entries:
        e["title"] = titles.get(e.get("doi", "").lower()) or titles.get(e["id"]) or e["title"]
    return entries


def parse_links_cvf(base, soup):
    out = []
    for a in soup.find_all("a", href=True):
        if re.search(r"/content/[^/]+/papers/.+_paper\.pdf$", a["href"]):
            url = urljoin(base or "https://openaccess.thecvf.com/", a["href"])
            dt = a.find_parent("dd")
            prev = dt.find_previous_sibling("dt") if dt else None
            title = prev.get_text(" ", strip=True) if prev else ""
            out.append(make_entry(url, title, pid=Path(url).stem.replace("_paper", "")))
    return out


def parse_links_neurips(base, soup):
    out = []
    for a in soup.find_all("a", href=True):
        m = re.search(r"/paper_files/paper/(\d+)/hash/([0-9a-f]{32})-Abstract-([\w_]+)\.html", a["href"])
        if m:
            y, h, track = m.groups()
            url = f"https://proceedings.neurips.cc/paper_files/paper/{y}/file/{h}-Paper-{track}.pdf"
            out.append(make_entry(url, a.get_text(" ", strip=True), pid=h))
    return out


def parse_links_ijcai(base, soup):
    out = []
    for a in soup.find_all("a", href=True):
        if re.search(r"/proceedings/\d{4}/\d{4}\.pdf$", a["href"]):
            url = urljoin(base or "https://www.ijcai.org/", a["href"])
            box = a.find_parent(class_="paper_wrapper")
            t = box.select_one(".title") if box else None
            out.append(make_entry(url, t.get_text(" ", strip=True) if t else "",
                                  pid="ijcai" + "-".join(url.split("/")[-2:]).replace(".pdf", "")))
    return out


def parse_links_regex(pattern):
    rx = re.compile(pattern)

    def parse(base, soup):
        out = []
        for a in soup.find_all("a", href=True):
            href = urljoin(base, a["href"]) if base else a["href"]
            if rx.search(href):
                u = urlparse(href)
                query = "_".join(v[0] for v in parse_qs(u.query).values())
                pid = safe_filename(query or Path(u.path).stem, 80)
                out.append(make_entry(href, guess_title(a), pid=pid))
        return out
    return parse


PARSERS = {"auto": parse_links_auto, "cvf": parse_links_cvf,
           "neurips": parse_links_neurips, "ijcai": parse_links_ijcai}


def collect_page(session, sources, parser_name, args):
    parser = parse_links_regex(args.pattern) if args.pattern else PARSERS[parser_name]
    entries = []
    for src in sources:
        for base, html in read_page(session, src):
            got = parser(base, BeautifulSoup(html, "html.parser"))
            log(f"[page] {src}: {len(got)} 个链接")
            entries.extend(got)
    return entries


# ============================================================================
# collect 主流程
# ============================================================================
def dedup(entries):
    out, seen = [], set()
    for e in entries:
        k = e["url"]
        if k in seen:
            continue
        seen.add(k)
        out.append(e)
    # 保证 id 唯一
    cnt = {}
    for e in out:
        e["id"] = e["id"] or safe_filename(e["title"], 60) or "paper"
        cnt[e["id"]] = cnt.get(e["id"], 0) + 1
        if cnt[e["id"]] > 1:
            e["id"] = f"{e['id']}_{cnt[e['id']]}"
    return out


def cmd_collect(args):
    series, year = parse_conf(args.conf)
    conf = f"{series}{year % 100:02d}"
    spec = dict(CONFERENCES.get(series, {}))

    # 命令行显式指定的来源优先
    if args.page:
        default_parser = spec.get("parser", "auto") if spec.get("source") == "page" else "auto"
        spec = {"source": "page", "parser": args.parser or default_parser}
    elif args.dblp:
        spec = {"source": "dblp", "dblp": args.dblp, "prefix": args.dblp_prefix or args.dblp.split("/")[-1]}
    elif args.usenix:
        spec = {"source": "usenix", "usenix": args.usenix}
    elif args.dblp_toc:
        spec = {"source": "dblp", "dblp": "", "prefix": ""}
    if not spec:
        raise SystemExit(f"注册表里没有 '{series}'，请用 --usenix / --dblp / --page 指定来源，"
                         f"或在 CONFERENCES 中添加一行")

    session = new_session()
    src = spec["source"]
    if src == "usenix":
        entries = collect_usenix(session, spec["usenix"], year, args)
    elif src == "dblp":
        entries = collect_dblp(session, spec["dblp"], spec["prefix"], year, args)
    else:
        pages = args.page or [spec["page"].format(yyyy=year, yy=f"{year % 100:02d}")]
        entries = collect_page(session, pages, spec.get("parser", "auto"), args)

    entries = dedup(entries)
    if not entries:
        raise SystemExit("[collect] 没有收集到任何链接，请检查来源 / 页面是否完整保存")

    out_dir = Path(args.links_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "conf": conf, "series": series, "year": year, "source": src,
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "count": len(entries), "papers": entries,
    }
    jpath = out_dir / f"{conf}.json"
    jpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / f"{conf}.txt").write_text("\n".join(e["url"] for e in entries) + "\n", encoding="utf-8")

    by_method = {}
    for e in entries:
        by_method[e["method"]] = by_method.get(e["method"], 0) + 1
    log(f"[collect] {conf}: {len(entries)} 篇 {by_method} → {jpath}")
    if by_method.get("browser"):
        log("          含需权限的链接：把 json 拷到有权限的电脑上执行 download 即可")
    return jpath


# ============================================================================
# download
# ============================================================================
def load_manifest(path):
    p = Path(path)
    if not p.exists():
        # 允许直接写会议名
        cand = DEFAULT_LINKS_DIR / f"{path}.json"
        if cand.exists():
            p = cand
        else:
            raise SystemExit(f"找不到链接文件 {path}")
    if p.suffix == ".json":
        m = json.loads(p.read_text(encoding="utf-8"))
        return m.get("conf", p.stem), m["papers"]
    # 兼容旧的纯文本链接列表（每行一个 URL，允许带引号和逗号）
    papers = []
    for line in p.read_text(encoding="utf-8").splitlines():
        url = line.strip().strip(",").strip('"').strip("'")
        if url.startswith("http"):
            m = DOI_RE.search(url)
            if "dl.acm.org" in url and m:
                papers.append(doi_to_entry(m.group(1)))
            else:
                papers.append(make_entry(url, pid=safe_filename(Path(urlparse(url).path).stem or url[-40:], 80)))
    return p.stem, dedup(papers)


def target_name(e, style):
    if style == "title" and e.get("title"):
        return safe_filename(e["title"]) + ".pdf"
    if style == "id_title" and e.get("title"):
        return safe_filename(f"{e['id']}_{e['title']}") + ".pdf"
    return safe_filename(e["id"]) + ".pdf"


def is_pdf(path):
    try:
        with open(path, "rb") as f:
            return f.read(5) == b"%PDF-"
    except OSError:
        return False


def load_cookies(session, cookie_file):
    if not cookie_file:
        return
    jar = http.cookiejar.MozillaCookieJar(cookie_file)
    jar.load(ignore_discard=True, ignore_expires=True)
    session.cookies.update(jar)
    log(f"[download] 已加载 cookies: {cookie_file}")


def download_requests(session, e, dst, delay):
    for url in [e["url"]] + e.get("fallbacks", []):
        try:
            with session.get(url, stream=True, timeout=60, allow_redirects=True) as r:
                if r.status_code != 200:
                    continue
                tmp = dst.with_suffix(".part")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(65536):
                        f.write(chunk)
                if is_pdf(tmp):
                    tmp.replace(dst)
                    return True, url
                tmp.unlink(missing_ok=True)
        except requests.RequestException:
            pass
        finally:
            time.sleep(delay)
    return False, None


class BrowserDownloader:
    """用 Chrome 下载需要权限的论文（ACM / IEEE）。
    --profile-dir 指定 Chrome 用户目录，登录一次（机构 SSO / 过 Cloudflare）后可复用。"""

    def __init__(self, tmp_dir, profile_dir=None, headless=False, timeout=90,
                 chrome_binary=None, chromedriver=None):
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        self.tmp_dir = Path(tmp_dir).resolve()
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        opts = Options()
        if chrome_binary:
            opts.binary_location = chrome_binary
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--disable-gpu")
        if headless:
            opts.add_argument("--headless=new")
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            opts.add_argument("--no-sandbox")  # Linux 下以 root 运行时 Chrome 需要
        if profile_dir:
            opts.add_argument(f"--user-data-dir={Path(profile_dir).resolve()}")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("prefs", {
            "download.default_directory": str(self.tmp_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,  # PDF 直接下载，不在浏览器里打开
        })
        from selenium.webdriver.chrome.service import Service
        try:
            # selenium>=4.6 自带驱动管理；也可用 --chromedriver 指定本地驱动
            self.driver = webdriver.Chrome(service=Service(chromedriver) if chromedriver else None, options=opts)
        except Exception:
            if chromedriver:
                raise
            from webdriver_manager.chrome import ChromeDriverManager
            self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
        # 直接触发下载的 URL 可能让 get() 一直等到页面超时，这里设短一点，文件由 _wait_new_file 去等
        self.driver.set_page_load_timeout(min(timeout, 45))

    def _files(self):
        return {p.name for p in self.tmp_dir.iterdir()}

    def _wait_new_file(self, before, timeout):
        start, clicked = time.time(), False
        while time.time() - start < timeout:
            new = [self.tmp_dir / n for n in self._files() - before]
            done = [p for p in new if not p.name.endswith((".crdownload", ".tmp", ".part"))]
            pending = [p for p in new if p.name.endswith(".crdownload")]
            if done and not pending:
                f = done[0]
                size = f.stat().st_size
                time.sleep(1)
                if size > 0 and size == f.stat().st_size:
                    return f
            # 页面没触发下载（例如落在 ACM epdf 阅读器页面）→ 尝试点下载按钮
            if not new and not clicked and time.time() - start > 8:
                clicked = self._try_click_download()
            time.sleep(1)
        return None

    def _try_click_download(self):
        from selenium.webdriver.common.by import By
        xps = ["//a[contains(@class,'download-button')]",
               "//a[contains(@href,'/doi/pdf/')]",
               "//a[contains(@href,'stamp.jsp')]"]
        for xp in xps:
            try:
                for el in self.driver.find_elements(By.XPATH, xp):
                    if el.is_displayed():
                        self.driver.execute_script("arguments[0].click();", el)
                        return True
            except Exception:
                pass
        return False

    def _resolve(self, url):
        """doi.org / 论文详情页 → 直接 PDF 地址"""
        if "doi.org/" not in url:
            return url
        self.driver.get(url)
        time.sleep(3)
        cur = self.driver.current_url
        m = re.search(r"ieeexplore\.ieee\.org/document/(\d+)", cur)
        if m:
            return f"https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber={m.group(1)}&ref="
        m = re.search(r"dl\.acm\.org/doi/(?:abs/|full/)?(10\.\d+/[^?#]+)", cur)
        if m:
            return f"https://dl.acm.org/doi/pdf/{m.group(1)}"
        return cur

    def fetch(self, e, dst):
        for url in [e["url"]] + e.get("fallbacks", []):
            before = self._files()
            try:
                url = self._resolve(url)
                self.driver.get(url)
            except Exception as ex:
                # 直接触发下载时，部分 Chrome 版本会抛超时/中断异常，忽略继续等文件
                log(f"    [i] driver.get: {type(ex).__name__}")
            f = self._wait_new_file(before, self.timeout)
            if f and is_pdf(f):
                f.replace(dst)
                return True, url
            if f:
                f.unlink(missing_ok=True)  # 下到的是 HTML（没权限 / 验证页）
        return False, None

    def close(self):
        try:
            self.driver.quit()
        except Exception:
            pass


def cmd_download(args):
    conf, papers = load_manifest(args.links)
    out = Path(args.out) if args.out else DEFAULT_PDF_ROOT / f"{conf}_papers"
    out.mkdir(parents=True, exist_ok=True)
    if args.only:
        rx = re.compile(args.only, re.I)
        papers = [p for p in papers if rx.search(p.get("title", "")) or rx.search(p["id"])]
    if args.limit:
        papers = papers[:args.limit]

    todo, ok, skipped, failed = [], [], [], []
    for e in papers:
        dst = out / target_name(e, args.name)
        if dst.exists() and is_pdf(dst):
            skipped.append(e)
        else:
            todo.append((e, dst))
    log(f"[download] {conf}: 共 {len(papers)} 篇，已存在 {len(skipped)}，待下载 {len(todo)} → {out}")

    mode = args.mode
    use_req = lambda e: mode == "requests" or (mode == "auto" and e["method"] == "requests")
    req_jobs = [(e, d) for e, d in todo if use_req(e)]
    brw_jobs = [(e, d) for e, d in todo if not use_req(e)]

    # ---- 1) 开放获取：requests 并发下载 ----
    if req_jobs:
        session = new_session()
        load_cookies(session, args.cookies)
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(download_requests, session, e, d, args.delay): (e, d) for e, d in req_jobs}
            for i, f in enumerate(as_completed(futs), 1):
                e, d = futs[f]
                good, _ = f.result()
                (ok if good else failed).append(e)
                log(f"  [{i}/{len(req_jobs)}] {'✔' if good else '✘'} {d.name}")

    # ---- 2) 需要权限：浏览器逐篇下载 ----
    if brw_jobs:
        bd = BrowserDownloader(out / ".browser_tmp", args.profile_dir, args.headless, args.timeout,
                               args.chrome_binary, args.chromedriver)
        try:
            if args.login:
                bd.driver.get(args.login if args.login.startswith("http") else brw_jobs[0][0]["url"])
                input("[download] 请在打开的浏览器里完成登录 / 人机验证，然后回到这里按回车继续...")
            for i, (e, d) in enumerate(brw_jobs, 1):
                good, _ = bd.fetch(e, d)
                (ok if good else failed).append(e)
                log(f"  [{i}/{len(brw_jobs)}] {'✔' if good else '✘'} {d.name}  {e.get('title', '')[:60]}")
                time.sleep(args.delay)
        finally:
            bd.close()

    # ---- 汇总 ----
    with open(out / "index.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["file", "title", "doi", "url", "exists"])
        for e in papers:
            dst = out / target_name(e, args.name)
            w.writerow([dst.name, e.get("title", ""), e.get("doi", ""), e["url"], dst.exists()])
    log(f"[download] 完成：成功 {len(ok)}，跳过 {len(skipped)}，失败 {len(failed)}")
    if failed:
        fpath = out / "failed.json"
        fpath.write_text(json.dumps({"conf": conf, "papers": failed}, ensure_ascii=False, indent=2),
                         encoding="utf-8")
        log(f"           失败列表已写入 {fpath}，可直接重跑：python paper_catch.py download {fpath}")


# ============================================================================
# list / run / CLI
# ============================================================================
def cmd_list(args):
    log(f"{'key':<12}{'source':<8}{'area':<22}where")
    for k, v in CONFERENCES.items():
        where = v.get("usenix") or v.get("dblp") or v.get("page")
        log(f"{k:<12}{v['source']:<8}{v.get('area', ''):<22}{where}")
    log("\n不在表中的会议：collect <name><yy> 加 --usenix/--dblp/--page 即可。")


def cmd_run(args):
    args.links = str(cmd_collect(args))
    cmd_download(args)


def build_parser():
    ap = argparse.ArgumentParser(description="会议论文 PDF 链接收集 + 下载（USENIX / ACM / IEEE / 开放获取）",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="列出内置的会议").set_defaults(func=cmd_list)

    def add_collect_args(p):
        p.add_argument("conf", help="会议名+年份，如 sigcomm24 / nsdi2025")
        p.add_argument("--page", nargs="+", help="改用页面解析：URL、本地 HTML 文件或目录（可多个）")
        p.add_argument("--parser", choices=list(PARSERS), help="页面解析器（默认 auto：识别 ACM/IEEE/DOI）")
        p.add_argument("--pattern", help="自定义正则，匹配页面中的 PDF 链接（配合 --page）")
        p.add_argument("--dblp", help="DBLP series 路径，如 conf/sigcomm")
        p.add_argument("--dblp-prefix", help="DBLP toc 文件名前缀（默认同 series 名）")
        p.add_argument("--dblp-toc", nargs="+", help="直接指定 DBLP toc，如 db/conf/asplos/asplos2024-1.bht")
        p.add_argument("--min-pages", type=int, default=5,
                       help="DBLP 来源时过滤页数少于该值的条目（poster/demo），默认 5，0 表示不过滤")
        p.add_argument("--usenix", help="USENIX 会议前缀，如 nsdi / usenixsecurity")
        p.add_argument("--fast", action="store_true", help="USENIX：不逐篇打开 presentation 页，直接按规律拼 PDF 链接")
        p.add_argument("--links-dir", default=str(DEFAULT_LINKS_DIR), help="链接文件输出目录")

    def add_download_args(p):
        p.add_argument("--out", help=f"PDF 保存目录（默认 {DEFAULT_PDF_ROOT}/<conf>_papers）")
        p.add_argument("--mode", choices=["auto", "requests", "browser"], default="auto",
                       help="auto：开放获取用 requests，ACM/IEEE 用浏览器")
        p.add_argument("--name", choices=["id", "title", "id_title"], default="id", help="PDF 文件命名方式")
        p.add_argument("--profile-dir", help="Chrome 用户目录（保存登录状态，推荐）")
        p.add_argument("--login", nargs="?", const="first",
                       help="下载前先打开浏览器让你手动登录 / 过验证（可给登录页 URL）")
        p.add_argument("--headless", action="store_true", help="浏览器无头模式")
        p.add_argument("--chrome-binary", help="Chrome/Chromium 可执行文件路径（一般不用填）")
        p.add_argument("--chromedriver", help="chromedriver 路径（一般不用填，selenium 会自动下载）")
        p.add_argument("--cookies", help="Netscape 格式 cookies.txt，给 requests 模式用")
        p.add_argument("--timeout", type=int, default=90, help="浏览器单篇下载超时秒数")
        p.add_argument("--delay", type=float, default=1.0, help="每篇之间的间隔秒数")
        p.add_argument("--only", help="只下载标题 / id 匹配该正则的论文")
        p.add_argument("--limit", type=int, help="最多下载 N 篇（测试用）")

    p = sub.add_parser("collect", help="收集论文 PDF 链接 → links/<conf>.json")
    add_collect_args(p)
    p.add_argument("--workers", type=int, default=4, help="并发数")
    p.set_defaults(func=cmd_collect)

    p = sub.add_parser("download", help="按链接文件下载 PDF")
    p.add_argument("links", help="links/<conf>.json、旧格式 .txt，或直接写会议名（如 sigcomm24）")
    add_download_args(p)
    p.add_argument("--workers", type=int, default=2, help="requests 模式并发数")
    p.set_defaults(func=cmd_download)

    p = sub.add_parser("run", help="collect + download 一步完成")
    add_collect_args(p)
    add_download_args(p)
    p.add_argument("--workers", type=int, default=2, help="并发数")
    p.set_defaults(func=cmd_run)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except KeyboardInterrupt:
        log("\n[!] 已中断，已下载的文件会保留，重跑会自动跳过")
        sys.exit(1)


if __name__ == "__main__":
    main()
