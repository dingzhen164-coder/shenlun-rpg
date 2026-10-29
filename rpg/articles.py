"""📅 每日文章（申论的时政简报里）：按来源（杂志 / 网站）、按分类抓文章，存到本地，一键精读。

抓取：只用标准库 urllib，在用户自己的电脑上抓。每个来源 = 一个列表页网址；从列表页里挑出“长得像文章”的链接
（网址里带日期 / 编号），逐篇取正文（通用提取：标题取 h1 / title，日期取 meta 或网址，正文取成段的 <p>）。
某个来源改版或连不上，只提示这一个来源失败，别的照常。

存放：训练/时政文章/<年-月>/<日期>-<编号>-<标题>.md（坚果云同步，换电脑也在），开头是
  ---
  id: 8 位编号（网址的哈希，同一篇不重复抓）
  title / source / category / url / date / fetched
  ---
  正文（一段一行）
精读结果：训练/时政文章/精读/<编号>.json（AI 讲过的存下来，不重复花钱）。
自定义来源：训练/时政文章/来源.json  [{name, url, category}]。
已读 / 收藏 / 来源开关：存档 state["articles"] = {read: {id: 日期}, star: [id], off: [来源名], on: [默认关的来源里被打开的]}。

精读（五步，程序校验，AI 只提炼；version=2）：{version, step1{old_words[{term,note}], verbs[{term,note}], new_terms[{term,definition}]},
  step2{thesis, parts[{point,kind}], paragraphs[{no,summary,type}]}, step3{items[{direction,domain,landing,source}]},
  step4{quotes[{kind,text,use}]}, step5{yuyan[{type,question}], shenlun[{type,question}]}}
  词语 / 原文方向 / 金句必须是原文里真有的，不在的丢掉；段号必须在送审范围内；shenlun 的题型只能是本科目题型名；第六步“模拟输出”由用户自己做，不生成。
  旧版精读（无 version 字段）照常显示，点“重新精读”才换成新版。
摘编：训练/时政文章/摘编/<编号>.json  {id,title,source,url,date,saved,countermeasures[step3.items],quotes[step4.quotes]}，在档案室「摘编」翻阅（只读），不是复习卡片。
调用：rpg/api.py 的 /api/articles*；网页 web/articles.js。
"""
import datetime as dt
import hashlib
import html
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from . import net

DIR = "时政文章"
CATEGORIES = ["社论评论", "党政治理", "经济", "民生社会", "文化教育", "生态", "科技", "国际", "其他"]
CAT_WORDS = [("生态", ("生态", "环保", "绿色", "碳", "污染", "绿水青山")), ("科技", ("科技", "创新", "人工智能", "智能", "数字", "算力", "航天")),
             ("经济", ("经济", "消费", "产业", "市场", "服务业", "金融", "投资", "就业", "贸易", "企业")),
             ("文化教育", ("文化", "教育", "学校", "青少年", "文明", "文旅", "读书", "非遗")),
             ("民生社会", ("民生", "养老", "医疗", "社区", "群众", "出行", "食品", "安全", "社保", "物业")),
             ("国际", ("国际", "全球", "外交", "世界", "中美", "峰会", "联合国")),
             ("党政治理", ("党", "治理", "基层", "干部", "作风", "改革", "法治", "政务", "监督", "反腐"))]
# 内置来源：url = 列表页，pat = 文章网址的样子（正则），cat = 默认分类（空 = 按标题猜），off = 没实测过，默认关
SOURCES = [
    {"name": "人民网·观点", "url": "http://opinion.people.com.cn/", "pat": r"/n1/\d{4}/\d{4}/c\d+-\d+\.html", "cat": ""},
    {"name": "新华网·评论", "url": "http://www.xinhuanet.com/comments/", "pat": r"/comments/\d{8}/[0-9a-f]{32}/c\.html", "cat": "社论评论"},
    {"name": "求是网", "url": "http://www.qstheory.cn/", "pat": r"/\d{8}/[0-9a-f]{32}/c\.html", "cat": "党政治理"},
    {"name": "光明网·评论", "url": "https://guancha.gmw.cn/", "pat": r"/\d{4}-\d{2}/\d{2}/\d+\.htm", "cat": "", "off": True},
    {"name": "半月谈", "url": "http://www.banyuetan.org/", "pat": r"/\d{8}/\d+\.html?|/\d{4}-\d{2}/\d{2}/\w+\.html?", "cat": "党政治理", "off": True},
]
CUSTOM_PAT = r"/\d{4}[-/]?\d{2}[-/]?\d{2}/|c\d{5,}|/\d{6,}\.html?"
PER_SOURCE = 10          # 一个来源一次最多新抓几篇
MAX_LIST_PAGES = 20      # 历史列表检索有界，避免网站循环链接拖住任务
MAX_CANDIDATES = 300
MIN_BODY = 200           # 正文少于这么多字就不当文章
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
JOB = {"running": False, "log": [], "added": 0, "done": 0, "total": 0, "t": 0}
LOCK = threading.Lock()


