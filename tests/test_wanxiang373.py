"""万象峰标红编辑不删批注，且与PDF消化清单独立。只用临时库和自编材料。"""
import os
import unittest
from unittest.mock import patch

from rpg import api, politics, politics_reading as reading
from tests import test_wanxiang372 as fixtures


def setUpModule():
    os.environ['SHENLUN_SUBJECT'] = '行测'


def tearDownModule():
    os.environ.pop('SHENLUN_SUBJECT', None)


@unittest.skipIf(fixtures.fixtures.fitz is None, '缺PDF组件')
class ReadingTests(unittest.TestCase):
    setUp, tearDown = fixtures.JournalTests.setUp, fixtures.JournalTests.tearDown
    call, upload = fixtures.JournalTests.call, fixtures.JournalTests.upload

    def current(self, **extra):
        return api.ROUTES[('POST','/api/politics/highlights')](dict(source='atlas',material='m1',**extra))

    def anchor(self):
        with api.open_game(save=False) as g:
            text=politics.source(g.paths,dict(source='atlas',material='m1'))['text']
        at=text.index('主产区')
        return dict(paragraph=text,start=at,end=at+3,word='主产区',block_offset=0)

    def test_only_exact_occurrence_is_highlighted_without_writing_source(self):
        with api.open_game(save=False) as g:
            file=g.paths.train/'时政知识地图/内容.json';before=file.read_bytes()
        result=self.current()
        self.assertEqual(result['ranges'],[[8,11]])
        self.assertNotIn('items',result,'标红接口不生成消化挖空')
        self.assertEqual(file.read_bytes(),before)

    def test_cancel_keeps_note_progress_xp_and_can_restore(self):
        body=self.anchor()
        with api.open_game() as g:
            src=politics.source(g.paths,dict(source='atlas',material='m1'))
            file=g.paths.train/'词义批注'/(politics.identity(src)+'.json')
            note=dict(body,key='old',version=4,explanation={'meaning':'自编解释'})
            politics.atomic_json(file,{'old':note});old_file=file.read_bytes();old_xp=g.state['xp']
            politics.set_progress(g.paths,dict(field='status',id='m1',value='done'))
        # 取消与恢复不调用AI；历史状态不删，恢复原重点时仍能读取。
        with patch('rpg.politics.ai.chat',side_effect=AssertionError('禁止调用AI')):
            self.assertEqual(self.current(**body,enabled=False)['ranges'],[])
            self.assertEqual(file.read_bytes(),old_file)
            self.assertEqual(len(self.current(**body,enabled=True)['ranges']),1)
        with api.open_game(save=False) as g:
            self.assertEqual(g.state['xp'],old_xp)
            self.assertEqual(politics.progress(g.paths)['status']['m1'],'done')

    def test_cancelled_note_stays_cached_without_creating_cloze(self):
        body=self.anchor()
        with api.open_game(save=False) as g:
            src=politics.source(g.paths,dict(source='atlas',material='m1'))
            anchor=politics.validate_anchor(src,body);key=politics.digest(anchor)
            file=g.paths.train/'词义批注'/(politics.identity(src)+'.json')
            note=dict(anchor,key=key,version=4,explanation={'meaning':'自编解释'})
            politics.atomic_json(file,{key:note})
            self.current(**body,enabled=False)
            with patch('rpg.politics.ai.chat',side_effect=AssertionError('不重新生成')):
                self.assertTrue(politics.explain(g.paths,src,body)['cached'])
            self.assertEqual(self.current()['ranges'],[])

    def test_utf32_repeated_paragraphs_and_partial_removal(self):
        text='😀支持甲方。\n\n😀支持甲方。'
        src={'id':['atlas','self-written'],'text':text,'emphasis':[[1,5],[7,11]]}
        with api.open_game(save=False) as g:
            result=reading.mark(g.paths,src,dict(paragraph='😀支持甲方。',word='甲方',start=3,end=5,block_offset=6,enabled=False))
            self.assertEqual(result['ranges'],[[1,5],[7,9]])
            self.assertNotIn('items',result)

    def test_empty_default_practice_keeps_builtin_and_imported_progress(self):
        with api.open_game(save=False) as g:
            self.assertEqual(politics.atlas(g.paths)['practice_question_ids'],[])
            politics.set_progress(g.paths,dict(field='attempts',id=1,value={'choice':'A'}))
        self.upload('sprint-quiz',self.month)
        with api.open_game(save=False) as g:
            data=politics.atlas(g.paths)
            self.assertTrue(data['practice_question_ids'])
            self.assertNotIn(1,data['practice_question_ids'])
            self.assertTrue(any(q['id']==1 for q in data['questions']))
            self.assertEqual(politics.progress(g.paths)['attempts']['1']['choice'],'A')

    def test_journal_pdf_blanks_do_not_change_when_highlights_change(self):
        issue=self.upload('month',self.month);body=dict(kind='month',id=issue['id'])
        current=self.call('get',body);item=current['data']['digest']['items'][0]
        self.call('mark',dict(body,cloze=item['legacy'],ok=0))
        self.assertEqual(self.call('cards',body)['added'],1)
        with api.open_game(save=False) as g:
            src=politics.source(g.paths,dict(source='wanxiang_journal',news=0,**body))
            text=src['text'];word=item['a'];at=text.index(word)
            reading.mark(g.paths,src,dict(paragraph=text,start=at,end=at+len(word),word=word,enabled=False))
        new=self.call('get',body)
        self.assertEqual(new['data']['digest']['items'],current['data']['digest']['items'])
        self.assertIn(item['legacy'],new['progress']['cloze'],'取消标红不删除清单进度')
        with api.open_game(save=False) as g:
            word='正式通航';at=text.index(word)
            reading.mark(g.paths,src,dict(paragraph=text,start=at,end=at+len(word),word=word,enabled=True))
        current=self.call('get',body)
        self.assertFalse(any(x['a']=='正式通航' for x in current['data']['digest']['items']))
        self.assertEqual(self.call('cards',body)['added'],0,'标红不改变PDF空位或重复刻旧卡')

    def test_invalid_anchor_and_subject_cannot_write_marks(self):
        body=self.anchor()
        for change in [dict(word='伪造词'),dict(start=-1),dict(block_offset=999),dict(enabled='false')]:
            payload=dict(body,enabled=False);payload.update(change)
            with self.assertRaises(api.ApiError):self.current(**payload)
        with patch.dict(os.environ,{'SHENLUN_SUBJECT':'申论'}):
            with self.assertRaises(api.ApiError):self.current()

    def test_marks_are_separated_by_exam(self):
        self.current(**self.anchor(),enabled=False)
        with api.open_game(save=False) as g:
            src=politics.material_source(politics.atlas(g.paths)['materials'][0],'2026-12-shengkao')
            self.assertTrue(reading.reading(g.paths,src)['ranges'])


if __name__=='__main__':unittest.main()
