"""发布前自动检查（两仓库共用，用户2026-10-25要求）：创建 validate/<版本>-<短SHA> 分支之前必须先跑，任何一项“失败”都不能发布。
只用标准库；只读（除 git fetch 外不改仓库）。

为什么要有它：Claude Code 和 Codex 可能同时在开发，最后由其中一方统一发布。发布前必须确认
  1. 两边的改动都已经合在当前这个开发分支上（没有别的分支、别人的新提交被漏掉）；
  2. 版本号、更新记录、发布请求文件是同一个新版本；
  3. 没有未提交/未推送的改动，没有冲突标记，共用文件两仓库一致。

用法（在仓库根目录）：
  python3 tools/release_precheck.py                 检查当前分支（默认对照 origin/main）
  python3 tools/release_precheck.py --tests         另外跑完整单元测试
  python3 tools/release_precheck.py --ack-branch claude/xxx   明确确认某个未合入的分支“有意不随本次发布”（可多次；长期不用的旧分支写进 tools/release_acked_branches.txt）
  python3 tools/release_precheck.py --days 7        其他分支多久以内的新提交算“可能是并行开发”（默认7天）
退出码：有“失败”项为1，否则0；“提醒”项不挡发布，但要在汇报里说明。"""
import argparse
import os
import re
import subprocess
import sys
import time

FAIL, WARN, OK = '失败', '提醒', '通过'