class ArticleError(Exception):
    pass


def folder(paths):
    return paths.train / DIR


def _safe(name):
    return re.sub(r'[\\/:*?"<>|\s]+', "_", name).strip("_.")[:40] or "无题"


def aid(url):
    return hashlib.md5(url.encode("utf-8")).hexdigest()[:8]


# ---------------------------------------------------------------- 网页 → 文字
def fetch(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})
    with net.urlopen(req, timeout=timeout) as r:
        raw = r.read(3_000_000)
        head = r.headers.get_content_charset()
    m = re.search(rb'charset=["\']?([\w-]+)', raw[:4000], re.I)
    for enc in (m.group(1).decode("ascii", "ignore") if m else None, head, "utf-8", "gb18030"):
        if not enc:
            continue
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "replace")


class _Page(HTMLParser):
    """收集：链接（href + 文字）、段落 <p>、h1、title、meta"""
    SKIP = {"script", "style", "noscript", "nav", "footer", "header", "aside", "form"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.paras, self.h1, self.title, self.meta = [], [], "", "", {}
        self._skip = 0
        self._a = None
        self._p = None
        self._h1 = None
        self._title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP:
            self._skip += 1
        elif tag == "a" and a.get("href"):
            self._a = [a["href"], ""]
        elif tag == "p" and not self._skip:
            self._p = []
        elif tag == "h1":
            self._h1 = []
        elif tag == "title":
            self._title = True
        elif tag == "meta" and (a.get("name") or a.get("property")):
            self.meta[(a.get("name") or a.get("property")).lower()] = a.get("content") or ""
        elif tag == "br" and self._p is not None:
            self._p.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        elif tag == "a" and self._a:
            self.links.append(tuple(self._a))
            self._a = None
        elif tag == "p" and self._p is not None:
            self.paras.extend(x.strip() for x in "".join(self._p).split("\n") if x.strip())
            self._p = None
        elif tag == "h1" and self._h1 is not None:
            self.h1 = self.h1 or "".join(self._h1).strip()
            self._h1 = None
        elif tag == "title":
            self._title = False

    def handle_data(self, data):
        if self._a is not None:
            self._a[1] += data
        if self._p is not None and not self._skip:
            self._p.append(data)
        if self._h1 is not None:
            self._h1.append(data)
        if self._title:
            self.title += data


def _text(s):
    return re.sub(r"[\s　 ]+", " ", html.unescape(s or "")).strip()


def find_links(page_html, base, pat):
    """列表页里长得像文章的链接 → [(网址, 标题)]，去重、保持页面顺序"""
    p = _Page()
    p.feed(page_html)
    rx = re.compile(pat)
    seen, out = set(), []
    for href, text in p.links:
        url = urllib.parse.urljoin(base, href.strip()).split("#")[0]
        t = _text(text)
        if len(t) < 6 or url in seen or not rx.search(url):
            continue
        seen.add(url)
        out.append((url, t))
    return out


NOISE = ("责任编辑", "责编", "编辑：", "版权所有", "扫一扫", "扫描二维码", "关注我们", "点击进入", "相关阅读", "转载", "来源：", "微信公众号",
         "Copyright", "客户端下载", "纠错", "举报", "登录", "分享到")


def parse_article(page_html, url):
    """文章页 → {title, date, paras}；不像文章（正文太短）就抛 ArticleError"""
    p = _Page()
    p.feed(page_html)
    title = _text(p.h1) or _text(p.meta.get("og:title")) or _text(re.split(r"[_\-—|]", p.title)[0])
    paras = []
    for x in p.paras:
        x = _text(x)
        if len(x) < 12 or (len(x) < 60 and any(w in x for w in NOISE)) or x.rstrip("※ ") == title:
            continue
        paras.append(x)
    if sum(len(x) for x in paras) < MIN_BODY or not title:
        raise ArticleError("没取到正文")
    date = ""
    for src in (p.meta.get("publishdate"), p.meta.get("pubdate"), p.meta.get("article:published_time"),
                p.meta.get("date"), p.meta.get("dc.date"), url):
        # 人民网 /n1/2026/1001/ 及紧凑日期必须按两位月份拆，不能把 10 月拆成 1 月。
        m = re.search(r"(20\d{2})[-/年]?(\d{2})[-/月]?(\d{2})(?!\d)", src or "")
        if not m:
            m = re.search(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})(?!\d)", src or "")
        if m:
            try:
                date = dt.date(*map(int, m.groups())).isoformat()
                break
            except ValueError:
                continue
    return {"title": title[:80], "date": date or dt.date.today().isoformat(), "date_known": bool(date), "paras": paras}


