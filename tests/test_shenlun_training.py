"""主题分类只保存索引，保留题目、草稿和评分输入。全部使用自编题。"""
import json
import unittest
import test_shenlun_complete as fixture
from rpg import api, shenlun_bank as bank, shenlun_training as training

class TrainingTest(unittest.TestCase):
    setUp=fixture.CompleteTest.setUp
    tearDown=fixture.CompleteTest.tearDown

    def test_material_scope_and_manual_override(self):
        bank.import_packages(self.p,{'title':'自编主题套卷','materials':[
            {'id':'1','text':'乡村发展农业，服务农村。'},
            {'id':'2','text':'科研人员研发人工智能技术。'}],
            'questions':[{'type':'归纳概括','text':'概括措施。','material_ids':['1']},
                         {'type':'综合分析','text':'分析作用。','material_ids':['2']}]})
        paper=next(p for p in bank.listing(self.p) if p['title']=='自编主题套卷')
        a,b=paper['questions']
        self.assertEqual(a['topics'],['农村']);self.assertEqual(b['topics'],['科技'])
        self.assertEqual(a['topic_scope'],'本题资料')
        original=bank.question(self.p,b['qid'],reveal=True)
        bank.answer_save(self.p,{'qid':b['qid'],'text':'自编草稿','revision':0})
        training.save(self.p,{'id':b['qid'],'topics':['基层治理','数字政务'],'revision':0})
        updated=next(p for p in bank.listing(self.p) if p['id']==paper['id'])['questions'][1]
        self.assertEqual(updated['topics'],['基层治理','数字政务'])
        self.assertEqual(updated['topic_scope'],'手动标注')
        self.assertEqual(original,bank.question(self.p,b['qid'],reveal=True))
        self.assertEqual(bank.answer_get(self.p,b['qid'])['text'],'自编草稿')
        training.save(self.p,{'id':b['qid'],'automatic':True,'revision':1})
        self.assertEqual(next(p for p in bank.listing(self.p) if p['id']==paper['id'])['questions'][1]['topics'],['科技'])

    def test_revision_validation_and_empty_labels(self):
        training.save(self.p,{'id':self.qid,'topics':[],'revision':0})
        self.assertEqual(bank.listing(self.p)[0]['questions'][0]['topics'],['待标注'])
        for body in [{'id':self.qid,'topics':['科技'],'revision':0},
                     {'id':'missing','topics':['科技'],'revision':1},
                     {'id':self.qid,'topics':['x']*9,'revision':1},
                     {'id':self.qid,'topics':['坏\n标签'],'revision':1},
                     {'id':self.qid,'topics':[{}],'revision':1}]:
            with self.assertRaises(bank.BankError):training.save(self.p,body)
        self.assertEqual(training.read(self.p)['revision'],1)
        with self.assertRaises(api.ApiError):api.shenlun_topics({'save':True,'id':self.qid,'topics':[],'revision':0})

    def test_api_and_corrupt_metadata(self):
        self.assertIn('农村',api.shenlun_papers({})['topics'])
        self.assertEqual(api.shenlun_topics({})['labels'],{})
        training.path(self.p).write_text(json.dumps({'schema':1,'revision':0,'labels':{'x':'bad'}}),encoding='utf-8')
        with self.assertRaises(bank.BankError):bank.listing(self.p)

if __name__=='__main__':unittest.main()
