"""领取目录持久、幂等及真实草稿/批改状态；自编材料和假AI。"""
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import test_shenlun_complete as fixture
from rpg import api, ai, shenlun_bank as bank, shenlun_claims as claims

class ClaimsTest(unittest.TestCase):
    setUp=fixture.CompleteTest.setUp
    tearDown=fixture.CompleteTest.tearDown
    def item(self):return claims.listing(self.p)['items'][0]

    def test_persistent_duplicate_and_atomic_validation(self):
        original=bank.question(self.p,self.qid,reveal=True)
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:claims.claim(self.p,{'qids':[self.qid]}),range(2)))
        self.assertEqual(sum(r['added'] for r in results),1)
        self.assertEqual(claims.read(self.p)['qids'],[self.qid]);self.assertEqual(self.item()['status'],'未做')
        self.assertEqual(original,bank.question(self.p,self.qid,reveal=True))
        old=claims.path(self.p).read_bytes()
        for ids in [[],[self.qid,'slq-'+'0'*20],['../bad'],[self.qid]*101]:
            with self.assertRaises(bank.BankError):claims.claim(self.p,{'qids':ids})
        self.assertEqual(old,claims.path(self.p).read_bytes())
        with self.assertRaises(api.ApiError):api.shenlun_claims({'claim':True,'qids':['../bad']})

    def test_legacy_answer_migration_ignores_empty_drafts(self):
        bank.answer_save(self.p,{'qid':self.qid,'text':'','revision':0})
        self.assertEqual(claims.listing(self.p)['items'],[])
        bank.answer_save(self.p,{'qid':self.qid,'text':'自编作答','revision':1})
        self.assertEqual(self.item()['status'],'待批改');self.assertTrue(self.item()['answered'])
        self.assertEqual(claims.read(self.p)['qids'],[self.qid])
        self.assertEqual(claims.claim(self.p,{'qids':[self.qid]})['added'],0)

    def test_scores_match_current_answer_and_handwriting(self):
        with patch.object(ai,'chat_json',lambda *a,**k:fixture.CompleteTest.fake(self,*a,**k)):
            _,r=fixture.CompleteTest.submit(self,fixture.ANSWER,'a'*32)
        item=self.item();self.assertEqual((item['status'],item['score'],item['full']),('已批改',20,20))
        d=bank.answer_get(self.p,self.qid)
        # 阅读计时和材料批注不改变作答，仍是同一稿分数。
        bank.answer_save(self.p,{'qid':self.qid,'text':' '+fixture.ANSWER+' ','revision':d['revision']})
        self.assertEqual(self.item()['score'],20)
        d=bank.answer_get(self.p,self.qid)
        bank.answer_save(self.p,{'qid':self.qid,'text':'新的自编作答','revision':d['revision']})
        self.assertEqual((self.item()['status'],self.item()['score']),('待批改',None))
        d=bank.answer_get(self.p,self.qid)
        bank.answer_save(self.p,{'qid':self.qid,'text':fixture.ANSWER,'revision':d['revision'],'card':{'pages':[{'strokes':[{'points':[[10,10],[20,20]],'width':3,'erase':False}]}]}})
        self.assertEqual(self.item()['status'],'待批改')
        self.assertNotIn('references',self.item());self.assertNotIn('answer',self.item())

if __name__=='__main__':unittest.main()