def guess_category(title, default=""):
    if default:
        return default
    for cat, words in CAT_WORDS:
        if any(w in title for w in words):
            return cat
    return "社论评论" if re.search(r"评|论", title) else "其他"


# ---------------------------------------------------------------- 存取
def _file(paths, art):
    return folder(paths) / art["date"][:7] / ("%s-%s-%s.md" % (art["date"], art["id"], _safe(art["title"])))


def _dump(art):
    head = "\n".join("%s: %s" % (k, str(art.get(k, "")).replace("\n", " ")) for k in ("id", "title", "source", "category", "url", "date", "fetched"))
    return "---\n%s\n---\n%s\n" % (head, "\n".join(art["paras"]))


def _read_file(f):
    try:
        text = f.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.match(r"---\n(.*?)\n---\n?(.*)", text, re.S)
    if not m:
        return None
    art = {}
    for line in m.group(1).split("\n"):
        k, _, v = line.partition(": ")
        art[k.strip()] = v.strip()
    if not art.get("id"):
        return None
    art["paras"] = [x for x in m.group(2).split("\n") if x.strip()]
    art["chars"] = sum(len(x) for x in art["paras"])
    art["file"] = f
    return art


def all_files(paths):
    d = folder(paths)
    return sorted(d.glob("*/*.md"), reverse=True) if d.is_dir() else []


def _id_of(f):
    m = re.match(r"\d{4}-\d{2}-\d{2}-([0-9a-f]{8})-", f.name)
    return m.group(1) if m else None


def known_ids(paths):
    return {_id_of(f) for f in all_files(paths)} - {None}


