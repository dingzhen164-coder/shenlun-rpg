"""发布前检查脚本 tools/release_precheck.py：用临时 git 仓库模拟“别的AI推了新提交/有未合入的并行分支/版本号不一致”，确保这些情况会挡住发布。"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import release_precheck as rp


def sh(cwd, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t', GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t')
    return subprocess.run(['git', *args], cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env).stdout.strip()


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


class PrecheckTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup); base = t.name
        self.remote, self.a, self.b = [os.path.join(base, x) for x in ('remote.git', 'a', 'b')]
        sh(base, 'init', '-q', '--bare', '-b', 'main', self.remote)
        sh(base, 'clone', '-q', self.remote, self.a)
        write(self.a, 'CLAUDE.md', '每个版本的更新记录都写明“旧存档照常使用”\n')
        write(self.a, 'rpg/version.py', 'VERSION = "1.0.0"\n')
        write(self.a, 'rpg/data/changelog.md', '## 1.0.0 · 2026-01-01\n- 旧存档照常使用\n')
        write(self.a, '.github/release-request.json', json.dumps({'version': '1.0.0'}))
        sh(self.a, 'add', '-A'); sh(self.a, 'commit', '-qm', 'init'); sh(self.a, 'push', '-q', 'origin', 'main')
        sh(self.a, 'tag', 'v1.0.0'); sh(self.a, 'push', '-q', '--tags')
        sh(self.a, 'checkout', '-qb', 'dev'); sh(self.a, 'push', '-q', '-u', 'origin', 'dev')
        sh(base, 'clone', '-q', self.remote, self.b); sh(self.b, 'checkout', '-q', 'dev')

    def levels(self, results):
        return [l for l, _ in results]

    def test_clean_new_version_passes_the_basic_checks(self):
        write(self.a, 'rpg/version.py', 'VERSION = "1.1.0"\n')
        write(self.a, 'rpg/data/changelog.md', '## 1.1.0 · 2026-02-01\n- 新功能\n- 旧存档照常使用\n\n## 1.0.0 · 2026-01-01\n- 旧存档照常使用\n')
        write(self.a, '.github/release-request.json', json.dumps({'version': '1.1.0'}))
        sh(self.a, 'add', '-A'); sh(self.a, 'commit', '-qm', '1.1.0'); sh(self.a, 'push', '-q')
        self.assertEqual(rp.check_tree_clean(self.a)[0][0], rp.OK)
        self.assertEqual(rp.check_pushed(self.a, 'dev')[0][0], rp.OK)
        self.assertEqual(rp.check_main_merged(self.a)[0][0], rp.OK)
        self.assertEqual(rp.check_versions(self.a), [(rp.OK, rp.check_versions(self.a)[0][1])])

    def test_other_ai_pushed_to_same_branch_blocks(self):
        write(self.b, 'other.txt', 'codex'); sh(self.b, 'add', '-A'); sh(self.b, 'commit', '-qm', 'codex work'); sh(self.b, 'push', '-q')
        sh(self.a, 'fetch', '-q')
        res = rp.check_pushed(self.a, 'dev')
        self.assertEqual(res[0][0], rp.FAIL); self.assertIn('不在本地', res[0][1])

    def test_unpushed_and_dirty_block(self):
        write(self.a, 'x.txt', '1'); sh(self.a, 'add', '-A'); sh(self.a, 'commit', '-qm', 'local only')
        self.assertEqual(rp.check_pushed(self.a, 'dev')[0][0], rp.FAIL)
        write(self.a, 'y.txt', '2')
        self.assertEqual(rp.check_tree_clean(self.a)[0][0], rp.FAIL)

    def test_parallel_branch_must_be_merged_or_acknowledged(self):
        sh(self.b, 'checkout', '-qb', 'codex/feature'); write(self.b, 'f.txt', 'x'); sh(self.b, 'add', '-A'); sh(self.b, 'commit', '-qm', 'feature'); sh(self.b, 'push', '-q', '-u', 'origin', 'codex/feature')
        sh(self.a, 'fetch', '-q')
        self.assertEqual(rp.check_parallel_branches(self.a, 'dev')[0][0], rp.FAIL)
        self.assertEqual(rp.check_parallel_branches(self.a, 'dev', acked=('codex/feature',))[0][0], rp.OK)
        old = rp.check_parallel_branches(self.a, 'dev', now=time.time() + 30 * 86400)
        self.assertEqual(old[0][0], rp.WARN, '很久以前的分支只提醒')
        sh(self.a, 'merge', '-q', 'origin/codex/feature')
        self.assertEqual(rp.check_parallel_branches(self.a, 'dev')[0][0], rp.OK, '合入后通过')

    def test_main_has_new_release_blocks(self):
        sh(self.a, 'checkout', '-q', 'main'); write(self.a, 'rel.txt', '1'); sh(self.a, 'add', '-A'); sh(self.a, 'commit', '-qm', 'released'); sh(self.a, 'push', '-q')
        sh(self.a, 'checkout', '-q', 'dev')
        self.assertEqual(rp.check_main_merged(self.a)[0][0], rp.FAIL)

    def test_version_mismatch_and_not_bumped_block(self):
        res = rp.check_versions(self.a)
        self.assertTrue(any(l == rp.FAIL and '不高于已发布' in t for l, t in res), '没改版本号')
        write(self.a, 'rpg/version.py', 'VERSION = "1.2.0"\n')
        res = rp.check_versions(self.a)
        self.assertTrue(any('更新记录顶部' in t for l, t in res)); self.assertTrue(any('release-request' in t for l, t in res))
        write(self.a, 'rpg/data/changelog.md', '## 1.2.0 · 2026-02-01\n- 新功能\n')
        self.assertTrue(any('旧存档照常使用' in t for l, t in rp.check_versions(self.a)))

    def test_conflict_markers_block(self):
        write(self.a, 'a.py', 'x\n<<<<<<< HEAD\ny\n=======\nz\n>>>>>>> other\n'); sh(self.a, 'add', '-A')
        self.assertEqual(rp.check_conflict_markers(self.a)[0][0], rp.FAIL)

    def test_new_pdf_in_repo_blocks(self):
        write(self.a, 'docs/真题.pdf', '%PDF'); sh(self.a, 'add', '-A'); sh(self.a, 'commit', '-qm', 'pdf'); sh(self.a, 'push', '-q')
        self.assertEqual(rp.check_secrets_and_samples(self.a)[0][0], rp.FAIL)


if __name__ == '__main__':
    unittest.main()
