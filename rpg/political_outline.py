"""专题时政目录：按原文标题/完整内容主题组织导航，保留原news索引。

tianji.parse_pdf和load调用；只生成outline元数据，不合并/改写正文、题目、进度或批注定位。
同一大章内相邻且同主题的原文组成一节，每节保留各原文入口，避免把题号当章节。
"""
import re

TOPICS = (
    ('发展新质生产力', ('新质生产力',)),
    ('经济大省担当', ('经济大省',)),
    ('中国式现代化与共同富裕', ('共同富裕',)),
    ('建设健康中国', ('健康中国',)),
    ('国防和军队建设', ('建军', '强军', '国防和军队', '军队现代化')),
    ('建设现代化产业体系', ('现代化产业体系', '新型工业化')),
    ('扩大内需', ('扩大内需', '消费需求', '内需主导')),
    ('建设全国统一大市场', ('统一大市场',)),
    ('科技创新', ('科技创新', '科技自立自强')),
    ('教育科技人才', ('教育科技人才', '教育强国', '人才强国')),
    ('乡村全面振兴', ('乡村振兴', '三农', '农业农村现代化')),
    ('保障粮食安全', ('粮食安全', '粮食主产区')),
    ('宏观政策与经济治理', ('逆周期', '跨周期', '宏观政策', '宏观经济')),
    ('保障和改善民生', ('就业', '养老', '社会保障', '民生')),
    ('绿色发展与生态保护', ('绿色发展', '生态保护', '生态文明', '碳达峰')),
    ('高水平对外开放', ('对外开放', '制度型开放')),
    ('党的建设', ('党的建设', '全面从严治党', '党风廉政')),
)
HEADING = re.compile(r'^(?:[一二三四五六七八九十百]+[、．.]|[（(][一二三四五六七八九十0-9]+[)）]|第[一二三四五六七八九十0-9]+[章节篇])')


def heading(text):
    """只接受短标题式行，不把完整陈述句或题目开头当标题。"""
    text = str(text).strip()
    if not text or len(text) > 40 or re.search(r'[，,。！？：:；;]', text):
        return ''
    if HEADING.match(text):
        return re.sub(r'^(?:[一二三四五六七八九十百]+[、．.]|[（(][一二三四五六七八九十0-9]+[)）])\s*', '', text)
    if re.fullmatch(r'【[^】]{2,28}】', text) and text not in ('【原文速递】', '【答案】', '【解析】'):
        return text[1:-1]
    return ''


def title_of(item, index=0):
    explicit = item.get('heading')
    if explicit and len(explicit) <= 36:
        return explicit
    for paragraph in item.get('paras', []):
        found = heading(paragraph)
        if found:
            return found
    text = '\n'.join(item.get('paras', []))
    scored = [(sum(text.count(word) for word in words), -i, title)
              for i, (title, words) in enumerate(TOPICS)]
    best = max(scored)
    if best[0]:
        return best[2]
    # 无法可靠概括时保留明确短标题；不把截断题干包装成概括。
    old = str(item.get('title', ''))
    if 2 <= len(old) <= 22 and not re.search(r'[，。！？：:]|习近平|指出|强调', old) and old != item.get('group'):
        return old
    # 从全文提取独立的小标题式政策表述，而非固定套用第一句话。
    for clause in re.split(r'[，。；\n]', text):
        clause = clause.strip()
        if re.fullmatch(r'(?:加快|推进|建设|完善|健全|提升|深化|扩大|促进)[\u4e00-\u9fff]{3,15}', clause):
            return clause
    return '专题研读 · 材料%d' % (index + 1)


def outline(data):
    if data.get('kind') != 'topic':
        return []
    chapters = []
    for index, item in enumerate(data.get('news', [])):
        title = title_of(item, index)
        group = item.get('group', '')
        if chapters and chapters[-1]['group'] == group and chapters[-1]['title'] == title:
            chapters[-1]['items'].append(index)
        else:
            chapters.append({'title': title, 'group': group, 'items': [index]})
    return chapters
