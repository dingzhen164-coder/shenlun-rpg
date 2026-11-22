#!/usr/bin/env python3
"""整场模考错题一键提取脚本（仅标准库，兼容 Python 3.8+）。

同时兼容：
  1. 粉笔 HTML/ZIP 导入：`<行测库>/训练/试炼与大比/模考复盘/第XX季/[0-9][0-9]-*.md`（及旧版 `训练/模考复盘/第XX季/`）
  2. PDF 拆分导入：`<行测库>/FB模考试卷复盘/第XX季/[0-9][0-9]-*.md`

只提取错题与未作答题（❌ / ⚪ 或 我的答案 != 正确答案），不筛慢题。
自动附带共享材料（资料分析 / 一拖五）与本地真实图片路径（供本地 AI 直接看图复盘）。

用法示例：
  python3 extract_mock_wrongs.py --vault /path/to/行测库 --list
  python3 extract_mock_wrongs.py --vault /path/to/行测库 --latest
  python3 extract_mock_wrongs.py --vault /path/to/行测库 --season 39 --out-dir /tmp/mock39
  python3 extract_mock_wrongs.py --vault /path/to/行测库 --season 39 --format json
"""
import argparse
import json
import re
import sys
from pathlib import Path

HEAD_RE = re.compile(r'^###\s*(\d+)\.\s*([✅❌⚪])\s*$')
MAT_RE = re.compile(r'^##\s*材料（第(\d+)[-–—~](\d+)题）')
ANS_RE = re.compile(r'正确答案[：:]\s*\**([A-D?]+)\**.*?我的答案[：:]\s*\**([A-D?—\-]*)\**')
IMG_WIKI_RE = re.compile(r'!\[\[([^\]]+)\]\]')
IMG_MD_RE = re.compile(r'!\[[^\]]*\]\(([^)]+)\)')

# 思过崖 7 板块精确映射（模考板块名 -> 错题集文档名）
SIGUO_MAP = {
    '片段阅读': '中心理解.md',
    '中心理解': '中心理解.md',
    '逻辑填空': '逻辑填空.md',
    '数量关系': '数量关系.md',
    '定义判断': '定义判断.md',
    '论证逻辑': '论证逻辑.md',
    '类比推理': '类比推理.md',
    '一拖五': '一拖五.md',
}

# 分批并行复盘的模块归组
BATCH_GROUP = {
    '政治理论': ('01-政治理论', '小黑政治理论 skill + 对应时政地图 .md（必须注明出处文件）', 'gk-skill/错题集/政治理论.md（同步至 训练/万象峰/易错题.md，不进思过崖）'),
    '常识判断': ('02-常识判断', '常识积累与对应考点核对', '仅回填本季模考复盘文档（不进思过崖）'),
    '逻辑填空': ('03-言语理解', '言语理解/成语实词 skill', 'gk-skill/错题集/逻辑填空.md（思过崖）'),
    '片段阅读': ('03-言语理解', '言语理解/中心理解 skill', 'gk-skill/错题集/中心理解.md（思过崖）'),
    '中心理解': ('03-言语理解', '言语理解/中心理解 skill', 'gk-skill/错题集/中心理解.md（思过崖）'),
    '数量关系': ('04-数量关系', '数量关系十八讲 skill', '同时归入十八讲对应课程 .md + gk-skill/错题集/数量关系.md（必须写 所属课程：第XX课-XXX）'),
    '图形推理': ('05-判断推理', '判断推理/图推规律 skill（需直接读取本地原图）', '回填本季模考复盘文档（不进思过崖 7 碑）'),
    '定义判断': ('05-判断推理', '判断推理/定义判断 skill', 'gk-skill/错题集/定义判断.md（思过崖）'),
    '类比推理': ('05-判断推理', '判断推理/类比推理 skill', 'gk-skill/错题集/类比推理.md（思过崖）'),
    '论证逻辑': ('05-判断推理', '判断推理/论证逻辑 skill', 'gk-skill/错题集/论证逻辑.md（思过崖）'),
    '形式逻辑': ('05-判断推理', '判断推理/形式逻辑 skill', '回填本季模考复盘文档（不进思过崖 7 碑）'),
    '一拖五': ('05-判断推理', '判断推理/一拖五 skill', 'gk-skill/错题集/一拖五.md（思过崖）'),
    '资料分析': ('06-资料分析', '资料分析速算与坑点 skill（有图表需读原图）', '回填本季模考复盘文档（不进思过崖 7 碑）'),
}


