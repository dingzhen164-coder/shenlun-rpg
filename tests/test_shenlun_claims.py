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

class UnclaimTest(unittest.TestCase):
    """2026-11-11：已领取的题可以移出目录；草稿和批改保留，不会被“已有作答自动收录”拉回，重新领取接着用。"""
    setUp=fixture.CompleteTest.setUp
    tearDown=fixture.CompleteTest.tearDown

    def test_unclaim_keeps_draft_and_reclaim_restores(self):
        claims.claim(self.p,{'qids':[self.qid]})
        bank.answer_save(self.p,{'qid':self.qid,'text':'自编作答','revision':0})
        draft=bank.answer_get(self.p,self.qid)
        r=api.shenlun_claims({'unclaim':True,'qids':[self.qid]})
        self.assertEqual(r['count'],0)
        self.assertEqual(claims.listing(self.p)['items'],[])               # 有草稿也不被自动收回
        self.assertEqual(claims.read(self.p)['removed'],[self.qid])
        self.assertEqual(bank.answer_get(self.p,self.qid)['text'],draft['text'])   # 草稿原样保留
        self.assertEqual(claims.claim(self.p,{'qids':[self.qid]})['added'],1)
        self.assertEqual(claims.read(self.p)['removed'],[])
        item=claims.listing(self.p)['items'][0]
        self.assertEqual((item['qid'],item['status']),(self.qid,'待批改'))   # 重新领取：接着用原草稿

    def test_unclaim_validation_and_old_file_compatible(self):
        old=claims.path(self.p)
        bank._write(old,{'schema':1,'qids':[self.qid]})                      # 旧格式没有 removed
        self.assertEqual(claims.listing(self.p)['items'][0]['qid'],self.qid)
        before=old.read_bytes()
        for ids in [[],['../bad'],[self.qid]*101]:
            with self.assertRaises(bank.BankError):claims.unclaim(self.p,{'qids':ids})
        self.assertEqual(before,old.read_bytes())
