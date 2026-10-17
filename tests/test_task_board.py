"""任务板：自编临时规则/学习证据；配置原子写入、冲突、跨日、幂等及原档兼容。"""
import copy
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rpg import config, engine, paths, store, task_board


class TaskBoardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = patch.object(Path, 'home', return_value=Path(self.tmp.name)/'fake-home')
        self.home.start()
        self.addCleanup(self.home.stop)
        self.p = paths.Paths(Path(self.tmp.name)/'vault', '行测') if hasattr(config, 'canon_key') else paths.Paths(Path(self.tmp.name)/'vault')
        self.p.ensure_train_dir()
        self.day = dt.date(2026, 10, 17)
        self.g = engine.Game(self.p, task_board._rules(type('G', (), {'subject':'行测'})(), self.p.rules.read_text(encoding='utf-8')), config.Persona(), config.Lines(), store.new_state(self.day), self.day)

    def configure(self, **extra):
        c = task_board.settings(self.g)
        return task_board.save(self.g, dict(c, tasks=[dict(id='test',title='自编方法整理',board='',minutes=30)], **extra))

    def test_config_preserves_unknown_rules_and_conflicts(self):
        with self.p.rules.open('a', encoding='utf-8') as f:
            f.write('\n# 自编注释\n- 外部自定义: 保留\n')
        c = task_board.settings(self.g)
        body = dict(c, daily_minutes=240, daily_title='方法精进', tasks=[])
        result = task_board.save(self.g, body)
        self.assertEqual(result['config']['daily_minutes'],240)
        text = self.p.rules.read_text(encoding='utf-8')
        self.assertIn('# 自编注释',text)
        self.assertIn('- 外部自定义: 保留',text)
        with self.assertRaises(ValueError): task_board.save(self.g,body)
        self.assertEqual(self.p.rules.read_text(encoding='utf-8'),text)

    def test_invalid_settings_never_write(self):
        c = task_board.settings(self.g)
        before = self.p.rules.read_bytes()
        for extra in ({'daily_minutes':0},{'daily_minutes':True},{'tasks':[dict(id='../../x',title='a',minutes=30)]},{'daily_title':'注入\n- 经验.听道每分钟: 900'},{'daily_title':'注释  # 丢失'}):
            with self.subTest(extra=extra),self.assertRaises(ValueError): task_board.save(self.g,dict(c,**extra))
        self.assertEqual(self.p.rules.read_bytes(),before)

    def test_record_once_and_delete_retracts_progress(self):
        b = self.configure()
        self.g.state['journey']={'schema':1,'worlds':{}}
        old = copy.deepcopy(self.g.state['journey'])
        body=dict(id='test',revision=b['config']['revision'],op='once',minutes=30,note='自编学习备注')
        after=task_board.record(self.g,body)
        self.assertEqual(after['tasks'][0]['current'],30)
        self.assertEqual(after['daily_current'],30)
        snapshot=copy.deepcopy(self.g.state)
        task_board.record(self.g,body)
        self.assertEqual(self.g.state,snapshot)
        self.assertEqual(self.g.state['journey'],old)
        with self.assertRaises(ValueError):task_board.record(self.g,dict(body,minutes=31))
        self.g.delete_selfstudy(self.g.state['selfstudy'][-1]['id'])
        self.assertEqual(task_board.view(self.g)['tasks'][0]['current'],0)
        self.assertEqual(task_board.view(self.g)['daily_current'],0)

    def test_week_evidence_deduplicates_and_rejects_future(self):
        self.g.state['mocks']={'1':dict(score=60,date='2026-10-12'),'2':dict(score=70,date='2026-10-18'),'3':dict(score=None,date='2026-10-17')}
        self.g.state['boss']=[dict(name='第1季',score=60,d='2026-10-12',kind='大比'),dict(name='旧周',score=60,d='2026-10-11',kind='大比'),dict(name='第3季',score=50,d='2026-10-17',kind='大比')]
        self.assertEqual(task_board.view(self.g)['weekly_current'],1)
        self.g.state['mocks']['1']['score']=None
        self.assertEqual(task_board.view(self.g)['weekly_current'],0)

    def test_day_rollover_restart_and_rename_keep_history(self):
        b=self.configure()
        task_board.record(self.g,dict(id='test',revision=b['config']['revision'],op='roll',minutes=20,note=''))
        c=task_board.settings(self.g);c['tasks'][0]['title']='修改后的任务'
        self.assertEqual(task_board.save(self.g,c)['tasks'][0]['current'],20)
        store.Store(self.p).save(self.g.state,self.day)
        state=store.Store(self.p).load(self.day)
        self.assertEqual(state['selfstudy'][0]['task_board_id'],'test')
        self.g.today=self.day+dt.timedelta(days=1);self.g.t=self.g.today.isoformat()
        self.assertEqual(task_board.view(self.g)['tasks'][0]['current'],0)
        self.assertEqual(len(self.g.state['selfstudy']),1)

    def test_failed_replace_leaves_rules_intact(self):
        before=self.p.rules.read_bytes()
        with patch('rpg.task_board.os.replace',side_effect=OSError('自编磁盘失败')):
            with self.assertRaises(OSError):self.configure()
        self.assertEqual(self.p.rules.read_bytes(),before)
        self.assertEqual(list(self.p.rules.parent.glob('.task-board-*')),[])

    @unittest.skipUnless(hasattr(config, 'canon_key'), '两科程序专有的科目隔离')
    def test_subject_settings_are_independent(self):
        p2=paths.Paths(Path(self.tmp.name)/'office', '申论');p2.ensure_train_dir()
        g2=engine.Game(p2, config.Rules(p2.rules.read_text(encoding='utf-8'),'申论'),config.Persona(),config.Lines(),store.new_state(self.day),self.day)
        c=task_board.settings(g2)
        self.assertEqual(c['daily_minutes'],300)
        task_board.save(g2,dict(c,daily_title='公文研习',daily_minutes=180,tasks=[]))
        self.assertEqual(task_board.settings(g2)['daily_title'],'公文研习')
        self.assertNotEqual(task_board.settings(self.g)['daily_title'],'公文研习')
        self.assertEqual(task_board.view(g2)['daily_current'],0)

    def test_custom_two_hour_goal_survives_startup_migration(self):
        c=task_board.settings(self.g)
        task_board.save(self.g,dict(c,daily_minutes=120,tasks=[]))
        self.p.ensure_train_dir()
        self.assertEqual(task_board.settings(self.g)['daily_minutes'],120)
