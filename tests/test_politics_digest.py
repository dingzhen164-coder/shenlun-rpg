"""独立清单PDF与配套原文匹配：自编PDF/临时库，不访问真实资料，不调用AI。"""
import base64
import copy
import os
import unittest
from unittest.mock import patch

from rpg import api, politics, politics_digest as digest
from tests import test_wanxiang372 as fixtures
from tests.test_tianji import make_pdf, fitz


def setUpModule():os.environ['SHENLUN_SUBJECT']='行测'
def tearDownModule():os.environ.pop('SHENLUN_SUBJECT',None)


@unittest.skipIf(fitz is None,'缺PDF组件')
class DigestTests(unittest.TestCase):
    setUp,tearDown=fixtures.JournalTests.setUp,fixtures.JournalTests.tearDown
    call,upload=fixtures.JournalTests.call,fixtures.JournalTests.upload
    target={'source':'atlas','exam':'2026-10-guokao','material':'m1'}

    def pdf(self,lines,name='自编消化.pdf'):
        file=self.vault/name;make_pdf(file,[[(1,x) for x in lines]]);return file

    def send(self,file,target=None):
        return self.upload('digest',file,target=target or self.target)

    def get(self,target=None):
        return api.ROUTES[('POST','/api/wanxiang/digest/get')]({'target':target or self.target})

    def mark(self,item,value='remember',target=None):
        return api.ROUTES[('POST','/api/wanxiang/digest/mark')]({'target':target or self.target,'id':item['id'],'value':value})

    def test_import_real_pdf_match_and_pending_without_ai_or_source_edits(self):
        file=self.pdf(['消化清单','1.在________布局产能。','2.自编未知政策提出________要求。'])
        with api.open_game(save=False) as g:
            source=g.paths.train/'时政知识地图/内容.json';before=source.read_bytes();xp=g.state['xp']
        with patch('rpg.politics.ai.chat',side_effect=AssertionError('不得猜答案')):
            result=self.send(file);data=self.get()
        self.assertEqual((result['blanks'],result['ready'],result['pending']),(2,1,1))
        self.assertEqual([p['a'] for p in data['items']],['主产区',None])
        self.assertEqual(data['items'][1]['status'],'pending')
        with self.assertRaises(api.ApiError):self.mark(data['items'][1])
        self.assertEqual(source.read_bytes(),before)
        with api.open_game(save=False) as g:self.assertEqual(g.state['xp'],xp)

    def test_explicit_pdf_answers_take_priority_and_multiple_blanks(self):
        file=self.pdf(['1.在____布局____。','参考答案','1.自编甲方、乙产业'])
        self.send(file);data=self.get()
        self.assertEqual([p['a'] for p in data['items']],['自编甲方','乙产业'])
        self.assertTrue(all(p['status']=='provided' for p in data['items']))

    def test_target_catalog_contains_materials_and_periodicals(self):
        issue=self.upload('month',self.month)
        entries=api.ROUTES[('POST','/api/wanxiang/digest/targets')]({})['targets']
        self.assertIn(self.target,[e['target'] for e in entries])
        self.assertIn({'source':'wanxiang_journal','kind':'month','id':issue['id']},[e['target'] for e in entries])

    def test_titled_answer_section_is_not_mistaken_for_cover(self):
        self.send(self.pdf(['1.在____布局产能。','消化清单·答案与解析','1.自编答案']))
        self.assertEqual(self.get()['items'][0]['a'],'自编答案')

    def test_ambiguous_context_does_not_pick_first_or_greedy_split(self):
        self.assertEqual(digest.match_answers('支持____发展产业。',['支持甲方发展产业。支持乙方发展产业。']),[None])
        self.assertEqual(digest.match_answers('支持____和____发展。',['支持甲和乙和丙发展。']),[None,None])
        self.assertEqual(digest.match_answers('支持____发展产业。',['支持甲方发展产业。支持甲方发展产业。']),['甲方'])
        self.assertEqual(digest.match_answers('____发展产业。',['支持甲方发展产业。']),[None])

    def test_duplicate_import_keeps_progress_and_does_not_repeat_rows(self):
        file=self.pdf(['1.在____布局产能。'])
        self.send(file);item=self.get()['items'][0];self.mark(item)
        self.assertTrue(self.send(file)['duplicate'])
        data=self.get();self.assertEqual(len(data['items']),1)
        self.assertEqual(data['progress'][item['id']],'remember')

    def test_highlight_cancel_does_not_remove_pdf_blank_or_progress(self):
        self.send(self.pdf(['1.在____布局产能。']));item=self.get()['items'][0];self.mark(item)
        with api.open_game(save=False) as g:text=politics.source(g.paths,dict(source='atlas',material='m1'))['text']
        at=text.index('主产区')
        api.ROUTES[('POST','/api/politics/highlights')]({'source':'atlas','material':'m1','paragraph':text,'word':'主产区','start':at,'end':at+3,'block_offset':0,'enabled':False})
        data=self.get();self.assertEqual(data['items'][0]['id'],item['id']);self.assertEqual(data['progress'][item['id']],'remember')

    def test_source_answer_change_does_not_reuse_old_memory(self):
        file=self.pdf(['1.在____布局产能。']);self.send(file)
        old=self.get()['items'][0];self.mark(old)
        with api.open_game(save=False) as g:
            path=g.paths.train/'时政知识地图/内容.json';data=politics.read_json(path,{})
            data['materials'][0]['original']='在自编新区布局产能。';politics.atomic_json(path,data)
        new=self.get();self.assertEqual(new['items'][0]['a'],'自编新区')
        self.assertNotEqual(new['items'][0]['id'],old['id']);self.assertIsNone(new['progress'][new['items'][0]['id']])

    def test_target_and_exam_isolation_and_whole_pdf_bundle(self):
        self.upload('sprint-study',self.month,exam='2026-12-shengkao')
        with api.open_game(save=False) as g:
            data=politics.atlas(g.paths,'2026-12-shengkao');m=data['materials'][0]
            bundle={'source':'atlas','exam':'2026-12-shengkao','bundle':m['pdf'].split('/')[-1][:-4]}
        self.send(self.pdf(['1.平陆运河是广西境内沟通____流域西江与北部湾的运河，是西部陆海新通道骨干工程。']),bundle)
        target={'source':'atlas','exam':'2026-12-shengkao','material':m['id']}
        self.assertTrue(self.get(target)['documents'])
        self.assertFalse(self.get()['documents'])
        with self.assertRaises(api.ApiError):self.get(dict(self.target,exam='2027-03-shengkao'))

    def test_periodical_target_keeps_old_embedded_pdf_cloze_and_import_priority(self):
        issue=self.upload('month',self.month);target={'source':'wanxiang_journal','kind':'month','id':issue['id']}
        old=self.get(target);self.assertTrue(old['counts']['ready'])
        self.send(self.pdf(['1.平陆运河是广西境内沟通____流域西江与北部湾的运河，是西部陆海新通道骨干工程。']),target)
        data=self.get(target);self.assertEqual(data['counts']['blanks'],1)
        self.assertEqual(data['items'][0]['a'],'珠江');self.mark(data['items'][0],target=target)
        self.assertEqual(api.ROUTES[('POST','/api/wanxiang/journal/get')]({'kind':'month','id':issue['id']})['stat']['seen'],1)

    def test_empty_parentheses_and_vector_blank_not_text_underline(self):
        self.send(self.pdf(['1.在（    ）布局产能。']))
        self.assertEqual(self.get()['items'][0]['a'],'主产区')
        doc=fitz.open();p=doc.new_page();p.insert_text((90,110),'1.在',fontname='china-s',fontsize=10.5)
        p.insert_text((220,110),'布局产能。',fontname='china-s',fontsize=10.5);p.draw_line((125,112),(208,112))
        rows=digest.parse_pdf(doc.tobytes());doc.close()
        self.assertEqual(len(rows),1);self.assertEqual(digest.match_answers(rows[0]['text'],['在主产区布局产能。']),['主产区'])

    def test_missing_target_invalid_pdf_and_no_blank_are_rejected(self):
        for body in [{'channel':'digest','data':'bad'}, {'channel':'digest','target':dict(self.target,material='../x'),'data':'bad'}]:
            with self.assertRaises(api.ApiError):api.ROUTES[('POST','/api/wanxiang/import')](body)
        with self.assertRaises(api.ApiError):self.send(self.pdf(['没有空位的自编文字。']))
        with patch.dict(os.environ,{'SHENLUN_SUBJECT':'申论'}):
            with self.assertRaises(api.ApiError):self.get()
