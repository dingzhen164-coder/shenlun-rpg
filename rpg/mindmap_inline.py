"""灵脉图旧HTML节点转可编辑Markdown；只保留文字/行内格式，不输出HTML资源或属性。

由mindmap.py调用，输入/输出均为字符串，保留行内Markdown和公式源文。
"""
import re
from html.parser import HTMLParser


class RichText(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.parts = []
        self.stack = []
        self.active = set()
        self.blocked = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'iframe', 'object', 'embed', 'svg', 'math'):
            self.blocked += 1
        if self.blocked:
            return
        if tag == 'br':
            self.parts.append('\n')
            return
        style = dict(attrs).get('style', '') or ''
        marks = []
        if tag in ('b', 'strong') or re.search(r'font-weight\s*:\s*(?:bold|[6-9]00)\b', style, re.I):
            marks.append('**')
        if tag in ('i', 'em') or re.search(r'font-style\s*:\s*italic\b', style, re.I):
            marks.append('*')
        if tag in ('s', 'strike', 'del') or re.search(r'text-decoration[^:]*:[^;]*line-through', style, re.I):
            marks.append('~~')
        if tag == 'code':
            marks.append('`')
        marks = [m for m in marks if m not in self.active]
        self.stack.append((tag, marks))
        self.active.update(marks)
        self.parts.extend(marks)

    def handle_endtag(self, tag):
        if self.blocked:
            if tag in ('script', 'style', 'iframe', 'object', 'embed', 'svg', 'math'):
                self.blocked -= 1
            return
        if any(t == tag for t, _ in self.stack):
            while self.stack:
                current, marks = self.stack.pop()
                self.parts.extend(reversed(marks))
                self.active.difference_update(marks)
                if current == tag:
                    break
        if tag in ('p', 'div', 'li'):
            self.parts.append('\n')

    def handle_data(self, text):
        if not self.blocked:
            self.parts.append(text if '`' in self.active else re.sub(r'([\\`*_~$])', r'\\\1', text))


def rich_markdown(text):
    parser = RichText()
    parser.feed(text)
    for _, marks in reversed(parser.stack):
        parser.parts.extend(reversed(marks))
    return ''.join(parser.parts).strip()


def source_text(text):
    """结构解析只还原生成文档的HTML转义，行内Markdown/公式及其字面转义原样保留。"""
    return re.sub(r'\\([<>])', r'\1', text)


def document_text(text):
    return text.replace('<', '\\<').replace('>', '\\>')
