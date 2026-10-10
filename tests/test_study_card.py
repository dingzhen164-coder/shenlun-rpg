"""备考日期、红格草稿/确认、计时防重复和忠实OCR；隔离假库，不用真实手写或AI。"""
import base64
import copy
import datetime as dt
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from rpg import api, shenlun_bank as bank, shenlun_handwriting as hw, study_schedule as schedule, config
import test_shenlun_complete as fixture
ANSWER=fixture.ANSWER

CARD={'pages':[{'strokes':[{'points':[[30,70],[50,80]],'erase':False,'width':3}]}]}

class StudyCardTest(unittest.TestCase):
    setUp=fixture.CompleteTest.setUp
    tearDown=fixture.CompleteTest.tearDown
    fake=fixture.CompleteTest.fake
    def save(self,**kw):
        d=bank.answer_get(self.p,self.qid)
        return bank.answer_save(self.p,dict(qid=self.qid,text=ANSWER,revision=d['revision'],**kw))
    def test_dates_defaults_and_real_span_preserve_xp(self):
        for subject,expected in [('行测','2026-09-29'),('申论','2026-10-10')]:
            g=SimpleNamespace(state={'xp':1234},rules=config.Rules(),subject=subject,today=dt.date(2026,10,10),t='2026-10-10')
            self.assertEqual(schedule.install(g)['start'],expected)
            self.assertEqual(schedule.save(g,{'start':'2026-10-01','exam':'2026-10-11'})['ideal_total'],3000)
            self.assertEqual(g.rules.date('目标日'),dt.date(2026,10,11));self.assertEqual(g.state['xp'],1234)
            with self.assertRaises(ValueError):schedule.save(g,{'start':'2026-10-11','exam':'2026-11-01'})
            with self.assertRaises(ValueError):schedule.save(g,{'start':'2026-10-10','exam':'2026-10-09'})
            g.today=dt.date(2026,10,12);g.t='2026-10-12';self.assertEqual(schedule.install(g)['start'],'2026-10-01')
        with api.open_game() as g:
            xp=g.state['xp'];schedule.save(g,{'start':(g.today-dt.timedelta(days=10)).isoformat(),'exam':g.today.isoformat()})
            self.assertEqual(g.ideal_total(),3000);self.assertEqual(g.state['xp'],xp)
    def test_card_revision_confirmation_and_report_snapshot(self):
        d=self.save(card=CARD)
        body={'qid':self.qid,'answer':ANSWER,'revision':d['revision'],'submission_id':'f'*32}
        with patch.object(api.ai,'chat_json',self.fake):
            with self.assertRaisesRegex(api.ApiError,'核对'):api.shenlun_comprehensive(body)
            self.assertEqual(self.calls,[])
            d=self.save(card=CARD,confirm_handwriting=True);body['revision']=d['revision']
            r=api.shenlun_comprehensive(body)
        self.assertEqual(r['answer_card'],CARD);self.assertEqual(r['answer_seconds'],0)
        history=api.shenlun_history({'qid':self.qid})['history'];self.assertEqual(history[0]['result']['answer_card'],CARD)
        changed=copy.deepcopy(CARD);changed['pages'][0]['strokes'][0]['points'].append([70,80]);d=self.save(card=changed)
        self.assertEqual(d['confirmed_card_hash'],'')
        with self.assertRaises(bank.BankError):bank.answer_save(self.p,{'qid':self.qid,'text':'旧稿','revision':0,'card':CARD})
    def test_card_bounds_and_clock_pause_unique_session(self):
        bad=copy.deepcopy(CARD);bad['pages'][0]['strokes'][0]['points'][0][0]=9999
        with self.assertRaises(bank.BankError):self.save(card=bad)
        session='a'*32
        def tick(t,active=True,s=session):
            with patch.object(hw.time,'time',return_value=t):return hw.clock(self.p,{'qid':self.qid,'session':s,'active':active})
        self.assertEqual(tick(100)['seconds'],0)
        self.assertEqual(tick(110)['seconds'],10)
        with self.assertRaises(bank.BankError):tick(111,s='b'*32)
        self.assertEqual(tick(115,False)['seconds'],15)
        self.assertEqual(tick(500)['seconds'],15)
        self.assertEqual(tick(510)['seconds'],25)
        self.save(card=CARD);self.assertEqual(bank.answer_get(self.p,self.qid)['seconds'],25)
        self.assertEqual(tick(999)['seconds'],25)
    def test_ocr_transcription_and_stale_result(self):
        d=self.save(card=CARD)
        png=b'\x89PNG\r\n\x1a\n'+b'\0'*8+(1040).to_bytes(4,'big')+(560).to_bytes(4,'big')
        body={'qid':self.qid,'revision':d['revision'],'images':['data:image/png;base64,'+base64.b64encode(png).decode()]}
        with patch.object(hw.ai,'vision_available',return_value=False),patch.object(hw.report,'ocr',return_value='原句，不扩写。'):
            r=hw.recognize(self.p,body)
        self.assertEqual(r['text'],'原句，不扩写。');self.assertEqual(bank.answer_get(self.p,self.qid)['text'],ANSWER)
        def edited(_):self.save(card=CARD);return '旧识别'
        with patch.object(hw.ai,'vision_available',return_value=False),patch.object(hw.report,'ocr',side_effect=edited):
            with self.assertRaisesRegex(bank.BankError,'已修改'):hw.recognize(self.p,body)

if __name__=='__main__':unittest.main()
