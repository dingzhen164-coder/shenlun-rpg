"""3.7.4：已导入时政文件的列出与批量删除；自编PDF/临时库，不访问真实资料、不调用AI。"""
import base64
import os
import unittest

from rpg import api, politics, politics_manage
from tests import test_wanxiang372 as fixtures
from tests.test_tianji import make_pdf, fitz


def setUpModule():os.environ['SHENLUN_SUBJECT']='行测'
def tearDownModule():os.environ.pop('SHENLUN_SUBJECT',None)


@unittest.skipIf(fitz is None,'缺PDF组件')
class ManageTests(unittest.TestCase):
    setUp,tearDown=fixtures.JournalTests.setUp,fixtures.JournalTests.tearDown
    call,upload=fixtures.JournalTests.call,fixtures.JournalTests.upload

    def listing(self):return api.ROUTES[('POST','/api/wanxiang/import/list')]({})
    def delete(self,ids):return api.ROUTES[('POST','/api/wanxiang/import/delete')]({'ids':ids})
    def ids(self):return {i['id']:i for gr in self.listing()['groups'] for i in gr['items']}

    def digest_pdf(self):
        file=self.vault/'自编清单.pdf';make_pdf(file,[[(1,'1.在____布局产能。')]]);return file

    def test_lists_every_channel_and_rejects_unknown_or_empty_ids(self):
        self.upload('month',self.month);self.upload('sprint-study',self.month,exam='2026-12-shengkao');self.upload('digest',self.digest_pdf())
        groups={g['channel']:g for g in self.listing()['groups']}
        self.assertEqual(set(groups),{'month','sprint','digest'})
        self.assertIn('空',groups['digest']['items'][0]['detail'])
        for bad in ([],None,['../x'],['journal:month:不存在'],[1]):
            with self.assertRaises(api.ApiError):self.delete(bad)

    def test_batch_delete_backs_up_first_and_keeps_progress_and_other_imports(self):
        issue=self.upload('month',self.month);self.upload('digest',self.digest_pdf())
        api.ROUTES[('POST','/api/wanxiang/journal/mark')]({'kind':'month','id':issue['id'],'read':0})
        with api.open_game(save=False) as g:
            before=dict(g.state['wanxiang_journal']);train=g.paths.train;vault=g.paths.vault
        ids=sorted(self.ids());self.assertEqual(len(ids),2)
        result=self.delete(ids)
        self.assertEqual(result['deleted'],2);self.assertEqual(self.listing()['total'],0)
        recycle=vault/result['recycle']
        self.assertTrue(list(recycle.rglob('*.json')),'删除前先备份导入数据')
        self.assertTrue(list(recycle.rglob('*.pdf')),'原PDF也在回收文件夹里')
        with api.open_game(save=False) as g:self.assertEqual(g.state['wanxiang_journal'],before,'学习进度保留')
        self.assertFalse(list((train/'时政消化').glob('*.json')))
        self.assertFalse(list((train/'时政消化/原文').glob('*.pdf')) if (train/'时政消化/原文').exists() else [])

    def test_sprint_delete_removes_only_that_pdf_and_keeps_shared_original(self):
        self.upload('sprint-study',self.month,exam='2026-12-shengkao');self.upload('sprint-study',self.month,exam='2027-03-shengkao')
        items=[i for i in self.ids().values() if i['label']]
        self.assertEqual(len(items),2,'两个考试各导入一次')
        first=sorted(self.ids())[0]
        with api.open_game(save=False) as g:
            pdfs=list((g.paths.train/'时政知识地图/原文').glob('*.pdf'));self.assertEqual(len(pdfs),1)
        self.delete([first])
        self.assertEqual(len(self.ids()),1)
        self.assertTrue(pdfs[0].exists(),'另一个考试还在用这份原PDF：不能删')
        self.delete(list(self.ids()))
        self.assertFalse(pdfs[0].exists())
        with api.open_game(save=False) as g:
            for exam in ('2026-12-shengkao','2027-03-shengkao'):
                data=politics.atlas(g.paths,exam)
                self.assertFalse([m for m in data['materials'] if m.get('pdf')],'导入的资料已清掉，内置资料保留')

    def test_delete_then_reimport_restores_the_same_document_progress(self):
        issue=self.upload('month',self.month)
        api.ROUTES[('POST','/api/wanxiang/journal/mark')]({'kind':'month','id':issue['id'],'read':0})
        self.delete(list(self.ids()))
        again=self.upload('month',self.month)
        self.assertEqual(again['id'],issue['id'])
        self.assertEqual(api.ROUTES[('POST','/api/wanxiang/journal/get')]({'kind':'month','id':issue['id']})['stat']['read'],1)


if __name__ == '__main__':
    unittest.main()