def save_article(paths, art):
    art = dict(art)
    art.setdefault("fetched", dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
    f = _file(paths, art)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(_dump(art), encoding="utf-8")
    tmp.replace(f)
    return f


def find(paths, iid):
    for f in all_files(paths):
        if _id_of(f) == iid:
            a = _read_file(f)
            if a:
                return a
    raise ArticleError("这篇文章不见了（可能在另一台电脑上删了）")


def jd_file(paths, iid):
    return folder(paths) / "精读" / (iid + ".json")


def load_jd(paths, iid):
    f = jd_file(paths, iid)
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None
    except (OSError, ValueError):
        return None


def st(g):
    s = g.state.setdefault("articles", {})
    s.setdefault("read", {})
    s.setdefault("star", [])
    s.setdefault("off", [])
    s.setdefault("on", [])
    return s


def custom_sources(paths):
    f = folder(paths) / "来源.json"
    try:
        lst = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else []
    except (OSError, ValueError):
        return []
    return [x for x in lst if isinstance(x, dict) and x.get("url") and x.get("name")]


def sources(g):
    """全部来源 + 是否开着。内置里 off=True 的默认关（没实测过），用户可以在界面里打开"""
    s = st(g)
    out = []
    for x in SOURCES:
        on = x["name"] in s["on"] if x.get("off") else x["name"] not in s["off"]
        out.append({"name": x["name"], "url": x["url"], "cat": x["cat"], "builtin": True, "on": on, "pat": x["pat"], "untested": bool(x.get("off"))})
    for x in custom_sources(g.paths):
        out.append({"name": x["name"], "url": x["url"], "cat": x.get("category") or "", "builtin": False,
                    "on": x["name"] not in s["off"], "pat": x.get("pat") or CUSTOM_PAT, "untested": False})
    return out


def toggle_source(g, name, on):
    s = st(g)
    src = next((x for x in sources(g) if x["name"] == name), None)
    if not src:
        raise ArticleError("没有这个来源")
    for lst in (s["on"], s["off"]):
        if name in lst:
            lst.remove(name)
    default_off = src["builtin"] and next(x for x in SOURCES if x["name"] == name).get("off")
    if default_off and on:
        s["on"].append(name)
    elif not default_off and not on:
        s["off"].append(name)
    return {"ok": True}


def _write_custom(paths, lst):
    f = folder(paths) / "来源.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(lst, ensure_ascii=False, indent=1), encoding="utf-8")


def add_source(g, name, url, category):
    name, url = str(name or "").strip()[:20], str(url or "").strip()
    if not name or not re.match(r"https?://", url):
        raise ArticleError("来源要写名称和以 http 开头的列表页网址")
    if any(x["name"] == name for x in sources(g)):
        raise ArticleError("已经有叫“%s”的来源了" % name)
    _write_custom(g.paths, custom_sources(g.paths) + [{"name": name, "url": url, "category": category if category in CATEGORIES else ""}])
    return {"ok": True}


def remove_source(g, name):
    _write_custom(g.paths, [x for x in custom_sources(g.paths) if x["name"] != name])
    return {"ok": True}


def listing(g):
    s = st(g)
    items = []
    for f in all_files(g.paths):
        a = _read_file(f)
        if not a:
            continue
        iid = a["id"]
        items.append({"id": iid, "title": a.get("title", ""), "source": a.get("source", ""), "category": a.get("category", "其他"),
                      "date": a.get("date", ""), "url": a.get("url", ""), "chars": a["chars"], "lead": (a["paras"][0] if a["paras"] else "")[:80],
                      "read": iid in s["read"], "star": iid in s["star"], "jd": jd_file(g.paths, iid).is_file()})
    items.sort(key=lambda x: (x["date"], x["id"]), reverse=True)
    return {"items": items, "sources": [{k: x[k] for k in ("name", "url", "cat", "builtin", "on", "untested")} for x in sources(g)],
            "categories": CATEGORIES, "job": job_status()}


def get(g, iid):
    a = find(g.paths, iid)
    s = st(g)
    s["read"].setdefault(iid, dt.date.today().isoformat())
    from . import tianji
    tianji.touch()
    return {"id": iid, "title": a["title"], "source": a.get("source", ""), "category": a.get("category", "其他"), "date": a.get("date", ""),
            "url": a.get("url", ""), "paras": a["paras"], "star": iid in s["star"], "jd": load_jd(g.paths, iid),
            "digest": digest_file(g.paths, iid).is_file()}


def mark(g, iid, body):
    s = st(g)
    if "star" in body:
        if body["star"] and iid not in s["star"]:
            s["star"].append(iid)
        if not body["star"] and iid in s["star"]:
            s["star"].remove(iid)
    if "read" in body and not body["read"]:
        s["read"].pop(iid, None)
    from . import tianji
    tianji.touch()
    return {"ok": True}


def set_category(g, iid, cat):
    if cat not in CATEGORIES:
        raise ArticleError("没有这个分类")
    a = find(g.paths, iid)
    old = a["file"]
    a["category"] = cat
    new = save_article(g.paths, a)
    if new != old:
        old.unlink()
    return {"ok": True}


def delete(g, iid):
    a = find(g.paths, iid)
    a["file"].unlink()
    j = jd_file(g.paths, iid)
    if j.is_file():
        j.unlink()
    s = st(g)
    s["read"].pop(iid, None)
    if iid in s["star"]:
        s["star"].remove(iid)
    return {"ok": True}


# ---------------------------------------------------------------- 抓取（后台线程）
def job_status():
    with LOCK:
        return {k: (list(v) if isinstance(v, list) else v) for k, v in JOB.items()}


def _log(msg):
    with LOCK:
        JOB["log"].append(msg)
        del JOB["log"][:-40]


def import_url(paths, url, source="手动导入", cat="", fetcher=None):
    """抓一篇（手动粘贴的链接）。已经有了就返回已有的"""
    fetcher = fetcher or fetch
    url = str(url or "").strip()
    if not re.match(r"https?://", url):
        raise ArticleError("请粘贴以 http 开头的文章链接")
    iid = aid(url)
    if iid in known_ids(paths):
        return {"id": iid, "new": False}
    try:
        page = fetcher(url)
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise ArticleError("打不开这个网址：%s" % e)
    art = parse_article(page, url)
    art.update(id=iid, source=source, url=url, category=guess_category(art["title"], cat))
    save_article(paths, art)
    return {"id": iid, "new": True, "title": art["title"]}


def crawl_options(body=None, today=None):
    """抓取条件：所有来源合计 count 篇，分类多选，range=7d/1m/6m/all（旧接口兼容）。"""
    body = body or {}
    today = today or dt.date.today()
    count = body.get("count", 10)
    if isinstance(count, bool) or not str(count).isdigit() or not 1 <= int(count) <= 100:
        raise ArticleError("抓取数量要填 1–100 的整数")
    cats = body.get("categories", [])
    if not isinstance(cats, list) or any(c not in CATEGORIES for c in cats):
        raise ArticleError("请选择有效的文章分类")
    period = body.get("range", "7d")
    if period not in ("7d", "1m", "6m", "all"):
        raise ArticleError("请选择近七日、近一个月或近半年")
    if period == "7d":
        since = today - dt.timedelta(days=6)
    elif period in ("1m", "6m"):
        import calendar
        month = today.year * 12 + today.month - 1 - (1 if period == "1m" else 6)
        year, m = divmod(month, 12)
        m += 1
        since = dt.date(year, m, min(today.day, calendar.monthrange(year, m)[1]))
    else:
        since = None
    names = body.get("sources")
    if names is not None and (not isinstance(names, list) or any(not isinstance(n, str) for n in names)):
        raise ArticleError("来源选项格式不对")
    return {"count": int(count), "categories": list(dict.fromkeys(cats)), "range": period,
            "since": since.isoformat() if since else "", "until": today.isoformat(), "sources": names}


def history_links(page_html, base, article_pat):
    """只沿同站的翻页 / 历史栏目链接走，排除正文链接和无关站点，不猜造网站网址。"""
    page = _Page()
    page.feed(page_html)
    root = urllib.parse.urlsplit(base)
    out = []
    for href, label in page.links:
        url = urllib.parse.urljoin(base, href.strip()).split("#")[0]
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in ("http", "https") or parsed.netloc != root.netloc or re.search(article_pat, url):
            continue
        text = _text(label)
        is_nav = bool(re.search(r"下一页|下页|往期|历史|更多|上一页", text)) or text.isdigit()
        is_page = bool(re.search(r"(?:index|list|page)[_-]?\d+|[?&](?:page|p)=\d+", parsed.path + "?" + parsed.query, re.I))
        if (is_nav or is_page) and url != base and url not in out:
            out.append(url)
    return out


def crawl(paths, srcs, fetcher=None, per=PER_SOURCE, options=None):
    """同步抓取。新条件按总数限额；兼容旧调用的每来源上限。历史列表最多20页，正文最多300篇。"""
    fetcher = fetcher or fetch
    have = known_ids(paths)
    res, candidates, seen_urls = [], [], set()
    deadline = time.monotonic() + 180
    # 先收集列表候选再按日期新到旧处理，避免某个来源独占合计额度。
    for src in srcs:
        source_cap = max(1, MAX_CANDIDATES // max(1, len(srcs)))
        source_count = 0
        r = {"name": src["name"], "added": 0, "skipped": 0, "filtered": 0, "unknown_date": 0,
             "failed": 0, "error": "", "lists": 0}
        res.append(r)
        queue, seen_pages = [src["url"]], set()
        cap = MAX_LIST_PAGES if options else 1
        while queue and len(seen_pages) < cap and len(candidates) < MAX_CANDIDATES and time.monotonic() < deadline and source_count < source_cap:
            page_url = queue.pop(0)
            if page_url in seen_pages:
                continue
            seen_pages.add(page_url)
            try:
                page = fetcher(page_url)
                r["lists"] += 1
                links = find_links(page, page_url, src["pat"])
            except Exception as e:
                if page_url == src["url"]:
                    r["error"] = "列表页打不开（%s）" % (str(e)[:60] or e.__class__.__name__)
                continue
            for url, title in links:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                if aid(url) in have:
                    r["skipped"] += 1
                elif len(candidates) < MAX_CANDIDATES and source_count < source_cap:
                    candidates.append((src, r, url, title))
                    source_count += 1
            if options:
                queue.extend(u for u in history_links(page, page_url, src["pat"]) if u not in seen_pages and u not in queue)
        if not r["error"] and not any(c[0] is src for c in candidates) and not r["skipped"]:
            r["error"] = "列表页里没找到文章链接（网站可能改版了）"
        with LOCK:
            JOB["done"] += 1
    matches = []
    for src, r, url, title in candidates:
        if time.monotonic() >= deadline:
            _log("达到本次3分钟检索时限，保存已找到的匹配文章。")
            break
        if not options and r["added"] >= per:
            continue
        try:
            art = parse_article(fetcher(url), url)
        except Exception:
            r["failed"] += 1
            continue
        # 标题关键词优先于来源的默认分类，避免某站全部文章被贴成党政治理。
        category = guess_category(art["title"])
        if category in ("其他", "社论评论") and src.get("cat"):
            category = src["cat"]
        art.update(id=aid(url), source=src["name"], url=url, category=category)
        if options:
            if options["since"] and not art["date_known"]:
                r["unknown_date"] += 1
                continue
            if not options["since"] <= art["date"] <= options["until"] or (options["categories"] and category not in options["categories"]):
                r["filtered"] += 1
                continue
            matches.append((art, r))
        else:
            save_article(paths, art)
            have.add(art["id"])
            r["added"] += 1
            with LOCK:
                JOB["added"] += 1
    if options:
        matches.sort(key=lambda x: x[0]["date"], reverse=True)
        for art, r in matches[:options["count"]]:
            save_article(paths, art)
            r["added"] += 1
            with LOCK:
                JOB["added"] += 1
    for r in res:
        if r["error"]:
            _log("⚠ %s：%s" % (r["name"], r["error"]))
        else:
            _log("✓ %s：新增 %d 篇，查阅 %d 个列表（筛掉 %d 篇、日期不明 %d 篇、正文失败 %d 篇）" %
                 (r["name"], r["added"], r["lists"], r["filtered"], r["unknown_date"], r["failed"]))
    if options:
        added = sum(r["added"] for r in res)
        _log("本次新增 %d / %d 篇%s。历史范围受网站可访问列表限制，最多查20页 / 300篇候选。" %
             (added, options["count"], "，可访问内容中符合条件的新文章不足" if added < options["count"] else ""))
    return res


def start_crawl(g, body=None):
    # 空的旧调用保留旧行为；新版界面总会传明确条件。
    options = crawl_options(body) if body else None
    srcs = [x for x in sources(g) if x["on"]]
    if options and options["sources"] is not None:
        known = {x["name"] for x in sources(g)}
        if any(n not in known for n in options["sources"]):
            raise ArticleError("没有这个来源")
        srcs = [x for x in sources(g) if x["name"] in options["sources"]]
    if not srcs:
        raise ArticleError("请至少选择一个抓取来源")
    with LOCK:
        # 不按超时强开第二个任务，旧线程仍可能在写文件。
        if JOB["running"]:
            return {"started": False}
        JOB.update(running=True, log=[], added=0, done=0, total=len(srcs), t=time.time())
    paths = g.paths

    def run():
        try:
            crawl(paths, srcs, options=options)
        except Exception as e:
            _log("⚠ 抓取中断：%s" % e)
        finally:
            with LOCK:
                JOB["running"] = False
    threading.Thread(target=run, daemon=True).start()
    return {"started": True}


# ---------------------------------------------------------------- 精读（五步）
# 用户2026-10-29指定的《求是》文章拆解心法前五步；第六步“模拟输出”由用户自己做，程序不生成。
JD_SYSTEM = ("你是申论备考的精读老师。下面是一篇时政评论 / 理论文章，请按“五步拆解心法”只做提炼，不评价文章对错，不编造文中没有的内容。\n"
             "正文已按段编号 [1] [2] …。只返回 JSON 对象，字段如下：\n"
             '{"step1": {"old_words": [{"term": "老词新用的词，如“压舱石”“最后一公里”，文中原词", "note": "背后的深层逻辑，25 字内"}], '
             '"verbs": [{"term": "动词结构，如“统筹”“深化”“协同推进”，文中原词", "note": "常搭配什么对象，20 字内"}], '
             '"new_terms": [{"term": "新提法，如“新质生产力”，文中原词", "definition": "含义；文中有解释就据文摘要，没有就留空字符串"}]},\n'
             ' "step2": {"thesis": "文章总论点（提出问题），50 字内", '
             '"parts": [{"point": "分论点，40 字内", "kind": "分析意义|分析原因|提出对策|提出问题"}], '
             '"paragraphs": [{"no": 段号, "summary": "一句话概括这一段大意，30 字内", "type": "解释说明|举例论证|提出要求|提出问题"}]},\n'
             ' "step3": {"items": [{"direction": "文中的宏观方向 / 要求，必须一字不差从原文摘", "domain": "人才|科技|民生|治理|经济|生态|文化|其他", '
             '"landing": "如果让我落实，具体怎么做，60 字内", "source": "文中|参考做法"}]},\n'
             ' "step4": {"quotes": [{"kind": "巧用形象|辩证论述|标题段首句", "text": "原文句子，必须一字不差从原文摘", "use": "可以用在什么主题 / 位置，20 字内"}]},\n'
             ' "step5": {"yuyan": [{"type": "词语理解题|主旨概括题|其他", "question": "站在出题人角度可能这样问，40 字内"}], '
             '"shenlun": [{"type": "只能从给定题型里选", "question": "可能这样出题，如“请根据材料，概括XX问题的主要表现，并提出建议”，50 字内"}]}}\n'
             "要求：step1 三类词各 2~6 个，必须是原文里真有的词语；step2 的 parts 给 2~5 个，paragraphs 给全部主要段落；"
             "step3 的 landing 若原文已写明做法，source 填“文中”，否则可给常见做法，source 必须填“参考做法”；"
             "step3 给 2~8 条，step4 给 3~9 句（三类尽量都有）；step5 的 yuyan 与 shenlun 各给 1~3 条。")
JD_PARTS = ("分析意义", "分析原因", "提出对策", "提出问题")
JD_PTYPES = ("解释说明", "举例论证", "提出要求", "提出问题")
JD_DOMAINS = ("人才", "科技", "民生", "治理", "经济", "生态", "文化")
JD_KINDS = ("巧用形象", "辩证论述", "标题段首句")


def _shown_paras(art):
    """送给 AI 的那部分正文（前 7000 字内的整段），段号从 1 起"""
    out, n = [], 0
    for p in art["paras"]:
        n += len(p)
        if out and n > 7000:
            break
        out.append(p)
    return out


def jd_messages(art, tixing):
    body = "\n".join("[%d] %s" % (i + 1, p) for i, p in enumerate(_shown_paras(art)))
    return [{"role": "system", "content": JD_SYSTEM},
            {"role": "user", "content": "【本科目题型】%s\n【来源】%s\n【标题】%s\n【正文】\n%s" % ("、".join(tixing), art.get("source", ""), art["title"], body)}]


def _sq(s):
    return re.sub(r"\s+", "", str(s))


def _cut(v, n):
    return str(v or "").strip()[:n]


def _choice(v, options, default):
    v = str(v or "").strip()
    return v if v in options else default


def check_jd(raw, art, tixing):
    """校验 AI 返回（五步）：词语 / 原文方向 / 金句必须真在原文里，不在的丢掉；缺总论点或五步全空抛 ArticleError"""
    if not isinstance(raw, dict):
        raise ArticleError("精读结果格式不对")
    flat = _sq("".join(art["paras"]))
    s1, s2, s3, s4, s5 = (raw.get(k) if isinstance(raw.get(k), dict) else {} for k in ("step1", "step2", "step3", "step4", "step5"))

    def rows(v):
        return [x for x in (v or []) if isinstance(x, dict)]

    def terms(key, note):
        out, seen = [], set()
        for x in rows(s1.get(key)):
            t = _cut(x.get("term"), 20)
            if len(_sq(t)) >= 2 and _sq(t) in flat and t not in seen:
                seen.add(t)
                out.append({"term": t, note: _cut(x.get(note), 80)})
        return out[:8]
    step1 = {"old_words": terms("old_words", "note"), "verbs": terms("verbs", "note"), "new_terms": terms("new_terms", "definition")}
    thesis = _cut(s2.get("thesis"), 120)
    if not thesis:
        raise ArticleError("精读结果缺少总论点")
    n = len(_shown_paras(art))
    parts = [{"point": _cut(x.get("point"), 80), "kind": _choice(x.get("kind"), JD_PARTS, "其他")} for x in rows(s2.get("parts")) if _cut(x.get("point"), 80)][:6]
    paras, used = [], set()
    for x in rows(s2.get("paragraphs")):
        try:
            no = int(x.get("no"))
        except (TypeError, ValueError):
            continue
        if 1 <= no <= n and no not in used and _cut(x.get("summary"), 80):
            used.add(no)
            paras.append({"no": no, "summary": _cut(x.get("summary"), 80), "type": _choice(x.get("type"), JD_PTYPES, "其他")})
    paras.sort(key=lambda x: x["no"])
    items = []
    for x in rows(s3.get("items")):
        d = _cut(x.get("direction"), 120)
        if len(_sq(d)) >= 6 and _sq(d) in flat and _cut(x.get("landing"), 200):
            items.append({"direction": d, "domain": _choice(x.get("domain"), JD_DOMAINS, "其他"), "landing": _cut(x.get("landing"), 200),
                          "source": _choice(x.get("source"), ("文中", "参考做法"), "参考做法")})
    quotes = []
    for x in rows(s4.get("quotes")):
        t = _cut(x.get("text"), 200)
        if len(_sq(t)) >= 6 and _sq(t) in flat:
            k = str(x.get("kind") or "")
            kind = "巧用形象" if "形象" in k else "辩证论述" if "辩证" in k else "标题段首句"
            quotes.append({"kind": kind, "text": t, "use": _cut(x.get("use"), 40)})
    yuyan = [{"type": _cut(x.get("type"), 20) or "其他", "question": _cut(x.get("question"), 120)} for x in rows(s5.get("yuyan")) if _cut(x.get("question"), 120)][:4]
    shenlun = [{"type": _cut(x.get("type"), 20), "question": _cut(x.get("question"), 140)} for x in rows(s5.get("shenlun"))
               if _cut(x.get("question"), 140) and (not tixing or x.get("type") in tixing)][:4]
    if not (items or quotes or step1["old_words"] or step1["verbs"] or step1["new_terms"] or parts):
        raise ArticleError("精读结果几乎是空的")
    return {"version": 2, "step1": step1,
            "step2": {"thesis": thesis, "parts": parts, "paragraphs": paras},
            "step3": {"items": items[:10]}, "step4": {"quotes": quotes[:10]}, "step5": {"yuyan": yuyan, "shenlun": shenlun}}


def save_jd(paths, iid, jd):
    f = jd_file(paths, iid)
    f.parent.mkdir(parents=True, exist_ok=True)
    jd = dict(jd, time=dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
    f.write_text(json.dumps(jd, ensure_ascii=False, indent=1), encoding="utf-8")
    return jd


# ---------------------------------------------------------------- 摘编（档案室里翻阅；不是复习卡片）
def digest_file(paths, iid):
    return folder(paths) / "摘编" / (iid + ".json")


def digest_save(g, iid):
    """精读里的“万能对策”和“黄金句式”存成一份摘编（每篇一份，再存会覆盖），放在档案室里按领域 / 类型翻阅"""
    a = find(g.paths, iid)
    jd = load_jd(g.paths, iid)
    if not jd:
        raise ArticleError("这篇还没精读")
    if jd.get("version") != 2:
        raise ArticleError("这是旧版精读，先点“重新精读”换成新版再存入摘编")
    items = list((jd.get("step3") or {}).get("items") or [])
    quotes = list((jd.get("step4") or {}).get("quotes") or [])
    if not items and not quotes:
        raise ArticleError("这篇精读里没有可摘的对策或黄金句式")
    f = digest_file(g.paths, iid)
    again = f.is_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    data = {"id": iid, "title": a["title"], "source": a.get("source", ""), "url": a.get("url", ""), "date": a.get("date", ""),
            "saved": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "countermeasures": items, "quotes": quotes}
    f.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "again": again, "countermeasures": len(items), "quotes": len(quotes)}


def digest_list(paths):
    out = []
    d = folder(paths) / "摘编"
    for f in sorted(d.glob("*.json")) if d.is_dir() else []:
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    out.sort(key=lambda x: x.get("saved", ""), reverse=True)
    return out


def digest_remove(paths, iid):
    f = digest_file(paths, iid)
    if f.is_file():
        f.unlink()
    return {"ok": True}
