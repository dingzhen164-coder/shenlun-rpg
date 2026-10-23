"""万象峰独立迁移、四路PDF导入、学习进度与奖励隔离；只用临时库/现画示例PDF。"""
import base64
import copy
import json
import os
import unittest
from unittest.mock import patch

from rpg import api, politics, tianji, wanxiang_journal as journal
from tests import test_tianji as fixtures


def setUpModule():
    os.environ['SHENLUN_SUBJECT'] = '行测'


def tearDownModule():
    os.environ.pop('SHENLUN_SUBJECT', None)


@unittest.skipIf(fixtures.fitz is None, '缺PDF组件')
class JournalTests(unittest.TestCase):
    def setUp(self):
        fixtures.TianjiTest.setUp(self)
        from tests.politics_fixture import atlas_data
        from rpg import paths
        politics.atomic_json(paths.Paths(self.vault,'行测').train/'时政知识地图/内容.json',atlas_data())
    tearDown = fixtures.TianjiTest.tearDown

    def call(self, name='', body=None):
        return api.ROUTES[('POST','/api/wanxiang/journal'+('/'+name if name else ''))](body or {})

    def upload(self, channel, file, **kwargs):
        return api.ROUTES[('POST','/api/wanxiang/import')](dict(channel=channel,name=file.name,
                   data=base64.b64encode(file.read_bytes()).decode(),**kwargs))

    def test_copy_isolated_content_progress_pdf_annotations_and_no_rewards(self):
        original=api.tj_import({'data':base64.b64encode(self.month.read_bytes()).decode()})
        key=dict(kind='month',id=original['id'])
        api.tj_mark(dict(key,quiz=0,choice='B'))
        api.tj_mark(dict(key,read=0))
        before=api.tj_get(key)
        with api.open_game(save=False) as g:
            old=copy.deepcopy(g.state['tianji']);xp=g.state['xp']
            old_file=tianji._file(g.paths,'month',key['id']);raw=old_file.read_bytes()
            src=politics.source(g.paths,dict(key,source='tianji',news=0))
            saved_notes={'fixture':{'word':'自编词义','explanation':{'meaning':'测试已有批注'}}}
            politics.atomic_json(g.paths.train/'词义批注'/(politics.identity(src)+'.json'),saved_notes)
        self.assertEqual(len(self.call()['month']),1)
        with patch.object(tianji,'load',side_effect=AssertionError('不许依赖旧模块')):
            copied=self.call('get',key)
        self.assertEqual(copied['data']['news'],before['data']['news'])
        self.assertIn('万象时政/原文',copied['data']['pdf'])
        self.assertEqual(copied['progress']['read'],[0])
        with api.open_game(save=False) as g:
            src=politics.source(g.paths,dict(key,source='wanxiang_journal',news=0))
            self.assertEqual(politics.list_notes(g.paths,src),saved_notes)
            self.assertTrue((g.paths.vault/copied['data']['pdf']).is_file())
        self.call('mark',dict(key,reset='quiz'))
        self.assertEqual(self.call('mark',dict(key,quiz=0,choice='B'))['events'],[])
        self.call('mark',dict(key,read=1))
        with api.open_game(save=False) as g:
            self.assertEqual(g.state['tianji'],old)
            self.assertEqual(g.state['xp'],xp)
            self.assertEqual(old_file.read_bytes(),raw)
        self.call('delete',key)
        self.assertEqual(self.call()['month'],[],'删除新副本后不重新复制')
        self.assertEqual(api.tj_get(key)['data']['title'],before['data']['title'])

    def test_four_import_channels_and_wrong_type_is_rejected(self):
        month=self.upload('month',self.month)
        topic=self.upload('topic',self.topic)
        self.assertEqual((month['kind'],topic['kind']),('month','topic'))
        with self.assertRaises(api.ApiError):self.upload('month',self.topic)
        study=self.upload('sprint-study',self.month,exam='2026-12-shengkao')
        self.assertGreater(study['added'],0)
        again=self.upload('sprint-study',self.month,exam='2026-12-shengkao')
        self.assertTrue(again['duplicate'])
        quiz=self.upload('sprint-quiz',self.topic,exam='2027-03-shengkao')
        self.assertGreater(quiz['questions'],0)
        with api.open_game(save=False) as g:
            first=politics.atlas(g.paths,'2026-12-shengkao')
            self.assertTrue(any(politics.digest_items(m) for m in first['materials']))
            self.assertTrue(politics.atlas(g.paths,'2027-03-shengkao')['questions'])
        self.assertEqual(api.tj_list({})['month'],[],'新导入不回写天机台')

    def test_digest_progress_validation_and_exam_isolation(self):
        self.upload('sprint-study',self.month,exam='2026-12-shengkao')
        with api.open_game(save=False) as g:
            data=politics.atlas(g.paths,'2026-12-shengkao')
            item=next(x for m in data['materials'] for x in politics.digest_items(m))
            politics.set_progress(g.paths,dict(exam='2026-12-shengkao',field='digest',id=item['id'],value='forgot'))
            self.assertEqual(politics.progress(g.paths,'2026-12-shengkao')['digest'][item['id']],'forgot')
            self.assertNotIn('digest',politics.progress(g.paths,'2027-03-shengkao'))
            with self.assertRaises(politics.PoliticsError):politics.set_progress(g.paths,dict(field='digest',id='fake',value='remember'))

    def test_question_only_papers_have_distinct_sources_and_no_learning_entries(self):
        for i in (1,2):
            file=self.vault/('自编纯题卷%s.pdf'%i)
            fixtures.make_pdf(file,[[(1,'1.（单选）自编判断题%s：'%i),(1,'A.甲'),(1,'B.乙'),(1,'C.丙'),(1,'D.丁'),(1,'1.【答案】A。解析：自编说明。')]])
            result=self.upload('sprint-quiz',file,exam='2027-03-shengkao')
            self.assertEqual(result['questions'],1)
        with api.open_game(save=False) as g:
            data=politics.atlas(g.paths,'2027-03-shengkao')
            self.assertEqual(len(data['materials']),2)
            self.assertTrue(all(m['practice_only'] for m in data['materials']))
            self.assertEqual(len({q['material'] for q in data['questions']}),2)

    def test_multi_answer_and_reward_ledger_survives_reset(self):
        result=self.upload('month',self.month)
        key=dict(kind='month',id=result['id'])
        with api.open_game() as g:
            d=journal.load(g.paths,**dict(kind='month',iid=result['id']))
            d['questions'][0]['answer']='AB'
            journal._write(journal._file(g.paths,'month',result['id']),d)
        first=self.call('mark',dict(key,quiz=0,choice='BA'))
        self.assertTrue(first['progress']['quiz']['0']['ok'])
        self.assertTrue(first['events'])
        self.call('mark',dict(key,reset='quiz'))
        self.assertEqual(self.call('mark',dict(key,quiz=0,choice='AB'))['events'],[])
        for body in [dict(key,quiz=0,choice='AA'),dict(key,cloze='no-such-blank',ok=1),dict(key,id='../outside')]:
            with self.assertRaises(api.ApiError):self.call('mark',body)

    def test_bad_payload_rejected_and_subject_guard(self):
        for channel in ['unknown','month','sprint-study','sprint-quiz']:
            with self.assertRaises(api.ApiError):api.ROUTES[('POST','/api/wanxiang/import')]({'channel':channel,'data':'not pdf'})
        with patch.dict(os.environ,{'SHENLUN_SUBJECT':'申论'}):
            with self.assertRaises(api.ApiError):self.call()
