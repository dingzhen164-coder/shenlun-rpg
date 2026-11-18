"""完整真题闭环：自编材料、隔离库、假AI；验证证据、固定标准、草稿冲突和重复交卷。"""
from contextlib import closing
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rpg import api, ai, paths, shenlun_bank as bank, shenlun_review as review

PACKAGE={'title':'2026自编测试卷','region':'自编','materials':[{'id':'1','text':'社区走访居民，收集办事需求。部门共享资料，减少重复提交。'}], 'questions':[{'type':'贯彻执行','text':'写一份服务优化报告。（20分）不超过300字。','score':20,'limit':300,'references':[{'answer':'隐藏的机构参考答案'}]}]}
ANSWER='走访居民了解需求，推动部门共享资料。'

class CompleteTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent.parent.parent)
        self.root=Path(self.tmp.name); self.v=self.root/'库';(self.v/'copilot/skills/test').mkdir(parents=True)
        self.old=(paths.SETTINGS_DIR,paths.SETTINGS_FILE,paths.LEGACY_SETTINGS)
        self.env=patch.dict(os.environ,{'SHENLUN_SUBJECT':'申论'});self.env.start()
        paths.SETTINGS_DIR=self.root/'home';paths.SETTINGS_FILE=paths.SETTINGS_DIR/'settings.json';paths.LEGACY_SETTINGS=self.root/'无.json'
        paths.save_settings({'subject':'申论','vaults':{'申论':str(self.v)}})
        self.p=paths.Paths(self.v,'申论');self.p.ensure_train_dir();bank.import_packages(self.p,PACKAGE)
        self.qid=bank.listing(self.p)[0]['questions'][0]['qid'];self.calls=[]
    def tearDown(self):
        paths.SETTINGS_DIR,paths.SETTINGS_FILE,paths.LEGACY_SETTINGS=self.old;self.env.stop();self.tmp.cleanup()
    def fake(self,msgs,**kwargs):
        data=json.loads(msgs[1]['content']);self.calls.append(data)
        if 'answer' not in data:
            return {'task':'向服务对象报告优化措施','points':[{'name':'了解需求','material_quote':'社区走访居民，收集办事需求。'},{'name':'资料共享','material_quote':'部门共享资料，减少重复提交。'}]}
        answer=data['answer'];return {'points':[{'id':i+1,'hit':'full' if '共享' in answer or i==0 else 'none','quote':answer if '共享' in answer or i==0 else '', 'reason':'语义覆盖','suggestion':'结合措施写具体'} for i in range(len(data['standard']['points']))],'dimensions':[{'name':n,'level':4,'quote':answer,'reason':'任务完整','improvement':'保持'} for n in data['dimension_names']], 'checks':[{'name':'报告身份与目的','status':'通过','quote':answer,'reason':'题干没有强制落款'}], 'revisions':[{'quote':answer,'rewrite':'走访了解居民需求，推动资料共享，减少群众重复提交。','reason':'补上成效'}],'summary':'措施清晰，可进一步说明群众获得的便利。','lost':[]}
    def state(self):
        with api.open_game(save=False) as g:return copy.deepcopy(g.state)
    def submit(self,answer,sid):
        old=api.shenlun_answer({'qid':self.qid});d=api.shenlun_answer({'save':True,'qid':self.qid,'text':answer,'revision':old['revision']})
        body={'qid':self.qid,'answer':answer,'revision':d['revision'],'submission_id':sid}
        return body,api.shenlun_comprehensive(body)
    def test_closed_loop_rewrite_and_retry(self):
        with patch.object(ai,'chat_json',self.fake):
            body,r=self.submit('走访居民了解需求。','a'*32)
            self.assertEqual(r['total'],12)
            count=len(self.state()['grades']);xp=self.state()['xp'];calls=len(self.calls)
            self.assertEqual(api.shenlun_comprehensive(body)['record'],r['record'])
            self.assertEqual((len(self.state()['grades']),self.state()['xp'],len(self.calls)),(count,xp,calls))
            _,r2=self.submit(ANSWER,'b'*32)
        self.assertEqual(r2['total'],20);self.assertEqual(r2['comparison']['change'],8)
        self.assertEqual(r2['comparison']['improved'],['资料共享'])
        self.assertEqual(sum('answer' not in d for d in self.calls),1)
        self.assertNotIn('answer',self.calls[0]);self.assertEqual(r['standard_hash'],r2['standard_hash'])
        self.assertEqual(len(review.history(self.p,self.qid)),2)
        self.assertIn(ANSWER,(self.v/r2['review_file']).read_text(encoding='utf-8'))
    def test_calibrate_with_reference_answers_does_not_record(self):
        with api.open_game(save=False) as g:rules=g.rules
        before=copy.deepcopy(self.state());count=len(self.state()['grades'])
        out=review.calibrate(self.p,self.qid,rules,self.fake)
        self.assertTrue(out['results'] and 'rate' in out['results'][0])
        self.assertEqual(len(self.state()['grades']),count);self.assertEqual(self.state()['xp'],before['xp'])
        self.assertNotIn('answer',json.dumps(out,ensure_ascii=False).replace('answer_',''))  # 不回传参考答案原文
        self.assertEqual(review.calibration(self.p,self.qid,out['standard_hash'])['average_rate'],out['average_rate'])
        self.assertIsNone(review.calibration(self.p,self.qid,'0'*64))
        self.assertEqual(review.history(self.p,self.qid),[])
    def test_calibrate_needs_reference(self):
        paper=copy.deepcopy(PACKAGE);paper['title']='无参考答案卷';paper['questions'][0].pop('references',None)
        bank.import_packages(self.p,paper);qid=[q['qid'] for x in bank.listing(self.p) if x['title']=='无参考答案卷' for q in x['questions']][0]
        with api.open_game(save=False) as g:rules=g.rules
        with self.assertRaises(review.ReviewError):review.calibrate(self.p,qid,rules,self.fake)
    def test_hide_references_duplicate_and_validation_atomic(self):
        self.assertNotIn('references',api.shenlun_question({'qid':self.qid}))
        self.assertNotIn('隐藏的机构参考答案',json.dumps(api.shenlun_papers({}),ensure_ascii=False))
        self.assertEqual(bank.import_packages(self.p,PACKAGE)['skipped'],1)
        n=len(bank.papers(self.p));bad=dict(PACKAGE,title='第二套',questions=[{}])
        with self.assertRaises(bank.BankError):bank.import_packages(self.p,[dict(PACKAGE,title='第三套'),bad])
        self.assertEqual(len(bank.papers(self.p)),n)
    def test_stale_draft_and_grade_rejected(self):
        api.shenlun_answer({'save':True,'qid':self.qid,'text':ANSWER,'revision':0})
        with self.assertRaises(api.ApiError):api.shenlun_answer({'save':True,'qid':self.qid,'text':'旧稿','revision':0})
        with patch.object(ai,'chat_json',self.fake):
            with self.assertRaises(api.ApiError):api.shenlun_comprehensive({'qid':self.qid,'answer':'旧稿','revision':0,'submission_id':'c'*32})
        self.assertEqual(self.calls,[]);self.assertEqual(api.shenlun_answer({'qid':self.qid})['text'],ANSWER)
        with self.assertRaises(api.ApiError):api.shenlun_comprehensive({'qid':'../x','submission_id':'c'*32})
    def test_concurrent_drafts_only_one_revision_wins(self):
        from concurrent.futures import ThreadPoolExecutor
        def save(text):
            try:return bank.answer_save(self.p,{'qid':self.qid,'text':text,'revision':0})
            except bank.BankError:return None
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(save,['甲稿','乙稿']))
        self.assertEqual(sum(x is not None for x in results),1)
        self.assertEqual(bank.answer_get(self.p,self.qid)['revision'],1)
    def test_report_without_state_commit_recovers_once(self):
        with patch.object(ai,'chat_json',self.fake):
            original=self.state()
            body,r=self.submit(ANSWER,'e'*32)
            with api.open_game() as g:g.state.clear();g.state.update(original)
            calls=len(self.calls)
            recovered=api.shenlun_comprehensive(body)
            self.assertEqual(recovered['record'],r['record'])
            self.assertEqual(len(self.state()['grades']),1)
            api.shenlun_comprehensive(body)
            self.assertEqual(len(self.state()['grades']),1)
            self.assertEqual(len(self.calls),calls)

    def test_fabricated_evidence_never_scores(self):
        def bad(msgs,**kwargs):
            d=self.fake(msgs)
            if 'dimensions' in d:d['points'][0]['quote']='答案中根本没有的句子'
            return d
        n=len(self.state()['grades'])
        with patch.object(ai,'chat_json',bad):
            with self.assertRaises(api.ApiError):self.submit(ANSWER,'d'*32)
        self.assertEqual(len(self.state()['grades']),n);self.assertEqual(len(review.history(self.p,self.qid)),0)
        self.assertEqual(len(self.calls),3)
    def test_missing_material_or_score_block_review(self):
        raw=dict(PACKAGE,title='缺材料',materials=[]);bank.import_packages(self.p,raw)
        q=next(p['questions'][0] for p in bank.listing(self.p) if p['title']=='缺材料');self.assertFalse(q['complete'])
        with patch.object(ai,'chat_json',self.fake):
            with api.open_game(save=False) as g:
                with self.assertRaises(review.ReviewError):review.grade(self.p,q['qid'],ANSWER,g.rules,self.fake)
        self.assertEqual(self.calls,[])
    def test_essay_program_weights_and_fixed_standard(self):
        raw=copy.deepcopy(PACKAGE);raw['title']='自编作文';raw['questions'][0].update(type='大作文',score=40)
        bank.import_packages(self.p,raw);qid=next(p['questions'][0]['qid'] for p in bank.listing(self.p) if p['title']=='自编作文')
        with api.open_game(save=False) as g:q,r=review.grade(self.p,qid,ANSWER,g.rules,self.fake)
        self.assertEqual(r['total'],40);self.assertEqual(r['points'],[]);self.assertEqual(len(r['dimensions']),4)
        f=bank.folder(self.p)/(q['paper_id']+'.json');d=json.loads(f.read_text(encoding='utf-8'));d['materials'][0]['text']+='原文变化';bank._write(f,d)
        with api.open_game(save=False) as g:
            with self.assertRaises(review.ReviewError):review.grade(self.p,qid,ANSWER,g.rules,self.fake)
    def test_source_sqlite_material_join_and_idempotence(self):
        import sqlite3
        db=self.root/'tiny.db';md=self.root/'materials.db'
        with closing(sqlite3.connect(db)) as c:
            c.execute('CREATE TABLE papers(id,subjectName,name,category)');c.execute('INSERT INTO papers VALUES(1,?,?,?)',('公务员·申论','2025自编卷','国考'))
            c.execute('CREATE TABLE questions(id,questionId,paperId,content,contentHtml,answer,analysis)')
            c.execute('INSERT INTO questions VALUES(1,12,1,?,?,?,?)',('写一份报告。（本题20分，250字以内）','','','自编解析'));c.commit()
        with closing(sqlite3.connect(md)) as c:
            c.execute('CREATE TABLE materials(paperId,idx,title,text)');c.execute('INSERT INTO materials VALUES(1,1,?,?)',('材料1','社区⾛访居⺠。'));c.commit()
        result=bank.import_sqlite(self.p,db,md);self.assertEqual(result['added'],1)
        q=next(p['questions'][0] for p in bank.listing(self.p) if p['title']=='2025自编卷')
        self.assertEqual((q['complete'],q['total'],q['words']),(True,20,250))
        self.assertEqual(bank.question(self.p,q['qid'])['materials'][0]['text'],'社区走访居民。')
        self.assertEqual(bank.import_sqlite(self.p,db,md)['skipped'],1)

    def test_combined_revision_budget_and_ambiguity(self):
        rows=[{'quote':'甲甲','rewrite':'甲甲甲甲'},{'quote':'乙乙','rewrite':'乙乙乙乙'}]
        with self.assertRaisesRegex(review.ReviewError,'超过6字'):
            review.revision_plan(rows,'甲甲乙乙',6)
        self.assertEqual(review.revision_plan(rows,'甲甲乙乙',8),8)
        with self.assertRaisesRegex(review.ReviewError,'出现多次'):
            review.revision_plan([{'quote':'甲','rewrite':'乙'}],'甲甲',10)
        with self.assertRaisesRegex(review.ReviewError,'出现多次'):
            review.revision_plan([{'quote':'甲甲','rewrite':'乙'}],'甲甲甲',10)
        with self.assertRaisesRegex(review.ReviewError,'重叠'):
            review.revision_plan([{'quote':'甲乙','rewrite':'甲'},{'quote':'乙丙','rewrite':'丙'}],'甲乙丙',10)
        self.assertEqual(review.revision_plan([{'quote':'甲甲','rewrite':'甲'}],'甲甲乙乙',3),3)
        self.assertEqual(review.revision_plan([],'甲甲乙乙',3),4)

    def test_overlong_advice_retries_and_program_counts(self):
        def bounded(msgs,**kwargs):
            d=self.fake(msgs)
            if 'dimensions' in d:
                d['checks'].append({'name':'字数限制','status':'通过','quote':'','reason':'约1字'})
                d['revisions'][0]['rewrite']='甲'*301 if len(msgs)==2 else ANSWER
            return d
        with api.open_game(save=False) as g:q,r=review.grade(self.p,self.qid,ANSWER,g.rules,bounded)
        self.assertEqual(len(self.calls),3)
        self.assertEqual(r['revision_words'],len(ANSWER));self.assertTrue(r['revision_verified'])
        checks=[x for x in r['checks'] if '字数' in x['name']]
        self.assertEqual(len(checks),1);self.assertIn('程序计数%d字'%len(ANSWER),checks[0]['reason'])

    def test_old_standard_archived_only_after_success(self):
        with api.open_game(save=False) as g:
            q=bank.question(self.p,self.qid,True);old=review.standard(self.p,q,g.rules,self.fake)
            old.pop('method_version');old['method']='申论证据批改 v1'
            f=self.p.rubrics/'综合'/(self.qid+'.json');bank._write(f,old)
            def bad(msgs):return {'task':'错误引用','points':[{'name':'核心','material_quote':'虚构材料'}]}
            with self.assertRaises(review.ReviewError):review.standard(self.p,q,g.rules,bad)
            self.assertEqual(json.loads(f.read_text(encoding='utf-8')),old)
            new=review.standard(self.p,q,g.rules,self.fake)
        self.assertEqual(new['method_version'],2)
        backups=list((f.parent/'历史标准').glob('*.json'));self.assertEqual(len(backups),1)
        self.assertEqual(json.loads(backups[0].read_text(encoding='utf-8')),old)

    def test_material_paragraphs_and_html_old_files(self):
        raw=copy.deepcopy(PACKAGE);raw['title']='段落测试';raw['materials'][0]['text']='<p>第一段。</p><p>第二段。</p>'
        bank.import_packages(self.p,raw)
        qid=next(p['questions'][0]['qid'] for p in bank.listing(self.p) if p['title']=='段落测试')
        q=bank.question(self.p,qid);self.assertEqual(q['materials'][0]['text'],'第一段。\n第二段。')
        f=bank.folder(self.p)/(q['paper_id']+'.json');data=json.loads(f.read_text(encoding='utf-8'))
        data['materials'][0]['text']='<p>旧第一段。</p><p>旧第二段。</p>';bank._write(f,data)
        self.assertEqual(bank.question(self.p,qid)['materials'][0]['text'],'旧第一段。\n旧第二段。')
        self.assertEqual(json.loads(f.read_text(encoding='utf-8'))['materials'][0]['text'],data['materials'][0]['text'])

    def test_markdown_bank_reload_and_paragraphs(self):
        tpl=bank.folder(self.p)/'_模板.md'
        self.assertTrue(tpl.exists())
        self.assertFalse(any('示例卷' in p['title'] for p in bank.listing(self.p)))
        sc_md="""---
考试: 省考
地区: 四川
年份: 2025
卷型: 县乡卷
真题性质: 考生回忆版
来源: 粉笔公考题库
源试卷ID: 99001
---

# 2025年四川省公务员录用考试《申论》试卷（县乡卷）

## 给定材料

### 材料 1

第一自然段：基层社工⾛访居⺠需求。

第二自然段：跨部门协同办理。

### 材料 2

第三则材料第一段。

## 题目

### 第 1 题

关联材料：材料 1

根据“给定资料1”，概括基层便民举措。（20分）

作答要求：全面准确，不超过200字。

<details>
<summary>展开答案与解析</summary>

**参考答案（单一版）**

1. 走访居民需求；2. 跨部门协同办理。

**解析**

定位材料1两段分别提炼。
![思维导图](assets/map.png)

**考点**

归纳概括

</details>

### 第 2 题

关联材料：材料 1、材料 2

围绕基层治理现代化的思考，自选角度，自拟题目，写一篇文章。（40分）

要求：观点明确，800-1000字。

<details>
<summary>展开答案与解析</summary>

**参考答案**

以民为本赋能治理

第一段引出中心论点。

**基层善治，需要我们俯身倾听民意**。结合走访实践展开论述。

**解析**

文章写作立意解析。

**考点**

文章写作

</details>
"""
        md_file=bank.folder(self.p)/'2025-四川-县乡卷.md'
        md_file.write_text(sc_md,encoding='utf-8')
        info=api.shenlun_bank_reload({})
        self.assertEqual(info['errors'],[])
        paper=next(x for x in bank.listing(self.p) if '2025年四川省' in x['title'])
        self.assertEqual((paper['region'],paper['year'],paper['count']),('四川','2025',2))
        q1=bank.question(self.p,paper['questions'][0]['qid'],reveal=True)
        self.assertEqual(q1['materials'][0]['text'],'第一自然段：基层社工走访居民需求。\n第二自然段：跨部门协同办理。')
        self.assertEqual((q1['material_ids'],q1['material_source'],q1['total'],q1['words']),(['1'],'import',20.0,200))
        self.assertNotIn('map.png',q1['analysis'])
        q2=bank.question(self.p,paper['questions'][1]['qid'],reveal=True)
        self.assertEqual((q2['type'],q2['total'],q2['words']),('大作文',40.0,1000))
        self.assertIn('基层善治，需要我们俯身倾听民意',q2['references'][0]['answer'])

    def test_gwy_source_download_and_errrc_migration(self):
        import hashlib, time
        from rpg import shenlun_claims, shenlun_training
        errrc_used={
            'source_id':'errrc-paper-77',
            'title':'2024年贵州省公务员录用考试《申论》试卷（A卷）（网友回忆版）',
            'region':'贵州','year':'2024',
            'sourceName':'ERRRC/kaogong-shuati',
            'materials':[{'id':'1','label':'材料1','text':'贵州山村发展特色林下经济，带动村民家门口增收致富。'}],
            'questions':[{'source_id':'errrc-q-1','text':'概括林下经济的主要做法。（15分）不超过200字。','score':15,'limit':200}],
        }
        errrc_unused=copy.deepcopy(errrc_used)
        errrc_unused.update(source_id='errrc-paper-78',title='2023年未作答旧卷',year='2023')
        bank.import_packages(self.p,[errrc_used,errrc_unused])
        old_paper=next(x for x in bank.listing(self.p) if '贵州省' in x['title'])
        old_qid=old_paper['questions'][0]['qid']
        bank.answer_save(self.p,{'qid':old_qid,'text':'发展林下特色种植，拓宽增收渠道。','revision':0})
        shenlun_claims.claim(self.p,{'qids':[old_qid]})
        rev=shenlun_training.read(self.p)['revision']
        shenlun_training.save(self.p,{'id':old_qid,'topics':['农村'],'revision':rev})
        raw_dir=self.p.train/'题库原始库';raw_dir.mkdir(parents=True,exist_ok=True);(raw_dir/'materials.db').write_bytes(b'old')

        gz_md=("---\n考试: 省考\n地区: 贵州\n年份: 2024\n卷型: A卷\n真题性质: 考生回忆版\n来源: 粉笔\n源试卷ID: 8801\n---\n\n"
               "# 2024年贵州省公务员录用考试《申论》试卷（A卷）\n\n## 给定材料\n\n### 材料 1\n\n"
               "贵州山村发展特色林下经济，带动村民家门口增收致富。\n\n第二段补充产业联农机制。\n\n"
               "## 题目\n\n### 第 1 题\n\n关联材料：材料 1\n\n请概括林下经济的主要做法。（15分）\n\n要求：不超过200字。\n").encode('utf-8')
        manifest_entry={
            'path':'真题/申论/2024/贵州/2024年贵州省公务员录用考试《申论》试卷（A卷）.md',
            'subject':'申论','year':'2024','area':'贵州',
            'bytes':len(gz_md),'sha256':hashlib.sha256(gz_md).hexdigest(),
        }
        manifest_bytes=(json.dumps(manifest_entry,ensure_ascii=False)+'\n').encode('utf-8')
        def fake_fetch(url,max_bytes,timeout=45):
            if url.endswith('manifest.jsonl'):return manifest_bytes
            self.assertNotIn('贵州',url)  # URL中文路径必须经过quote编码
            return gz_md
        with patch.object(bank,'_fetch_bytes',fake_fetch):
            bank.source_start(self.p)
            for _ in range(50):
                st=bank.source_status(self.p)
                if not st.get('running'):break
                time.sleep(0.02)
        self.assertFalse(st.get('error'),st)
        self.assertFalse(raw_dir.exists())
        titles=[x['title'] for x in bank.listing(self.p)]
        self.assertNotIn('2023年未作答旧卷',titles)
        gz_papers=[x for x in bank.listing(self.p) if '贵州省' in x['title']]
        self.assertEqual(len(gz_papers),1)
        new_qid=gz_papers[0]['questions'][0]['qid']
        self.assertNotEqual(new_qid,old_qid)
        self.assertEqual(bank.answer_get(self.p,new_qid)['text'],'发展林下特色种植，拓宽增收渠道。')
        self.assertIn(new_qid,[x['qid'] for x in shenlun_claims.listing(self.p)['items']])
        self.assertEqual(gz_papers[0]['questions'][0]['topics'],['农村'])

if __name__=='__main__':unittest.main()