def git(root, *args, check=False):
    p = subprocess.run(['git', '-c', 'core.quotepath=off', *args], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
    if check and p.returncode:
        raise RuntimeError(p.stderr.strip() or 'git %s 失败' % ' '.join(args))
    return p.returncode, p.stdout.strip()


def read(path):
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except OSError:
        return None


def version_tuple(text):
    m = re.match(r'^\D*(\d+)\.(\d+)\.(\d+)', text or '')
    return tuple(int(x) for x in m.groups()) if m else None


def check_tree_clean(root):
    code, out = git(root, 'status', '--porcelain')
    if out:
        return [(FAIL, '有未提交的改动（先提交并推送）：' + '；'.join(l.strip() for l in out.splitlines()[:6]))]
    return [(OK, '工作区干净')]


def check_pushed(root, branch, remote='origin'):
    ref = '%s/%s' % (remote, branch)
    if git(root, 'rev-parse', '--verify', '-q', ref)[0]:
        return [(FAIL, '远端还没有分支 %s：先推送' % ref)]
    ahead = git(root, 'rev-list', '--count', '%s..HEAD' % ref)[1]
    behind = git(root, 'rev-list', '--count', 'HEAD..%s' % ref)[1]
    out = []
    if behind != '0':
        who = git(root, 'log', '-5', '--format=%an %s', 'HEAD..%s' % ref)[1].replace('\n', ' | ')
        out.append((FAIL, '远端 %s 有 %s 个提交不在本地（可能是另一个AI/另一台电脑推的），先 git merge %s：%s' % (ref, behind, ref, who[:200])))
    if ahead != '0':
        out.append((FAIL, '本地有 %s 个提交还没推到 %s：先推送，验证分支要和远端开发分支一致' % (ahead, ref)))
    return out or [(OK, '本地与 %s 一致' % ref)]


def check_main_merged(root, base='main', remote='origin'):
    ref = '%s/%s' % (remote, base)
    if git(root, 'rev-parse', '--verify', '-q', ref)[0]:
        return [(WARN, '找不到 %s，无法确认开发分支已合入最新 main' % ref)]
    if git(root, 'merge-base', '--is-ancestor', ref, 'HEAD')[0]:
        return [(FAIL, '开发分支没有合入最新的 %s（别人已发布过新版本）：先 git merge %s，解决冲突后重新测试' % (ref, ref))]
    return [(OK, '已合入最新 %s' % ref)]


def check_parallel_branches(root, branch, base='main', remote='origin', days=7, acked=(), now=None):
    """别的AI/别的会话的分支：有新提交没合进当前分支，且在最近几天内，就可能是并行开发的内容，必须合入或明确确认不随本次发布。"""
    code, out = git(root, 'for-each-ref', '--format=%(refname:short)|%(committerdate:unix)|%(authorname)|%(subject)', 'refs/remotes/' + remote)
    now = now or time.time()
    found, stale = [], []
    for line in out.splitlines():
        name, _, rest = line.partition('|')
        stamp, _, rest = rest.partition('|')
        author, _, subject = rest.partition('|')
        short = name[len(remote) + 1:] if name.startswith(remote + '/') else name
        if short in (branch, base, 'HEAD') or short.startswith('validate/') or short in acked or name == remote:
            continue
        if git(root, 'merge-base', '--is-ancestor', name, 'HEAD')[0] == 0:
            continue                                              # 已合入
        cherry = git(root, 'cherry', 'HEAD', name)[1].splitlines()
        if cherry and all(l.startswith('-') for l in cherry):
            continue                                              # 提交内容都已在当前分支（改过提交ID的合入，如cherry-pick/rebase）
        age = (now - int(stamp or 0)) / 86400
        item = '%s（%s，%.1f天前：%s）' % (short, author, age, subject[:40])
        (found if age <= days else stale).append(item)
    res = []
    if found:
        res.append((FAIL, '这些分支有最近的新提交没合入当前分支（可能是并行开发的内容，合入它们，或用 --ack-branch 明确确认不随本次发布）：' + '；'.join(found)))
    if stale:
        res.append((WARN, '这些旧分支有未合入的提交（超过%d天，通常是废弃分支）：' % days + '；'.join(stale[:5]) + ('…' if len(stale) > 5 else '')))
    return res or [(OK, '没有未合入的并行分支')]


def read_version(root):
    text = read(os.path.join(root, 'rpg', 'version.py')) or ''
    m = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', text, re.M)
    return m.group(1) if m else None


def check_versions(root, remote='origin'):
    import json
    ver = read_version(root)
    out = []
    if not ver:
        return [(FAIL, 'rpg/version.py 里没有 VERSION')]
    log = read(os.path.join(root, 'rpg', 'data', 'changelog.md')) or ''
    m = re.search(r'^## (\d+\.\d+\.\d+)', log, re.M)
    if not m or m.group(1) != ver:
        out.append((FAIL, '更新记录顶部是 %s，和 version.py 的 %s 不一致' % (m.group(1) if m else '没有', ver)))
    try:
        req = json.loads(read(os.path.join(root, '.github', 'release-request.json')) or '{}')
    except ValueError:
        req = {}
    if req.get('version') != ver:
        out.append((FAIL, '.github/release-request.json 的版本是 %s，和 version.py 的 %s 不一致' % (req.get('version'), ver)))
    top = re.split(r'^## ', log, flags=re.M)[1:2]
    need_note = '更新记录都写明“旧存档照常使用”' in (read(os.path.join(root, 'CLAUDE.md')) or '')     # 只有规则文件要求每版都写时才检查
    if need_note and top and '旧存档照常使用' not in top[0]:
        out.append((FAIL, '更新记录顶部这一节没有写“旧存档照常使用”（CLAUDE.md 要求每个版本都写）'))
    git(root, 'fetch', '-q', '--tags', remote)
    tags = [t for t in git(root, 'tag', '-l', 'v*')[1].split() if version_tuple(t)]
    if tags:
        latest = max(tags, key=version_tuple)
        if version_tuple(ver) <= version_tuple(latest):
            out.append((FAIL, '版本号 %s 不高于已发布的最新版 %s：这一批要先改版本号和更新记录（并行开发的两边只在发布这一刻改一次）' % (ver, latest)))
    return out or [(OK, '版本号 %s：version.py、更新记录、发布请求一致，且高于已发布版本' % ver)]


def check_conflict_markers(root):
    code, out = git(root, 'grep', '-nIE', r'^(<<<<<<< |>>>>>>> )', '--', '.', ':!*.md')
    if out:
        return [(FAIL, '文件里还有合并冲突标记：' + '；'.join(out.splitlines()[:5]))]
    return [(OK, '没有合并冲突标记')]


def check_secrets_and_samples(root, base='main', remote='origin'):
    """真题原文、参考答案、密钥不能进仓库（CLAUDE.md 第5节）：只看这次相对 main 新增的内容。"""
    ref = '%s/%s' % (remote, base)
    if git(root, 'rev-parse', '--verify', '-q', ref)[0]:
        return []
    out = []
    added = git(root, 'diff', '--name-status', '--diff-filter=A', ref + '...HEAD')[1].splitlines()
    pdfs = [l.split('\t', 1)[1] for l in added if '\t' in l and l.lower().endswith('.pdf') and not l.split('\t', 1)[1].startswith(('tests/', 'web/assets/', 'web/vendor/'))]
    if pdfs:
        out.append((FAIL, '新增了PDF文件（真题/资料原文不能进仓库）：' + '；'.join(pdfs[:5])))
    diff = git(root, 'diff', '-U0', ref + '...HEAD', '--', '.', ':!tests/', ':!*.md')[1]
    if re.search(r'^\+.*(sk-[A-Za-z0-9]{24,}|api[_-]?key\s*[=:]\s*["\'][A-Za-z0-9]{20,})', diff, re.M | re.I):
        out.append((FAIL, '新增的代码里像是有 API key，请检查后再发布'))
    return out or [(OK, '没有新增PDF原文或疑似密钥')]


def check_new_ui_tests_in_workflow(root, base='main', remote='origin'):
    ref = '%s/%s' % (remote, base)
    if git(root, 'rev-parse', '--verify', '-q', ref)[0]:
        return []
    added = [l.split('\t', 1)[1] for l in git(root, 'diff', '--name-status', '--diff-filter=A', ref + '...HEAD', '--', 'tests/')[1].splitlines()
             if '\t' in l and re.search(r'tests/ui_[^/]+\.cjs$', l)]
    wf = ''
    wdir = os.path.join(root, '.github', 'workflows')
    for name in (os.listdir(wdir) if os.path.isdir(wdir) else []):
        wf += read(os.path.join(wdir, name)) or ''
    missing = [f for f in added if os.path.basename(f) not in wf]
    if missing:
        return [(WARN, '新增的界面测试没有写进 .github/workflows（云端不会跑它）：' + '；'.join(missing))]
    return [(OK, '新增界面测试都已写进工作流')]


def check_bug_record(root, base='main', remote='origin'):
    ref = '%s/%s' % (remote, base)
    if git(root, 'rev-parse', '--verify', '-q', ref)[0]:
        return []
    msgs = git(root, 'log', '--format=%s', ref + '..HEAD')[1]
    if not re.search(r'修复|修好|bug|Bug|BUG|修正', msgs):
        return [(OK, '本批提交里没有bug修复')]
    changed = git(root, 'diff', '--name-only', ref + '...HEAD')[1].splitlines()
    if '踩坑记录.md' not in changed:
        return [(WARN, '本批提交里有 bug 修复，但踩坑记录.md 没有更新（规矩：每个修复的 bug 都要记一条）')]
    return [(OK, '有 bug 修复，踩坑记录.md 已更新')]


def check_shared(root):
    script = os.path.join(root, 'tools', 'sync_shared.py')
    if not os.path.isfile(script):
        return []
    sibling = [d for d in os.listdir(os.path.dirname(root)) if d in ('fakao-rpg', 'shenlun-rpg') and os.path.join(os.path.dirname(root), d) != root]
    if not sibling:
        return [(WARN, '旁边找不到另一个仓库，没能检查两仓库共用文件是否一致（发布前请手动运行 sync_shared.py --strict）')]
    p = subprocess.run([sys.executable, script, '--strict'], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
    if p.returncode:
        return [(FAIL, '两仓库共用文件不一致：' + ' '.join(p.stdout.split())[:300] + '（先 sync_shared.py --pull 转移并提交）')]
    return [(OK, '两仓库共用文件一致')]


def check_tests(root):
    p = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
    tail = p.stdout.strip().splitlines()[-3:]
    return [(OK if p.returncode == 0 else FAIL, '完整单元测试：' + ' '.join(tail))]


def run(root, base='main', remote='origin', days=7, acked=(), tests=False, fetch=True):
    branch = git(root, 'rev-parse', '--abbrev-ref', 'HEAD')[1]
    if fetch:
        git(root, 'fetch', '-q', remote)
    if branch in (base, 'HEAD'):
        return [(FAIL, '当前在 %s：请在开发分支上运行' % branch)]
    results = []
    for result in (check_tree_clean(root), check_pushed(root, branch, remote), check_main_merged(root, base, remote),
                   check_parallel_branches(root, branch, base, remote, days, acked), check_versions(root, remote),
                   check_conflict_markers(root), check_secrets_and_samples(root, base, remote),
                   check_new_ui_tests_in_workflow(root, base, remote), check_bug_record(root, base, remote), check_shared(root)):
        results += result
    if tests:
        results += check_tests(root)
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--base', default='main')
    ap.add_argument('--remote', default='origin')
    ap.add_argument('--days', type=int, default=7)
    ap.add_argument('--ack-branch', action='append', default=[])
    ap.add_argument('--tests', action='store_true')
    ap.add_argument('--no-fetch', action='store_true')
    args = ap.parse_args(argv)
    root = git(os.getcwd(), 'rev-parse', '--show-toplevel', check=True)[1]
    acked = list(args.ack_branch)
    for line in (read(os.path.join(root, 'tools', 'release_acked_branches.txt')) or '').splitlines():       # 长期确认“不随发布”的旧分支（一行一个，#开头为注释）
        if line.strip() and not line.strip().startswith('#'):
            acked.append(line.split('#')[0].strip())
    results = run(root, args.base, args.remote, args.days, tuple(acked), args.tests, not args.no_fetch)
    for level, text in results:
        print('[%s] %s' % (level, text))
    failed = [t for l, t in results if l == FAIL]
    print('\n发布前检查：%s' % ('未通过（%d 项失败），不能创建 validate 分支' % len(failed) if failed else '通过（提醒项请在汇报里说明）'))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
