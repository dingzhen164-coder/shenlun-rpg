"""3.6.1五项回归：同匣分类、旧批注升级、考试隔离、真实PDF增量导入和旧专题目录。只用自编资料。"""
import base64
import copy
import datetime as dt
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rpg import api, cards, config, engine, paths, political_outline, politics, politics_import, store, tianji
from tests.politics_fixture import atlas_data
from tests.test_tianji import make_pdf, TOPIC, fitz


def setUpModule():
    os.environ['SHENLUN_SUBJECT'] = '行测'


def tearDownModule():
    os.environ.pop('SHENLUN_SUBJECT', None)


class Revision361Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name)
        self.pp = paths.Paths(self.vault, '行测')
        self.pp.ensure_train_dir()
        self.base = atlas_data()
        politics.atomic_json(self.pp.train / '时政知识地图/内容.json', self.base)
        day = dt.date(2026, 10, 21)
        self.g = engine.Game(self.pp, config.Rules(), config.Persona(), config.Lines(), store.new_state(day), day)
        cards._CACHE['key'] = None

    def test_same_deck_classification_next_answer_and_undo(self):
        notes = {}
        for category, word in [('geo','地理'),('history','文史'),('economy','经济'),('science','科技')]:
            notes[category] = cards.add(self.g, {'deck':'常识判断', 'type':'问答', 'front':'【'+word+'常识】自编问题', 'back':'自编答案'})
        misleading = cards.add(self.g, {'deck':'常识判断::地理::政治理论','type':'问答','front':'【地理常识】深层政治', 'back':'答'})
        files = {f:f.read_bytes() for f in (self.pp.train/'卡片').glob('*.md')}
        for category, note in notes.items():
            scope = {'decks':['常识判断','常识判断::地理::政治理论'], 'category':category}
            key = note['id']+'#1'
            self.assertEqual(cards.next_card(self.g,'',scope)['card']['key'],key)
            self.assertEqual(cards.overview(self.g,scope)['cards'],1)
            with patch.object(api,'_cards',side_effect=lambda fn:fn(self.g)):
                with self.assertRaises(cards.CardError):
                    api.cards_answer({'key':misleading['id']+'#1','rating':4,'scope':scope})
                api.cards_answer({'key':key,'rating':4,'scope':scope})
            wrong = dict(scope,category='history' if category=='geo' else 'geo')
            before = copy.deepcopy(self.g.state)
            with self.assertRaises(cards.CardError):
                cards.undo(self.g,scope=wrong)
            self.assertEqual(self.g.state,before)
            self.assertEqual(cards.undo(self.g,scope=scope),key)
        self.assertEqual(files,{f:f.read_bytes() for f in files},'分类与温习不搬动卡片')

    def test_exam_catalog_and_progress_are_separate(self):
        catalog = politics.catalog(self.pp)
        self.assertEqual([e['title'] for e in catalog],['2026.10国考时政地图','2026.12省考时政地图','2027.3省考时政地图'])
        self.assertEqual([e['counts']['total'] for e in catalog],[1,0,0])
        self.assertEqual(catalog[2]['range'],'2026年1月至2027年2月上')
        politics.set_progress(self.pp,{'field':'status','id':'m1','value':'done'})
        self.assertEqual(politics.progress(self.pp)['status'],{'m1':'done'})
        self.assertEqual(politics.progress(self.pp,'2026-12-shengkao')['status'],{})
        with self.assertRaises(politics.PoliticsError):
            politics.set_progress(self.pp,{'exam':'2026-12-shengkao','field':'status','id':'m1','value':'done'})
        with self.assertRaises(politics.PoliticsError):
            politics.atlas(self.pp,'../../bad')

    def test_event_counts_not_theme_or_question_counts(self):
        m=self.base['materials'][0]
        m2=dict(m,id='copy',tags=['t0','t1'],questions=[2,3])
        helper=dict(m,id='helper',kind='配套练习')
        result=politics.source_counts(dict(self.base,materials=[m,m2,helper]))
        self.assertEqual(result['total'],1)
        self.assertEqual(result['kinds']['重大会议'],1)

    def test_legacy_note_stays_cached_until_one_explicit_upgrade(self):
        src=politics.source(self.pp,{'source':'atlas','material':'m1'})
        body={'paragraph':src['text'],'word':'主产区','start':src['text'].index('主产区'),'end':src['text'].index('主产区')+3}
        anchor=politics.validate_anchor(src,body);key=politics.digest(anchor)
        old=dict(anchor,key=key,explanation={k:'旧解释' for k in politics.FIELDS[:5]})
        file=self.pp.train/'词义批注'/(politics.identity(src)+'.json')
        politics.atomic_json(file,{key:old})
        answer={k:'自编通俗解释' for k in politics.FIELDS};answer['evidence']='在主产区布局产能'
        with patch('rpg.politics.ai.available',return_value=True),patch('rpg.politics.ai.chat',return_value=json.dumps(answer)) as chat:
            self.assertEqual(politics.explain(self.pp,src,body)['note'],old)
            chat.assert_not_called()
            upgraded=politics.explain(self.pp,src,dict(body,refresh=True))
            self.assertEqual(upgraded['note']['version'],2)
            self.assertEqual(upgraded['note']['explanation']['example'],'自编通俗解释')
            self.assertTrue(politics.explain(self.pp,src,dict(body,refresh=True))['cached'])
            self.assertEqual(chat.call_count,1)

    def test_old_topic_navigation_groups_without_reindexing_or_rewriting(self):
        news=[{'no':i+1,'title':'习近平强调，到2035年建成健康中国是我们作出的一项战略决策','group':'两会讲话','paras':['建设健康中国。自编第%d段。'%i], 'qs':[i]} for i in range(3)]
        news.append({'no':4,'title':'习近平强调，“十五五”时期如期实现建军目标','group':'两会讲话','paras':['国防和军队现代化取得进展。'],'qs':[3]})
        data={'id':'old-topic','kind':'topic','news':news,'questions':[{'id':i,'news':i} for i in range(4)],'cloze':[]}
        file=self.pp.train/'天机简报/专题时政/old-topic.json';politics.atomic_json(file,data)
        raw=file.read_bytes()
        loaded=tianji.load(self.pp,'topic','old-topic')
        self.assertEqual(loaded['outline'],[{'title':'建设健康中国','group':'两会讲话','items':[0,1,2]},{'title':'国防和军队建设','group':'两会讲话','items':[3]}])
        self.assertEqual(loaded['news'],news)
        self.assertEqual(loaded['questions'],data['questions'])
        self.assertEqual(file.read_bytes(),raw)

    @unittest.skipIf(fitz is None,'需要已有PDF组件')
    def test_cross_page_headings_remain_separate(self):
        p=self.vault/'heading.pdf'
        make_pdf(p,[[(1,'一、建设现代化产业体系')],[(1,'加快推进新型工业化。'),(1,'二、保障粮食安全'),(1,'加强粮食生产能力建设。')]])
        with fitz.open(p) as doc:
            paras=[text for _,text in tianji.paragraphs(doc)]
        self.assertTrue(any('一、建设现代化产业体系'==x for x in paras))
        self.assertTrue(any('二、保障粮食安全'==x for x in paras))

    def upload(self,p,exam='2026-12-shengkao',**kwargs):
        return politics_import.import_pdf(self.pp,dict(exam=exam,name=p.name,data=base64.b64encode(p.read_bytes()).decode(),**kwargs))

    @unittest.skipIf(fitz is None,'需要已有PDF组件')
    def test_generic_pdf_append_answers_multiple_choice_and_duplicate(self):
        p=self.vault/'自编会议.pdf'
        make_pdf(p,[[(1,'一、自编经济工作会议'),(1,'2026年11月1日召开自编会议。'),(1,'在主产区布局产能，支持产业发展。'),(1,'配套练习'),(1,'1.（多选）自编政策支持的对象有哪些？'),(1,'A.主产区'),(1,'B.主销区'),(1,'C.全部地区'),(1,'D.其他地区'),(1,'参考答案'),(1,'1.【答案】AB。解析：这里是自编解析。')]])
        before=(self.pp.train/'时政知识地图/内容.json').read_bytes()
        result=self.upload(p)
        self.assertEqual(result['added'],1)
        self.assertEqual(result['questions'],1)
        data=politics.atlas(self.pp,'2026-12-shengkao');m=data['materials'][0];q=data['questions'][0]
        self.assertIn('在主产区布局产能',m['original'])
        self.assertEqual(m['kind'],'重大会议')
        self.assertEqual(q['answer'],'AB')
        self.assertIn('自编解析',q['analysis'])
        self.assertEqual(m['questions'],[q['id']])
        self.assertEqual(q['material'],m['id'])
        politics.set_progress(self.pp,{'exam':'2026-12-shengkao','field':'status','id':m['id'],'value':'done'})
        politics.set_progress(self.pp,{'exam':'2026-12-shengkao','field':'attempts','id':q['id'],'value':{'choice':'BA'}})
        self.assertEqual(politics.progress(self.pp,'2026-12-shengkao')['attempts'][str(q['id'])]['choice'],'AB')
        self.assertTrue(self.upload(p)['duplicate'])
        self.assertEqual(len(politics.atlas(self.pp,'2026-12-shengkao')['materials']),1)
        self.assertEqual(politics.progress(self.pp,'2026-12-shengkao')['status'][m['id']],'done')
        self.assertEqual(len(politics.atlas(self.pp)['materials']),1)
        self.assertEqual((self.pp.train/'时政知识地图/内容.json').read_bytes(),before)
        self.assertEqual((self.pp.vault/m['pdf']).read_bytes(),p.read_bytes())
        self.upload(p,'2027-03-shengkao')
        self.assertEqual(politics.progress(self.pp,'2027-03-shengkao')['status'],{})
        self.assertNotEqual(politics.identity(politics.source(self.pp,{'source':'atlas','exam':'2026-12-shengkao','material':m['id']})),politics.identity(politics.source(self.pp,{'source':'atlas','exam':'2027-03-shengkao','material':m['id']})))

    @unittest.skipIf(fitz is None,'需要已有PDF组件')
    def test_multiple_sources_keep_ambiguous_questions_and_no_fake_answer(self):
        p=self.vault/'自编两份文件.pdf'
        make_pdf(p,[[(1,'一、自编经济会议'),(1,'自编经济会议讨论经济发展。'),(1,'二、自编农业文件'),(1,'自编农业文件讨论粮食安全。'),(1,'配套练习'),(1,'1.（单选）本讲义中的自编政策对象是？'),(1,'A.甲'),(1,'B.乙'),(1,'C.丙'),(1,'D.丁')]])
        result=self.upload(p)
        self.assertEqual(result['unanswered'],1)
        self.assertEqual(result['whole_document_questions'],1)
        self.assertEqual(result['counts']['total'],2)
        data=politics.atlas(self.pp,'2026-12-shengkao');q=data['questions'][0]
        helper=next(m for m in data['materials'] if m['id']==q['material'])
        self.assertEqual(helper['kind'],'配套练习')
        self.assertIn('自编经济会议讨论',helper['original'])
        self.assertIn('自编农业文件讨论',helper['original'])
        with self.assertRaises(politics.PoliticsError):
            politics.set_progress(self.pp,{'exam':'2026-12-shengkao','field':'attempts','id':q['id'],'value':{'choice':'A'}})

    @unittest.skipIf(fitz is None,'需要已有PDF组件')
    def test_known_topic_pdf_has_linked_questions(self):
        p=self.vault/'自编专题.pdf';make_pdf(p,TOPIC)
        result=self.upload(p)
        data=politics.atlas(self.pp,'2026-12-shengkao')
        self.assertEqual(result['questions'],1)
        self.assertEqual(data['questions'][0]['answer'],'A')
        self.assertIn('国内生产总值',data['materials'][0]['original'])
        self.assertEqual(data['materials'][0]['questions'],[data['questions'][0]['id']])

    @unittest.skipIf(fitz is None,'需要已有PDF组件')
    def test_same_source_new_question_uses_links_and_keeps_base_progress(self):
        p=self.vault/'同正文补题.pdf'
        make_pdf(p,[[(1,'一、自编补充文件'),(1,self.base['materials'][0]['original']),
                    (1,'配套练习'),(1,'2.（单选）新加的自编题应选什么？'),(1,'A.甲'),(1,'B.乙'),
                    (1,'C.丙'),(1,'D.丁'),(1,'参考答案'),(1,'2.【答案】B。解析：自编新增解析。')]])
        politics.set_progress(self.pp,{'field':'status','id':'m1','value':'done'})
        original=(self.pp.train/'时政知识地图/内容.json').read_bytes()
        result=self.upload(p,politics.DEFAULT_EXAM)
        self.assertEqual(result['added'],0)
        self.assertEqual(result['questions'],1)
        data=politics.atlas(self.pp)
        self.assertEqual(len(data['materials']),1)
        self.assertEqual(data['materials'][0]['questions'],[1,2])
        self.assertEqual(data['questions'][1]['material'],'m1')
        self.assertEqual(politics.progress(self.pp)['status']['m1'],'done')
        self.assertEqual((self.pp.train/'时政知识地图/内容.json').read_bytes(),original)

    @unittest.skipIf(fitz is None,'需要已有PDF组件')
    def test_scan_and_invalid_pdf_do_not_change_content(self):
        p=self.vault/'扫描.pdf'
        with fitz.open() as doc:
            doc.new_page();doc.save(p)
        with self.assertRaisesRegex(politics.PoliticsError,'OCR'):
            self.upload(p)
        with self.assertRaises(politics.PoliticsError):
            politics_import.import_pdf(self.pp,{'data':'notPDF'})
        self.assertFalse((politics.exam_folder(self.pp,'2026-12-shengkao')/'补充.json').exists())