def detect_vault(explicit=None):
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if p.is_dir():
            return p
        raise SystemExit(f'错误：指定的行测库目录不存在：{p}')
    cur = Path.cwd().resolve()
    for cand in [cur] + list(cur.parents):
        if (cand / '训练').is_dir() or (cand / 'FB模考试卷复盘').is_dir():
            return cand
    raise SystemExit('错误：未自动找到行测库目录，请用 --vault <行测库路径> 指定。')


def discover_seasons(vault):
    """按优先级扫描 PDF 拆分目录、4.4.0 六大类模考复盘目录、旧版模考复盘目录。"""
    roots = [
        ('PDF拆分', vault / 'FB模考试卷复盘'),
        ('HTML/ZIP导入', vault / '训练' / '试炼与大比' / '模考复盘'),
        ('旧版复盘', vault / '训练' / '模考复盘'),
    ]
    found = {}
    for kind, root in roots:
        if not root.is_dir():
            continue
        for d in sorted(root.iterdir()):
            m = re.fullmatch(r'第(\d+)季', d.name)
            if m and d.is_dir() and any(d.glob('[0-9][0-9]-*.md')):
                n = int(m.group(1))
                # 保留所有来源，默认优先已有 PDF/HTML 复盘目录
                found.setdefault(n, []).append((kind, d))
    return sorted(found.items())


def resolve_image(vault, season_dir, ref):
    """把 Markdown 中的图片引用解析为真实存在的本地路径。"""
    raw = str(ref or '').split('|', 1)[0].strip()
    if not raw or raw.startswith(('http://', 'https://', 'data:')):
        return None
    norm = raw.replace('\\', '/').lstrip('/')
    cands = [
        vault / norm,
        season_dir / norm,
        season_dir.parent / norm,
    ]
    # 兼容 4.4.0 六大类迁移前的旧路径 `训练/题库/...` -> `训练/藏经阁/题库/...`
    if norm.startswith('训练/'):
        sub = norm[len('训练/'):]
        cands.extend([
            vault / '训练' / '藏经阁' / sub,
            vault / '训练' / '试炼与大比' / sub,
            vault / '训练' / '思过崖' / sub,
        ])
    for c in cands:
        try:
            if c.is_file():
                return str(c.resolve())
        except OSError:
            pass
    return raw


def extract_images(text, vault, season_dir):
    seen, out = set(), []
    for rx in (IMG_WIKI_RE, IMG_MD_RE):
        for m in rx.finditer(text or ''):
            ref = m.group(1).strip()
            if ref in seen:
                continue
            seen.add(ref)
            out.append({'ref': ref, 'path': resolve_image(vault, season_dir, ref)})
    return out


def parse_board_file(path, vault, season_dir):
    lines = path.read_text(encoding='utf-8-sig', errors='ignore').splitlines()
    qs, mats, cur, mat, in_note = [], {}, None, None, False
    for ln in lines:
        h = HEAD_RE.match(ln)
        if h:
            cur = {
                'num': int(h.group(1)),
                'icon': h.group(2),
                'correct': '',
                'mine': '',
                'seconds': None,
                'source_accuracy': None,
                'body': [],
                'note': [],
                'material_key': None,
            }
            if mat and mat[0] <= cur['num'] <= mat[1]:
                cur['material_key'] = mat
            qs.append(cur)
            in_note = False
            continue
        mm = MAT_RE.match(ln)
        if mm:
            mat = (int(mm.group(1)), int(mm.group(2)))
            mats[mat] = []
            cur = None
            continue
        if cur is None:
            if mat in mats and ln.strip() != '---':
                mats[mat].append(ln)
            continue
        if ln.strip() == '---':
            cur = None
            continue
        if ln.startswith('> [!note]'):
            in_note = True
            continue
        if in_note:
            cur['note'].append(ln)
            continue
        a = ANS_RE.search(ln)
        if a:
            cur['correct'] = a.group(1).strip('?')
            cur['mine'] = a.group(2).strip('—-?')
            continue
        m_sec = re.match(r'^>\s*(?:原答题)?用时[：:]\s*\**(\d+)\s*秒', ln)
        if m_sec:
            cur['seconds'] = int(m_sec.group(1))
            continue
        m_acc = re.match(r'^>\s*(?:原题|全站|全网|本题)?正确率[：:]\s*\**(\d+(?:\.\d+)?)\s*%', ln)
        if m_acc:
            cur['source_accuracy'] = float(m_acc.group(1))
            continue
        if not ln.startswith('> [!check]'):
            cur['body'].append(ln)

    out = []
    for q in qs:
        body_text = '\n'.join(q['body']).strip()
        mat_text = '\n'.join(mats.get(q['material_key'], [])).strip() if q['material_key'] else ''
        note_lines = [re.sub(r'^>\s?', '', l) for l in q['note']]
        note_text = '\n'.join(note_lines).strip()
        is_wrong = (q['icon'] in ('❌', '⚪')) or (bool(q['correct']) and q['mine'] != q['correct'])
        imgs = extract_images((mat_text + '\n' + body_text), vault, season_dir)
        out.append({
            'num': q['num'],
            'icon': q['icon'],
            'is_wrong': is_wrong,
            'correct': q['correct'],
            'mine': q['mine'] or '未答',
            'seconds': q['seconds'],
            'source_accuracy': q['source_accuracy'],
            'material': mat_text,
            'body': body_text,
            'existing_note': note_text,
            'images': imgs,
        })
    return out


