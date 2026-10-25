"""独立清单PDF与配套原文匹配：自编PDF/临时库，不访问真实资料，不调用AI。"""
import base64
import copy
import os
import re
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
        return self.upload('digest',file)     # 3.7.4：不选配套讲义，程序按上下文自动找出处

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
        # 第2段（自编未知政策）在任何讲义里都找不到出处：不猜答案，但整份清单保留——按前后文归到相邻资料，标“待补全”，结果里如实告知。
        self.assertEqual((result['rows'],result['unmatched'],result['blanks'],result['ready'],result['pending']),(2,1,2,1,1))
        self.assertEqual([p['a'] for p in data['items']],['主产区',None])
        self.assertEqual([p['status'] for p in data['items']],['matched','pending'])
        self.assertEqual(source.read_bytes(),before)
        with api.open_game(save=False) as g:self.assertEqual(g.state['xp'],xp)

    def test_explicit_pdf_answers_take_priority_and_multiple_blanks(self):
        file=self.pdf(['1.为了保障供给，在____布局____。','参考答案','1.自编甲方、乙产业'])
        self.send(file);data=self.get()
        self.assertEqual([p['a'] for p in data['items']],['自编甲方','乙产业'])
        self.assertTrue(all(p['status']=='provided' for p in data['items']))

    def test_import_needs_no_target_and_finds_the_periodical_source(self):
        issue=self.upload('month',self.month);target={'source':'wanxiang_journal','kind':'month','id':issue['id']}
        result=self.send(self.pdf(['1.平陆运河是广西境内沟通____流域西江与北部湾的运河，是西部陆海新通道骨干工程。']))
        self.assertEqual((result['targets'],result['unmatched']),(1,0))
        data=self.get(target);self.assertEqual([p['a'] for p in data['items']][-1:],['珠江'])
        self.assertFalse(self.get()['documents'],'出处不在冲刺讲义里，不分到无关讲义')
        self.assertNotIn(('POST','/api/wanxiang/digest/targets'),api.ROUTES,'手选讲义的目录接口已取消')

    def test_not_found_source_is_reported_and_nothing_is_written(self):
        with self.assertRaises(api.ApiError):self.send(self.pdf(['1.自编完全无关的文字________补充说明内容。']))
        self.assertFalse(self.get()['documents'])
        with api.open_game(save=False) as g:self.assertFalse((g.paths.train/'时政消化/原文').exists() and list((g.paths.train/'时政消化/原文').glob('*.pdf')))

    @staticmethod
    def _page(rows,style):
        """按真实清单页的样子画一页：加粗小标题独占一行，空有下划线线段/细矩形/文字下划线/带下划线的空格四种写法。"""
        doc=fitz.open();page=doc.new_page(width=595,height=842);y=80
        for row in rows:
            x=60
            for seg in row:
                kind,text=('t',seg) if isinstance(seg,str) else seg
                if kind in ('t','B'):
                    page.insert_text((x,y),text,fontname='china-s',fontsize=10.5,render_mode=2 if kind=='B' else 0,border_width=.3 if kind=='B' else 0)
                    x+=fitz.get_text_length(text,fontname='china-s',fontsize=10.5)
                else:
                    w=float(text)
                    if style=='line':page.draw_line((x,y+2),(x+w,y+2),width=.6)
                    elif style=='rect':page.draw_rect(fitz.Rect(x,y+1.6,x+w,y+2.2),fill=(0,0,0),color=None)
                    elif style=='text':
                        under='_'*int(w/5.3);page.insert_text((x,y),under,fontname='china-s',fontsize=10.5);w=fitz.get_text_length(under,fontname='china-s',fontsize=10.5)
                    else:page.insert_text((x,y),' '*int(w/2.6),fontname='china-s',fontsize=10.5);page.draw_line((x,y+2),(x+w,y+2),width=.6)
                    x+=w
            y+=17
        return doc.tobytes()

    ROWS=[[('B','二、2026年全国两会之政府工作报告')],[('B','（一）2025年工作成就')],
          ['国内生产总值增长',('b',24),'%，总量达到',('b',48),'万亿元。'],
          [('b',50),'增加值规模连续16年保持全球第一，',('b',40),'领域外资准入限制措施全'],['部取消。货物贸易第',('b',40),'大国地位更加巩固。'],
          [('B','（三）2026年政策取向')],['坚持稳中求进、提质增效，加大',('b',30),'周'],['期和',('b',30),'周期调节力度。'],
          ['1.继续实施更加积极的',('b',40),'政策。把促进经济稳定增长、物价合理'],[('b',40),'作为货币政策的重要考量，运用',('b',20),'准',('b',20),'息工具。']]

    def test_headings_stay_out_of_paragraphs_and_every_underline_style_is_recognized(self):
        counts=[]
        for style in ('line','rect','text','space'):
            out=digest.parse_pdf(self._page(self.ROWS,style));texts=[re.sub(r'_+','____',x['text']) for x in out]
            self.assertEqual([x['text'] for x in out if x['kind']=='h'],['二、2026年全国两会之政府工作报告','（一）2025年工作成就','（三）2026年政策取向'],style+'：小标题单独成块保留')
            self.assertFalse([t for x,t in zip(out,texts) if x['kind']=='p' and ('2025年工作成就' in t or '政策取向' in t or '全国两会' in t)],style+'：小标题不能并进正文')
            self.assertTrue(any(t.startswith('____增加值规模') for t in texts),style+'：行首的空不能丢')
            self.assertTrue(any('物价合理____作为货币政策' in t for t in texts),style+'：换行后行首的空不能丢')
            counts.append(sum(len(digest.BLANK.findall(t)) for t in texts))
        self.assertEqual(counts,[11,11,11,11],'四种下划线写法认出的空一样多')

    def test_plain_underline_below_text_or_page_rule_is_not_a_blank(self):
        doc=fitz.open();page=doc.new_page(width=595,height=842)
        page.insert_text((60,100),'强调下划线下面的字不算空，后面有一个____真正的空。',fontname='china-s',fontsize=10.5)
        page.draw_line((60,102),(120,102),width=.6)           # 压在字下面的强调线
        page.draw_line((60,60),(500,60),width=.6)              # 页眉线
        out=digest.parse_pdf(doc.tobytes());self.assertEqual(sum(len(digest.BLANK.findall(x['text'])) for x in out),1)

    def test_reimport_after_recognition_upgrade_replaces_paragraphs_and_keeps_marks(self):
        file=self.pdf(['1.在________布局产能。'])
        self.send(file);first=self.get()
        with api.open_game(save=False) as g:
            store=next((g.paths.train/'时政消化').glob('*.json'))
            saved=politics.read_json(store,{});doc=saved['documents'][0];real=doc['paragraphs'][0]
            doc.pop('rv',None);doc['paragraphs']=[{'text':'自编旧段落____。','provided':[],'src':98},dict(real,src=0)]   # 旧规则留下的结果：多一段、序号不同
            politics.atomic_json(store,saved)
        old=self.get();item=next(x for x in old['items'] if x['a']=='主产区')
        self.mark(item,'remember')
        result=self.send(file)
        self.assertEqual((result['redone'],result['moved']),(1,1))
        new=self.get();self.assertEqual(len(new['items']),1)
        self.assertEqual(new['progress'][new['items'][0]['id']],'remember','核对记号随新识别结果保留')
        self.assertEqual(politics.read_json(store,{})['documents'][0]['rv'],digest.RV)
        again=self.send(file);self.assertTrue(again['duplicate'],'同一规则版本再次导入不叠加')

    def test_unmatched_samples_are_reported(self):
        result=self.send(self.pdf(['1.在________布局产能。','2.自编未知政策提出________要求，请注意。']))
        self.assertEqual(result['unmatched'],1);self.assertTrue(result['lost'][0].startswith('2.自编未知政策提出'))
        self.assertEqual(result['pdf_blanks'],2)

    def test_full_text_is_kept_with_headings_plain_sentences_and_bold(self):
        doc=fitz.open();page=doc.new_page(width=595,height=842)
        page.insert_text((60,80),'一、自编政策取向',fontname='china-s',fontsize=10.5)
        page.insert_text((60,98),'这一句没有空，也要保留。',fontname='china-s',fontsize=10.5)
        page.insert_text((60,116),'Key ',fontname='helv',fontsize=10.5);page.insert_text((84,116),'growth',fontname='hebo',fontsize=10.5)
        page.insert_text((120,116),' needs ____ policy.',fontname='helv',fontsize=10.5)
        out=digest.parse_pdf(doc.tobytes())
        self.assertEqual(out[0]['kind'],'h')
        body=next(x for x in out if 'Key' in x['text'])
        self.assertTrue(any(x['text']=='这一句没有空，也要保留。' and x['kind']=='p' for x in out),'没有空的句子也保留')
        word=body['text'].index('growth');self.assertIn([word,word+6],body['bold'],'PDF里加粗的字逐字记下来')
        self.assertNotIn([0,3],body['bold'])

    def test_blanks_in_another_font_stay_on_their_line_and_stroke_bold_is_bold(self):
        """用户的真实PDF（PDFium导出）：下划线是Times字体的“_”字符，基线比宋体字高/低约0.12磅，旧版按0.1取整拆成两行，
        行首/行中的空全被甩到行尾并合成一个；加粗是 Tr 2（填充+描边，texttrace里多出type=1的描边），不是粗体字库。"""
        doc=fitz.open();page=doc.new_page(width=595,height=842)
        def put(x,y,text,font='china-s',bold=False):
            page.insert_text((x,y),text,fontname=font,fontsize=10.4,**({'render_mode':2,'border_width':.3} if bold else {}))     # Tr 2：填充+描边，和真实PDF一样
            return x+fitz.get_text_length(text,fontname=font,fontsize=10.4)
        x=put(60,100,'2.继续实施适度宽松的');x=put(x,100.12,'________',font='tiro');put(x,100,'政策。把促进经济稳定增长、物价合理')
        x=put(60,118.12,'________',font='tiro');x=put(x,118,'作为货币政策的重要考量，灵活高效运用');x=put(x,118.12,'____',font='tiro')
        x=put(x,118,'准',bold=True);x=put(x,118.12,'____',font='tiro');put(x,118,'息等多种政策工具，')
        put(60,136,'保持');x=put(96,136,'流动性充裕',bold=True);put(x,136,'，使社会融资规模增长。')
        out=digest.parse_pdf(doc.tobytes())
        self.assertEqual(len(out),1)
        text=out[0]['text']
        self.assertEqual(text,'2.继续实施适度宽松的________政策。把促进经济稳定增长、物价合理________作为货币政策的重要考量，灵活高效运用____准____息等多种政策工具，保持流动性充裕，使社会融资规模增长。')
        self.assertEqual(len(digest.BLANK.findall(text)),4)
        for word in ('准','流动性充裕'):
            at=text.index(word);self.assertIn([at,at+len(word)],out[0]['bold'],word+'描边加粗要认出来')
        self.assertNotIn(text.index('作为'),[a for a,_ in out[0]['bold']])

    def test_unlocated_blocks_follow_neighbours_and_data_keeps_every_sentence(self):
        file=self.pdf(['消化清单','一、自编小标题','1.在________布局产能。','自编没有出处的普通句子，原样保留。','2.自编未知政策提出________要求。'])
        result=self.send(file);data=self.get()
        texts=[''.join(p.get('t','') if 't' in p else '____' for p in row['parts']) for row in data['paragraphs']]
        self.assertEqual([row['kind'] for row in data['paragraphs']],['h','p','p','p'])
        self.assertIn('自编没有出处的普通句子，原样保留。',texts[2])
        self.assertTrue(data['paragraphs'][0]['parts'][0]['b'],'小标题按粗体显示')
        self.assertEqual(result['unmatched'],1)

    def test_bold_runs_are_returned_with_literal_pieces(self):
        row={'text':'国家发展____很重要','provided':[],'kind':'p','bold':[[2,4]]}
        parts=digest._literals(row['text'],0,len(row['text']),row['bold'],False)
        self.assertEqual(parts,[{'t':'国家'},{'t':'发展','b':True},{'t':'____很重要'}])

    def test_user_fill_completes_pending_blank_and_survives_reimport(self):
        file=self.pdf(['1.在________布局产能。','2.自编未知政策提出________要求。'])
        self.send(file);item=next(p for p in self.get()['items'] if p['status']=='pending')
        with self.assertRaises(api.ApiError):api.ROUTES[('POST','/api/wanxiang/digest/fill')]({'target':self.target,'id':next(p for p in self.get()['items'] if p['status']=='matched')['id'],'text':'乱改'})
        data=api.ROUTES[('POST','/api/wanxiang/digest/fill')]({'target':self.target,'id':item['id'],'text':'  自编  答案 '})
        filled=next(p for p in data['items'] if p['status']=='filled');self.assertEqual(filled['a'],'自编 答案')
        self.mark(filled,'remember');self.assertEqual(self.get()['progress'][filled['id']],'remember')
        self.assertEqual(self.get()['counts']['pending'],0)
        # 改答案不丢核对记号；清空则回到待补全
        data=api.ROUTES[('POST','/api/wanxiang/digest/fill')]({'target':self.target,'id':filled['id'],'text':'新答案'})
        again=next(p for p in data['items'] if p['status']=='filled');self.assertEqual((again['id'],again['a']),(filled['id'],'新答案'))
        self.assertEqual(data['progress'][filled['id']],'remember')
        data=api.ROUTES[('POST','/api/wanxiang/digest/fill')]({'target':self.target,'id':filled['id'],'text':''})
        self.assertEqual(sum(p['status']=='pending' for p in data['items']),1)
        with self.assertRaises(api.ApiError):api.ROUTES[('POST','/api/wanxiang/digest/fill')]({'target':self.target,'id':item['id'],'text':'长'*81})

    def test_titled_answer_section_is_not_mistaken_for_cover(self):
        self.send(self.pdf(['1.在____布局产能。','消化清单·答案与解析','1.自编答案']))
        self.assertEqual(self.get()['items'][0]['a'],'自编答案')

    def test_ambiguous_context_does_not_pick_first_or_greedy_split(self):
        self.assertEqual(digest.match_answers('支持____发展产业。',['支持甲方发展产业。支持乙方发展产业。']),[None])
        self.assertEqual(digest.match_answers('支持____和____发展。',['支持甲和乙和丙发展。']),[None,None])
        self.assertEqual(digest.match_answers('支持____发展产业。',['支持甲方发展产业。支持甲方发展产业。']),['甲方'])
        # 3.7.6：空在整段开头/结尾时按“分句”取答案（上一个逗号/句号之后到后面的固定文字），仍须唯一才填
        self.assertEqual(digest.match_answers('____发展产业。',['支持甲方发展产业。']),['支持甲方'])
        self.assertEqual(digest.match_answers('2.____地制宜发展新质生产力，建设现代化产业体系。',['要求，因地制宜发展新质生产力，建设现代化产业体系。']),['因'])
        self.assertEqual(digest.match_answers('____发展产业。',['支持甲方发展产业。鼓励乙方发展产业。']),[None],'两处不同的前缀不猜')
        self.assertEqual(digest.match_answers('____增加值规模连续16年第一，____领域外资准入。',['制造业增加值规模连续16年第一，制造业领域外资准入。']),['制造业','制造业'])
        self.assertEqual(digest.match_answers('森林覆盖率提高到____',['森林覆盖率提高到25，成为国家。']),['25'])
        self.assertEqual(digest.match_answers('____以上',['成为国家，25%以上。']),[None],'上下文太少不猜')

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
            data=politics.atlas(g.paths,'2026-12-shengkao');m=next(x for x in data['materials'] if '平陆运河' in x['original'])
        self.send(self.pdf(['1.平陆运河是广西境内沟通____流域西江与北部湾的运河，是西部陆海新通道骨干工程。']))
        target={'source':'atlas','exam':'2026-12-shengkao','material':m['id']}
        self.assertTrue(self.get(target)['documents'])
        self.assertFalse(self.get()['documents'])
        with self.assertRaises(api.ApiError):self.get(dict(self.target,exam='2027-03-shengkao'))

    def test_periodical_target_keeps_old_embedded_pdf_cloze_and_import_priority(self):
        issue=self.upload('month',self.month);target={'source':'wanxiang_journal','kind':'month','id':issue['id']}
        old=self.get(target);self.assertTrue(old['counts']['ready'])
        self.send(self.pdf(['1.平陆运河是广西境内沟通____流域西江与北部湾的运河，是西部陆海新通道骨干工程。']))
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
