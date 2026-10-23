"""时政批注的权威背景检索：politics.explain调用，返回检索摘要和可核对出处。

只访问固定HTTPS搜索端点；不跟随结果URL抓取页面，不需要额外密钥。
结果为不可信参考资料，只接受政府、新华社、人民日报来源；失败明确降级。
"""
import datetime as dt
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape

from . import net

HOSTS = ('gov.cn', 'npc.gov.cn', 'xinhuanet.com', 'news.cn', 'people.com.cn')


def trusted_url(value):
    try:
        url = urllib.parse.urlsplit(value)
        host = (url.hostname or '').lower()
        return (url.scheme == 'https' and not url.username and not url.password
                and url.port in (None, 443)
                and any(host == h or host.endswith('.' + h) for h in HOSTS))
    except ValueError:
        return False


def search(word, title):
    query = '%s 中国 政策 背景 site:gov.cn' % word[:80]
    result = {'status': 'unavailable', 'sources': [], 'checked_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    request = urllib.request.Request('https://www.bing.com/search?' + urllib.parse.urlencode({'q': query, 'format': 'rss', 'setlang': 'zh-hans'}),
                                     headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/rss+xml'})
    try:
        with net.urlopen(request, timeout=8) as response:
            content = response.read(512001)
        if len(content) > 512000:
            return result
        tree = ET.fromstring(content)
        seen = set()
        for item in tree.findall('.//item'):
            url = (item.findtext('link') or '').strip()
            if not trusted_url(url) or url in seen:
                continue
            clean = lambda s: re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', '', s or ''))).strip()
            title_text, snippet = clean(item.findtext('title')), clean(item.findtext('description'))
            if not title_text or not snippet:
                continue
            # 搜索服务忽略中文查询、返回热门内容时，不把无关网页当作政策依据。
            terms = re.findall(r'[\u4e00-\u9fff]{2,8}|[A-Za-z]{3,}', word)
            if terms and not any(term in title_text + snippet for term in terms):
                continue
            result['sources'].append({'title': title_text[:200], 'url': url, 'summary': snippet[:1200],
                                      'date': clean(item.findtext('pubDate'))[:80]})
            seen.add(url)
            if len(result['sources']) == 3:
                break
        result['status'] = 'ok' if result['sources'] else 'empty'
    except (OSError, ValueError, ET.ParseError):
        pass
    return result