def extract_season(vault, season_num, season_dir, kind):
    files = sorted(season_dir.glob('[0-9][0-9]-*.md'))
    all_total = 0
    wrong_total = 0
    board_stats = []
    batches = {}

    for f in files:
        board = f.stem[3:]
        qs = parse_board_file(f, vault, season_dir)
        wrongs = [q for q in qs if q['is_wrong']]
        all_total += len(qs)
        wrong_total += len(wrongs)
        board_stats.append({
            'board': board,
            'file': str(f.resolve()),
            'total': len(qs),
            'wrong': len(wrongs),
            'siguo_target': SIGUO_MAP.get(board, ''),
        })
        if not wrongs:
            continue
        group_name, skill_hint, write_target = BATCH_GROUP.get(
            board,
            (f'99-{board}', '按对应板块常规方法复盘', '回填本季模考复盘文档'),
        )
        batch = batches.setdefault(group_name, {
            'batch': group_name,
            'boards': [],
            'skill_hints': [],
            'write_targets': [],
            'questions': [],
        })
        if board not in batch['boards']:
            batch['boards'].append(board)
        if skill_hint not in batch['skill_hints']:
            batch['skill_hints'].append(skill_hint)
        if write_target not in batch['write_targets']:
            batch['write_targets'].append(write_target)
        for q in wrongs:
            q_item = dict(q, board=board, source_file=str(f.resolve()), sigou_target=SIGUO_MAP.get(board, ''))
            batch['questions'].append(q_item)

    ordered_batches = [batches[k] for k in sorted(batches)]
    for b in ordered_batches:
        b['questions'].sort(key=lambda x: x['num'])
    return {
        'season': season_num,
        'kind': kind,
        'season_dir': str(season_dir.resolve()),
        'total_questions': all_total,
        'wrong_count': wrong_total,
        'board_stats': board_stats,
        'batches': ordered_batches,
    }


def render_batch_md(season, batch):
    lines = [
        f'# 第{season}季模考错题复盘包 · {batch["batch"]}（共 {len(batch["questions"])} 题）',
        '',
        f'- **包含板块**：{"、".join(batch["boards"])}',
        f'- **必查 Skill**：{"；".join(batch["skill_hints"])}',
        f'- **写回目标**：{"；".join(batch["write_targets"])}',
        '',
        '---',
        '',
    ]
    last_mat = None
    for q in batch['questions']:
        if q['material'] and q['material'] != last_mat:
            lines.append('## 共享材料')
            lines.append(q['material'])
            lines.append('')
            last_mat = q['material']
        sec_str = f' ｜ 用时：{q["seconds"]}秒' if q['seconds'] is not None else ''
        acc_str = f' ｜ 全站正确率：{q["source_accuracy"]:g}%' if q['source_accuracy'] is not None else ''
        lines.append(f'### 第{q["num"]}题 · {q["board"]} {q["icon"]}')
        lines.append(f'- **正确答案**：`{q["correct"]}` ｜ **我的答案**：`{q["mine"]}`{sec_str}{acc_str}')
        lines.append(f'- **原复盘文件**：`{q["source_file"]}`')
        if q['images']:
            img_paths = '、'.join(f'`{im["path"]}`' for im in q['images'])
            lines.append(f'- **本地原图（可直接读图）**：{img_paths}')
        lines.append('')
        lines.append(q['body'])
        if q['existing_note']:
            lines.append('')
            lines.append('<details><summary>粉笔原解析/已有笔记</summary>')
            lines.append('')
            lines.append(q['existing_note'])
            lines.append('')
            lines.append('</details>')
        lines.append('')
        lines.append('---')
        lines.append('')
    return '\n'.join(lines)


