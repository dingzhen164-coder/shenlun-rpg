"""自编旧季与混合题库：检查核分只读，删除/恢复隔离、冲突和失败回滚。"""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rpg import api,importer,mock_imports,paths,vault
from tests.test_mock_score import paper


def management_fixture(p):
    legacy=p.vault/'FB模考试卷复盘/板块复盘/第33季'
    paper(legacy,wrong={101})
    for file in legacy.glob('*.md'):
        # 自编完整选择题，银行题块与真实补导入解析结果一致。
        text=file.read_text(encoding='utf-8')
        import re
        text=re.sub(r'(### (\d+)\. [^\n]+\n)自编条件题，仅用于隔离测试。',lambda m:m[1]+'自编第'+m[2]+'题，仅用于隔离测试。\n'+''.join('- **%s.** 自编%s\n'%(k,k) for k in 'ABCD'),text)
        file.write_text(text,encoding='utf-8')
    parsed={q['num']:q for q in importer._collect(paths.Paths(p.vault,'行测'),{'kind':'season','season':33})[0]}
    other=p.train/'模考复盘/第39季';other.mkdir(parents=True,exist_ok=True)
    (other/'01-政治理论.md').write_text('### 1. ✅\n自编第39季题。\n> 正确答案：**A**　我的答案：**A**\n---\n',encoding='utf-8')
    bank=p.train/'题库';bank.mkdir(parents=True,exist_ok=True)
    for board,nums in [('政治理论',range(1,66)),('资料分析',range(66,131))]:
        text='\ufeff# 自编混合题库\r\n\r\n'
        for n in nums:
            q=copy.deepcopy(parsed[n]);q['stem']=importer.with_source(q['stem'],q['source'])
            text+=importer.bank_block(q).replace('\n','\r\n')
        q.update(id='粉笔39季-001',stem='自编其他季：学习历史要保留。');text+=importer.bank_block(q).replace('\n','\r\n')
        q.update(id='粉笔333季-001',stem='自编相似季号：不能误删。');text+=importer.bank_block(q).replace('\n','\r\n')
        (bank/(board+'真题.md')).write_bytes(text.encode('utf-8'))
    return legacy


class MockImportsTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        for ctx in (patch.object(Path,'home',return_value=self.root/'home'),patch.dict(os.environ,{'SHENLUN_SUBJECT':'行测'}),patch.object(paths,'SETTINGS_DIR',self.root/'settings'),patch.object(paths,'SETTINGS_FILE',self.root/'settings/settings.json')):
            ctx.start();self.addCleanup(ctx.stop)
        self.p=paths.Paths(self.root/'vault','行测');self.p.ensure_train_dir();(self.p.vault/'copilot/skills/test').mkdir(parents=True)
        self.legacy=management_fixture(self.p);self.p=paths.Paths(self.p.vault,'行测')
        paths.save_settings({'subject':'行测','vaults':{'行测':str(self.p.vault)}})
        (self.p.train/'模考试卷').mkdir(exist_ok=True);(self.p.train/'模考试卷/第33季.pdf').write_bytes(b'%PDF-self-authored-only')
        with api.open_game() as g:
            g.state.setdefault('mocks',{})['33']={'score':72.3,'reviewed':{'政治理论':[1]}}
            g.state.setdefault('bank',{})['records']={'政治理论::粉笔33季-001':{'history':[{'ok':True}],'question':{'id':'粉笔33季-001'}}}
            g.state['mock_practice']=['33'];g.state['xp']=500
        self.original={str(f.relative_to(self.p.vault)):f.read_bytes() for f in self.p.vault.rglob('*') if f.is_file()}

    def banks(self):return {str(f):f.read_bytes() for f in (self.p.train/'题库').glob('*真题*.md')}
    def remove(self):
        p=api.import_season_remove({'season':33});return api.import_season_remove(dict(season=33,commit=True,digest=p['digest']))

    def test_old_season_check_calculates_and_preserves_every_file(self):
        r=api.import_preview({'kind':'season','season':33})
        self.assertEqual((r['estimate']['score'],r['saved_score']),(99.15,72.3))
        current={str(f.relative_to(self.p.vault)):f.read_bytes() for f in self.p.vault.rglob('*') if f.is_file()}
        self.assertEqual(self.original,current)
        # 入库检查失败也不能挡住已有对错核分。
        with patch.object(importer,'preview',side_effect=importer.ImportError_('自编缺图提示')):
            r=api.import_preview({'kind':'season','season':33});self.assertEqual(r['estimate']['score'],99.15);self.assertIn('缺图',r['preview_error'])

    def test_unknown_answers_are_not_counted_as_wrong(self):
        f=self.legacy/'01-政治理论.md';f.write_text(f.read_text(encoding='utf-8').replace('### 1. ✅','### 1. ⚪'),encoding='utf-8')
        r=api.import_preview({'kind':'season','season':33});self.assertIsNone(r['estimate']['score']);self.assertEqual(r['estimate']['unknown'],1)

    def test_remove_restore_exact_bytes_history_other_seasons_and_idempotence(self):
        before=self.banks();preview=api.import_season_remove({'season':33})
        self.assertEqual(preview['removed'],130);self.assertFalse((self.p.train/'导入回收').exists())
        r=self.remove();self.assertEqual(r['removed'],130)
        for file,data in self.banks().items():
            self.assertNotIn('粉笔33季-001'.encode(),data)
            if '粉笔39季-001'.encode() in before[file]:
                self.assertIn('粉笔39季-001'.encode(),data);self.assertIn('粉笔333季-001'.encode(),data)
        status=api.import_status({});self.assertNotIn(33,[s['season'] for s in status['seasons']]);self.assertEqual(status['recycled'][0]['token'],r['token'])
        for rel,data in self.original.items():
            if rel not in {str(Path(f).relative_to(self.p.vault)) for f in before}:self.assertEqual((self.p.vault/rel).read_bytes(),data,rel)
        # 原复盘/成绩仍可读取，删除只撤销题库入库。
        self.assertIn(33,[n for n,d in vault.seasons(self.p)])
        api.import_season_restore({'token':r['token']});self.assertEqual(before,self.banks())
        self.assertTrue(api.import_season_restore({'token':r['token']})['already'])
        self.assertEqual(api.import_status({})['recycled'],[])

    def test_restore_preserves_other_later_edits_but_refuses_changed_ids(self):
        r=self.remove();f=self.p.train/'题库/政治理论真题.md';extra='\n## 题目 自编后加-001\n### 题干\n后续自己的新题不能丢。\n'
        f.write_bytes(f.read_bytes()+extra.encode());api.import_season_restore({'token':r['token']})
        self.assertIn('后续自己的新题不能丢。',f.read_text(encoding='utf-8'));self.assertIn('粉笔33季-001',f.read_text(encoding='utf-8'))
        r=self.remove();f.write_bytes(f.read_bytes()+'\n## 题目 粉笔33季-001\n### 题干\n自编同号新内容，不可覆盖。\n'.encode());before=self.banks()
        with self.assertRaisesRegex(api.ApiError,'已有不同内容'):api.import_season_restore({'token':r['token']})
        self.assertEqual(before,self.banks())

    def test_preview_digest_and_invalid_inputs_cannot_mutate(self):
        p=api.import_season_remove({'season':33});f=self.p.train/'题库/政治理论真题.md';f.write_bytes(f.read_bytes()+b'\n# external edit\n');before=self.banks()
        with self.assertRaisesRegex(api.ApiError,'变化'):api.import_season_remove(dict(season=33,commit=True,digest=p['digest']))
        for value in (None,True,-1,'33','../33'):
            with self.assertRaises(api.ApiError):api.import_season_remove({'season':value})
        with self.assertRaises(api.ApiError):api.import_season_restore({'token':'../bad'})
        self.assertEqual(before,self.banks())

    def test_delete_io_failure_rolls_back_all_files(self):
        before=self.banks();p=api.import_season_remove({'season':33});raw=mock_imports._atomic;failed=[]
        def fail_once(file,data):
            if file.name=='资料分析真题.md' and not failed:failed.append(True);raise OSError('自编磁盘失败')
            return raw(file,data)
        with patch.object(mock_imports,'_atomic',side_effect=fail_once),self.assertRaises(api.ApiError):
            api.import_season_remove(dict(season=33,commit=True,digest=p['digest']))
        self.assertEqual(before,self.banks());self.assertEqual(api.import_status({})['recycled'],[])

    def test_manifest_failure_rolls_back_and_interrupted_delete_is_recoverable(self):
        before=self.banks();p=api.import_season_remove({'season':33});raw=mock_imports._atomic;failed=[]
        def fail_once(file,data):
            if file.name=='清单.json' and b'"state": "deleted"' in data and not failed:failed.append(True);raise OSError('自编清单失败')
            return raw(file,data)
        with patch.object(mock_imports,'_atomic',side_effect=fail_once),self.assertRaises(api.ApiError):api.import_season_remove(dict(season=33,commit=True,digest=p['digest']))
        self.assertEqual(before,self.banks())
        r=self.remove();folder=self.p.train/'导入回收'/r['token'];f=folder/'清单.json';meta=json.loads(f.read_text(encoding='utf-8'));meta['state']='prepared';f.write_text(json.dumps(meta),encoding='utf-8')
        self.assertTrue(api.import_status({})['recycled'][0]['recovery']);api.import_season_restore({'token':r['token']});self.assertEqual(before,self.banks())

    def test_pending_blocks_and_restore_io_failure_are_recoverable(self):
        pending=self.p.train/'题库/_待修/粉笔33季模考.md';pending.parent.mkdir(exist_ok=True)
        pending.write_text('## 题目 粉笔33季-999\n### 题干\n自编待修题。\n\n## 题目 粉笔39季-999\n### 题干\n自编其他季待修题。\n',encoding='utf-8')
        original=pending.read_bytes();before=self.banks();r=self.remove();self.assertEqual(r['removed'],131)
        self.assertNotIn('粉笔33季-999',pending.read_text(encoding='utf-8'));self.assertIn('粉笔39季-999',pending.read_text(encoding='utf-8'))
        removed=self.banks();pending_removed=pending.read_bytes();raw=mock_imports._atomic;failed=[]
        def fail_once(file,data):
            if file.name=='资料分析真题.md' and not failed:failed.append(True);raise OSError('自编恢复磁盘失败')
            return raw(file,data)
        with patch.object(mock_imports,'_atomic',side_effect=fail_once),self.assertRaises(api.ApiError):api.import_season_restore({'token':r['token']})
        self.assertEqual(removed,self.banks());self.assertEqual(pending.read_bytes(),pending_removed)
        api.import_season_restore({'token':r['token']});self.assertEqual(before,self.banks());self.assertEqual(pending.read_bytes(),original)

    def test_path_symlink_and_manifest_tampering_rejected(self):
        outside=self.root/'outside.md';outside.write_text('自编外部资料不能修改。', encoding='utf-8')
        link=self.p.train/'题库/外部真题.md';link.symlink_to(outside)
        with self.assertRaises(api.ApiError):api.import_season_remove({'season':33})
        link.unlink();r=self.remove();folder=self.p.train/'导入回收'/r['token'];f=folder/'清单.json';meta=json.loads(f.read_text(encoding='utf-8'));meta['entries'][0]['path']='../outside.md';f.write_text(json.dumps(meta),encoding='utf-8');before=self.banks()
        with self.assertRaises(api.ApiError):api.import_season_restore({'token':r['token']})
        self.assertEqual(before,self.banks());self.assertEqual(outside.read_text(encoding='utf-8'),'自编外部资料不能修改。')
