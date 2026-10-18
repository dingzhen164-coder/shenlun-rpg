"""自编130题参考卷：精确估分、未知/空题、旧分数保护与补导入用时。"""
import base64
import copy
import datetime as dt
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rpg import api,config,engine,html_mock,mock,mock_score,paths,store,trainer,vault
from tests.test_html_mock import body,fixture


def paper(folder,wrong=()):
    folder.mkdir(parents=True,exist_ok=True)
    groups=[('政治理论',20),('常识判断',15),('逻辑填空',15),('片段阅读',10),('语句排序',5),('数量关系',10),('图形推理',10),('定义判断',10),('类比推理',5),('论证逻辑',5),('一拖五',5),('资料分析',20)]
    number=0
    for i,(board,count) in enumerate(groups):
        text=[]
        for _ in range(count):
            number+=1;icon='❌' if number in wrong else '✅'
            text.append('### %d. %s\n自编条件题，仅用于隔离测试。\n> [!check]- 答案\n> 正确答案：**A**　我的答案：**%s**\n> [!note] 复盘\n> 自编解析。\n---\n' % (number,icon,'B' if icon=='❌' else 'A'))
        (folder/('%02d-%s.md'%(i+1,board))).write_text(''.join(text),encoding='utf-8')


class MockScoreTest(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)
        for ctx in (patch.object(Path,'home',return_value=self.root/'home'),patch.dict(os.environ,{'SHENLUN_SUBJECT':'行测'}),patch.object(paths,'SETTINGS_DIR',self.root/'settings'),patch.object(paths,'SETTINGS_FILE',self.root/'settings/settings.json')):
            ctx.start();self.addCleanup(ctx.stop)
        self.p=paths.Paths(self.root/'vault','行测');self.p.ensure_train_dir()
        (self.p.vault/'copilot/skills/test').mkdir(parents=True)
        paths.save_settings({'subject':'行测','vaults':{'行测':str(self.p.vault)}})
        self.g=engine.Game(self.p,config.Rules(),config.Persona(),config.Lines(),store.new_state(dt.date(2026,10,18)),dt.date(2026,10,18))
        self.folder=self.p.train/'模考复盘/第39季'

    def test_exact_weights_unknown_and_explicit_blank(self):
        paper(self.folder,wrong={101})
        s=mock.summary(self.g)['seasons'][0]
        self.assertEqual(s['estimate']['score'],99.15)
        self.assertIsNone(s['score'])
        self.assertEqual(self.g.state.get('boss'),[])
        file=self.folder/'11-一拖五.md';text=file.read_text(encoding='utf-8');file.write_text(text.replace('### 106. ✅','### 106. ⚪'), encoding='utf-8')
        r=mock.summary(self.g)['seasons'][0]['estimate'];self.assertFalse(r['ready']);self.assertEqual(r['unknown'],1);self.assertIsNone(r['score'])
        self.g.state.setdefault('mocks',{}).setdefault('39',{})['html_import']={'known_numbers':[106]}
        self.assertEqual(mock.summary(self.g)['seasons'][0]['estimate']['score'],98.3)

    def test_configured_points_and_subject_guard(self):
        from types import SimpleNamespace
        paper(self.folder,wrong={1})
        self.g.rules.raw.update({'模考参考.分值.政治理论':'0.6','模考参考.分值.资料分析':'0.9'})
        self.assertEqual(mock.summary(self.g)['seasons'][0]['estimate']['score'],99.4)
        self.assertIsNone(mock_score.estimate(SimpleNamespace(subject='法考'),None,None,None))

    def test_saved_score_does_not_become_estimate_or_change_rewards(self):
        paper(self.folder,wrong={101});rec={'score':70.6,'reviewed':{'资料分析':[111]},'html_import':{'reported_score':70.6}}
        self.g.state.setdefault('mocks',{})['39']=copy.deepcopy(rec)
        before=copy.deepcopy(self.g.state);s=mock.summary(self.g)['seasons'][0]
        self.assertEqual((s['score'],s['reported_score'],s['estimate']['score']),(70.6,70.6,99.15))
        self.assertEqual(before,self.g.state)

    def test_incomplete_profile_duplicate_or_invalid_rule_no_full_score(self):
        paper(self.folder);(self.folder/'12-资料分析.md').unlink()
        self.assertFalse(mock.summary(self.g)['seasons'][0]['estimate']['ready'])
        paper(self.folder);file=self.folder/'12-资料分析.md';file.write_text(file.read_text(encoding='utf-8')+'### 1. ✅\n自编重复题。\n---\n', encoding='utf-8')
        self.assertIn('重复',mock.summary(self.g)['seasons'][0]['estimate']['reason'])
        paper(self.folder);self.g.rules.raw['模考参考.分值.逻辑判断']='NaN'
        self.assertIsNone(mock.summary(self.g)['seasons'][0]['estimate']['score'])

    def test_duration_reading_does_not_pollute_question_or_analysis(self):
        for value,expected in [('36秒',36),('1 分 25 秒',85),('1:25',85),('1时2分3秒',3723),('0秒',0),('未提供',None),('1:99',None)]:self.assertEqual(vault.parse_seconds(value),expected)
        self.folder.mkdir(parents=True);f=self.folder/'01-资料分析.md';f.write_text('### 1. ✅\n自编题。\n> 正确答案：**A**　我的答案：**A**\n> 用时：**85秒**\n> [!note] 复盘\n> 自编解析。\n---\n', encoding='utf-8')
        q=vault.parse_board_file(f)[0];self.assertEqual(q['seconds'],85);self.assertNotIn('用时',q['body']);self.assertNotIn('用时',q['analysis'])

    def test_reimport_adds_times_and_report_without_overwriting_notes_or_score(self):
        b=body();r=api.import_html(b);api.import_html(dict(b,commit=True,digest=r['digest']))
        review=next(self.p.train.glob('模考复盘/第39季/*.md'));review.write_text(review.read_text(encoding='utf-8')+'\n> 自编用户笔记保留。\n', encoding='utf-8');old=review.read_bytes()
        with api.open_game() as g:g.state['mocks']['39']['score']=66.6
        text=fixture().replace('<app-ti>','<app-ti><span class="answer-time">1分25秒</span>').replace('<html>','<html><span class="my-info-score-value-cur">70.6</span>')
        b['data']=base64.b64encode(text.encode()).decode();r=api.import_html(b);rep=api.import_html(dict(b,commit=True,digest=r['digest']))
        self.assertEqual((rep['ready'],rep['timed'],rep['reported_score']),(0,10,70.6));self.assertEqual(review.read_bytes(),old)
        with api.open_game(save=False) as g:
            self.assertEqual((g.state['mocks']['39']['score'],g.state['mocks']['39']['html_import']['reported_score']),(66.6,70.6))
            self.assertEqual(g.minutes(g.t),120)
            response=trainer.start(g,{'type':'mock_review','season':39,'board':'资料分析'})
            self.assertIn('原答题用时：1:25',str(response))
        # 新建复盘也把用时写在答案后、解析前；不依赖存档才可读。
        other=paths.Paths(self.root/'other','行测');other.ensure_train_dir();r=html_mock.import_file(other,b);html_mock.import_file(other,dict(b,commit=True,digest=r['digest']))
        q=vault.parse_board_file(next(other.train.glob('模考复盘/第39季/*.md')))[0];self.assertEqual(q['seconds'],85)