def render_summary_md(data):
    lines = [
        f'# 第{data["season"]}季模考错题总览（仅错题，不含慢题）',
        '',
        f'- **来源类型**：{data["kind"]}',
        f'- **模考目录**：`{data["season_dir"]}`',
        f'- **总题数 / 错题数**：{data["total_questions"]} 题 / **{data["wrong_count"]} 题**',
        '',
        '## 各板块错题统计',
        '',
        '| 板块 | 总题数 | 错题数 | 思过崖/错题集去向 |',
        '| --- | ---: | ---: | --- |',
    ]
    for s in data['board_stats']:
        if s['board'] == '政治理论':
            dest = '万象峰易错题（`gk-skill/错题集/政治理论.md`）'
        elif s['board'] == '数量关系':
            dest = '十八讲 + `错题集/数量关系.md`'
        elif s['siguo_target']:
            dest = f'思过崖（`错题集/{s["siguo_target"]}`）'
        else:
            dest = '仅回填模考复盘文档'
        lines.append(f'| {s["board"]} | {s["total"]} | {s["wrong"]} | {dest} |')
    lines.append('')
    lines.append('## 分批复盘清单（建议按批并行）')
    lines.append('')
    for b in data['batches']:
        nums = ', '.join(str(q['num']) for q in b['questions'])
        lines.append(f'- **{b["batch"]}**（{len(b["questions"])} 题：第 {nums} 题）→ 必查：{"；".join(b["skill_hints"])}')
    return '\n'.join(lines) + '\n'


def main():
    ap = argparse.ArgumentParser(description='提取行测整场模考的全部错题（兼容 HTML/ZIP 与 PDF 拆分导入）')
    ap.add_argument('--vault', help='Obsidian 行测库根目录（默认自动向上探测）')
    ap.add_argument('--season', type=int, help='指定季数，例如 39')
    ap.add_argument('--latest', action='store_true', help='自动提取最新一季模考')
    ap.add_argument('--list', action='store_true', help='列出库中所有可用模考季数')
    ap.add_argument('--format', choices=('md', 'json'), default='md', help='标准输出格式')
    ap.add_argument('--out-dir', help='按模块拆分成多个复盘包写入该目录（适合多子 Agent 并行复盘）')
    args = ap.parse_args()

    vault = detect_vault(args.vault)
    seasons = discover_seasons(vault)
    if args.list:
        if not seasons:
            print('未在库中找到任何模考复盘目录（检查 FB模考试卷复盘/ 或 训练/试炼与大比/模考复盘/）。')
            return
        for n, entries in seasons:
            desc = '；'.join(f'{k}: {d}' for k, d in entries)
            print(f'第{n}季 -> {desc}')
        return

    if not seasons:
        raise SystemExit('错误：未找到任何模考复盘目录。')

    if args.season is not None:
        hit = next(((n, entries) for n, entries in seasons if n == args.season), None)
        if not hit:
            avail = ', '.join(str(n) for n, _ in seasons)
            raise SystemExit(f'错误：未找到第{args.season}季模考。可用季数：{avail}')
        season_num, entries = hit
    else:
        season_num, entries = seasons[-1]

    kind, season_dir = entries[0]
    data = extract_season(vault, season_num, season_dir, kind)

    if args.out_dir:
        out_dir = Path(args.out_dir).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / '00-总览.md').write_text(render_summary_md(data), encoding='utf-8')
        (out_dir / '00-data.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        for b in data['batches']:
            (out_dir / f'{b["batch"]}.md').write_text(render_batch_md(season_num, b), encoding='utf-8')
        print(f'已提取第{season_num}季错题共 {data["wrong_count"]} 题（分 {len(data["batches"])} 批），写入：{out_dir}')
        return

    if args.format == 'json':
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(render_summary_md(data))
        for b in data['batches']:
            print(render_batch_md(season_num, b))


if __name__ == '__main__':
    main()
