"""冲刺刷题PDF按套卷/题号/选项切分：自编PDF页，不访问真实资料，不调用AI。"""
import os
import unittest

from rpg import politics, politics_exam as exam
from tests.test_tianji import fitz


def setUpModule():os.environ['SHENLUN_SUBJECT']='行测'
def tearDownModule():os.environ.pop('SHENLUN_SUBJECT',None)

# (缩进x, 文字)：首行缩进的题干、悬挂缩进的折行、一行里挤着四个选项……照真实套卷页的样子
PAGE1=[(95,'Hey，上岸吧！'),(380,'@公考小黑老师'),(180,'黑十专项卷一 党的创新理论'),(100,'用时（分钟）'),(100,'答对题数（道）'),(80,'根据题目要求，在四个选项中选出一个最恰当的答案。'),
       (90,'1.【小黑政治理论】关于中国特色社会主义新时代相关论断，下列说法正确'),(60,'的是：'),
       (90,'①坚持和发展中国特色社会主义，是改革开放以来我们党全部理论和实践的'),(60,'鲜明主题，也是习近平新时代中国特色社会主义思想的核心要义'),
       (90,'②党的十八大作出中国特色社会主义进入新时代这一重大政治论断'),(90,'③我国社会主要矛盾的变化是作出中国特色社会主义进入新时代重大判断的'),(60,'基本依据'),
       (90,'④社会主要矛盾发生转化，意味着我国社会主义所处历史阶段发生根本改变'),(60,'A.①③          B.①②          C.②④          D.③④'),
       (90,'2.【小黑政治理论】习近平新时代中国特色社会主义思想是坚持“两个结合”'),(60,'的重大成果和光辉典范。下列说法正确的是：'),
       (90,'A.“两个结合”是指要把马克思主义基本原理同中国具体实际相结合、同中'),(60,'华优秀传统文化相结合，这两个命题均为新时代提出，是重要的思想解放'),
       (90,'B.“两个结合”是对坚持和发展马克思主义作出的重大理论贡献，是我们取'),(60,'得成功的最大法宝'),
       (90,'C.“两个结合”是用新时代中国之“矢”去射马克思主义之“的”'),(90,'D.“两个结合”使马克思主义根脉和中华优秀传统文化魂脉内在贯通'),
       (90,'3.【小黑政治理论】“十个明确”是习近平新时代中国特色社会主义思想的'),(60,'主体内容，集中体现了这一思想体系的主要观点和基本精神。关于“十个明确”，'),(60,'下列说法正确的有几项？'),
       (90,'①中国特色社会主义最本质的特征是中国共产党领导'),(90,'②坚持和发展中国特色社会主义的总任务是实现社会主义现代化和中华民族伟大复兴'),
       (90,'③全面深化改革总目标是建设中国特色社会主义法治体系'),(90,'④党在新时代的强军目标是建设一支听党指挥、能打胜仗、作风优良的人民军队'),
       (90,'A.1项'),(90,'B.2项'),(90,'C.3项'),(90,'D.4项')]
PAGE2=[(180,'黑十专项卷二 经济与社会'),(90,'1.【小黑政治理论】关于高质量发展，下列说法正确的是：'),(90,'A.甲'),(90,'B.乙'),(90,'C.丙'),(90,'D.丁'),
       (90,'2.下列表述错误的是：'),(90,'A.甲错'),(90,'B.乙错'),(90,'C.丙错'),(90,'D.丁错')]
ANSWERS=[(180,'黑十专项卷一 答案解析'),(90,'1.【答案】A'),(90,'解析：本题考查新时代论断。'),(90,'2.【答案】B'),(90,'3.【答案】D'),
         (180,'黑十专项卷二 答案解析'),(90,'1.【答案】C'),(90,'2.【答案】A')]


def make(pages):
    doc=fitz.open()
    for rows in pages:
        page=doc.new_page(width=595,height=842);y=60
        for x,text in rows:
            page.insert_text((x,y),text,fontname='china-s',fontsize=11);y+=18
    return doc


@unittest.skipIf(fitz is None,'缺PDF组件')
class ExamTests(unittest.TestCase):
    def parse(self,pages,name='自编十套卷.pdf'):
        with make(pages) as doc:return exam.parse(doc,name)

    def test_papers_numbers_and_every_option_are_split(self):
        papers,questions,report=self.parse([PAGE1,PAGE2])
        self.assertEqual([p['title'] for p in papers],['黑十专项卷一党的创新理论','黑十专项卷二经济与社会'])
        self.assertEqual([(q['paper'],q['no']) for q in questions],[(0,1),(0,2),(0,3),(1,1),(1,2)])
        q1,q2,q3=questions[:3]
        self.assertIn('A.①③',q1['text']);self.assertEqual(q1['text'].splitlines()[-1],'D.③④')
        self.assertEqual([x[0] for x in exam.split_options('A.①③          B.①②          C.②④          D.③④')],['A','B','C','D'])
        for q in questions:self.assertEqual(q['letters'],['A','B','C','D'],'每题四个选项都在：%s'%q['text'][:30])
        self.assertTrue(all('选项不全' not in q['flags'] for q in questions))
        # 第2题的折行选项并回自己，第3题的题干没有被并进第2题的D项
        self.assertTrue(q2['text'].splitlines()[-1].startswith('D.“两个结合”使马克思主义根脉'))
        self.assertNotIn('十个明确',q2['text'])
        self.assertIn('同中华优秀传统文化相结合',q2['text'])
        self.assertTrue(q3['text'].startswith('【小黑政治理论】“十个明确”') or q3['text'].startswith('“十个明确”') or '十个明确' in q3['text'].splitlines()[0])
        self.assertIn('①中国特色社会主义最本质的特征是中国共产党领导',q3['text']);self.assertEqual(q3['text'].splitlines()[-1],'D.4项')
        self.assertEqual(report['papers'],[{'title':'黑十专项卷一党的创新理论','questions':3},{'title':'黑十专项卷二经济与社会','questions':2}])
        self.assertEqual((report['incomplete_count'],report['unanswered']),(0,5))

    def test_answers_follow_each_paper_and_numbers_restart(self):
        papers,questions,report=self.parse([PAGE1,PAGE2,ANSWERS])
        self.assertEqual([(q['paper'],q['no'],q['answer']) for q in questions],[(0,1,'A'),(0,2,'B'),(0,3,'D'),(1,1,'C'),(1,2,'A')])
        self.assertIn('新时代论断',questions[0]['analysis']);self.assertEqual(report['unanswered'],0)
        self.assertEqual(len(papers),2,'答案页标题不新增套卷')

    def test_missing_options_are_flagged_not_guessed(self):
        rows=[(180,'黑十专项卷一 测试'),(90,'1.【小黑政治理论】题干一：'),(90,'A.甲'),(90,'B.乙'),(90,'2.【小黑政治理论】题干二：'),(90,'A.甲'),(90,'B.乙'),(90,'C.丙'),(90,'D.丁')]
        _,questions,report=self.parse([rows])
        self.assertEqual([q['letters'] for q in questions],[['A','B'],['A','B','C','D']])
        self.assertEqual((report['incomplete_count'],report['incomplete']),(1,['黑十专项卷一测试第1题']))

    def test_ocr_noise_lowercase_options_and_at_sign_are_repaired(self):
        """用户截图：选项行被OCR成“B.①②c.@④”“D.③@”——小写c要认成选项C，“@”按数字顺序/出现次数补回②④。"""
        rows=[(180,'黑十专项卷一 测试'),(90,'1.【小黑政治理论】关于新时代相关论断，下列说法正确的是：'),(90,'①坚持和发展'),(90,'②党的十八大作出重大判断'),(90,'@我国社会主要矛盾的变化'),(90,'④社会主要矛盾发生转化'),
              (90,'A.①③'),(90,'B.①②c.@④'),(90,'D.③@'),
              (90,'2.【小黑政治理论】第二题：'),(90,'A.甲'),(90,'B.乙'),(90,'c.丙'),(90,'d.丁'),
              (90,'3.【小黑政治理论】第三题，etc. 之类写法不应当成选项：'),(90,'A.甲'),(90,'B.乙'),(90,'C.丙'),(90,'D.丁')]
        _,questions,report=self.parse([rows])
        first=questions[0]
        self.assertIn('B.①②',first['text']);self.assertIn('C.②④',first['text']);self.assertIn('D.③④',first['text'])
        self.assertNotIn('@',first['text']);self.assertIn('③我国社会主要矛盾',first['text'],'题干里“@”开头的第三条按顺序补成③')
        self.assertEqual(first['letters'],['A','B','C','D']);self.assertIn('符号推测',first['flags'],'C选项是按均衡推测的，要标出来')
        self.assertEqual(questions[1]['letters'],['A','B','C','D'],'小写c./d.接在B后面认成选项')
        self.assertEqual(questions[2]['letters'],['A','B','C','D'],'etc.不当选项')
        self.assertEqual((report['repaired'],report['guessed']),(2,1))

    def test_screenshot_ocr_pdf_noise_is_cleaned(self):
        """用户真实的“截图转PDF+OCR文字层”冲刺卷（自编同样的错法，原文不进仓库）：页眉页脚夹在题中间、并排选项y有抖动、
        陈述编号①被认成1/5、题号“7.”认成“乙.”、小黑标签括号不配对、“C绿色”丢了点、进人/自已。"""
        doc=fitz.open()
        def page(items):
            pg=doc.new_page(width=595,height=842)
            for x,y,text in items:pg.insert_text((x,y),text,fontname='china-s',fontsize=11)
        page([(90,50,'Hey、上岸吧！'),(380,54,'@公考小黑老师'),(180,120,'黑十专项卷一 测试'),
              (60,140,'1.【小黑政治理论】下列说法正确的有几项？'),(80,158,'1坚持甲'),(80,176,'②坚持乙'),(80,194,'③坚持丙'),(80,212,'④坚持丁'),(80,230,'3坚持戊，体现自已国情'),
              (360,250,'D.5项'),(60,250.4,'A.2项'),(260,251,'C.4项'),(160,249.3,'B.3项'),
              (90,790,'抖音关注公考小黑老师'),(300,780,'1'),(400,792,'时政要点即时学')])
        page([(440,50,'Hey，土岸吧！'),(110,54,'@公考小黑老师'),
              (60,100,'乙.（小黑政治理论】进人新时代，下列说法正确的有几项？'),(80,118,'①甲'),(80,136,'②乙'),(80,154,'③丙'),(80,172,'④丁'),
              (60,190,'A.①②'),(160,190.8,'B.①②3'),(260,189.5,'c.@④'),(360,190.2,'D.3④'),
              (60,220,'3.（小黑政治理论）第三题：'),(60,238,'A.甲'),(60,256,'B.乙'),(60,274,'C丙'),(60,292,'D.丁'),
              (90,790,'抖音关注公考小黑老师'),(300,780,'2'),(400,792,'时政要点即时学')])
        with doc:
            papers,questions,report=exam.parse(doc,'x.pdf')
        self.assertEqual(len(papers),1);self.assertEqual([q['no'] for q in questions],[1,2,3],'乙.认成第2题，第3题的小括号标签也认')
        one,two,three=[q['text'] for q in questions]
        self.assertNotIn('上岸',one+two+three);self.assertNotIn('抖音',one+two+three);self.assertNotIn('时政要点',one+two+three)
        self.assertEqual(one.split('\n')[-4:],['A.2项','B.3项','C.4项','D.5项'],'并排选项按从左到右，不被y抖动打乱')
        self.assertIn('\n①坚持甲\n',one);self.assertIn('\n⑤坚持戊',one,'1/3按顺序改回①/⑤');self.assertIn('自己国情',one)
        self.assertTrue(two.startswith('【小黑政治理论】进入新时代'));self.assertEqual(two.split('\n')[-4:],['A.①②','B.①②③','C.@④','D.③④'],'①②③出现次数并列，没把握就保持“@”，不乱猜')
        self.assertNotIn('符号推测',questions[1]['flags'])
        self.assertTrue(three.startswith('【小黑政治理论】第三题'),'括号配对统一');self.assertIn('C.丙',three);self.assertEqual(questions[2]['letters'],['A','B','C','D'])
        self.assertEqual(report['incomplete_count'],0)

    def test_symbols_that_cannot_be_decided_are_left_alone(self):
        stem=['①甲','②乙','③丙','④丁'];opts=[('A','①@'),('B','@④')]
        self.assertEqual(exam.repair_symbols(stem,opts),(0,0));self.assertEqual(opts,[('A','①@'),('B','@④')],'并列、没把握就不补，不乱猜')

    def test_numbers_inside_text_do_not_split_and_missing_headings_fall_back_to_file_name(self):
        rows=[(90,'1.【小黑政治理论】增长率达到5.2%，居世界前列：'),(90,'2024年以来GDP增长'),(90,'A.1.5倍'),(90,'B.2倍'),(90,'C.3倍'),(90,'D.4倍')]
        papers,questions,_=self.parse([rows],'专项练习.pdf')
        self.assertEqual((len(papers),papers[0]['title'],len(questions)),(1,'专项练习',1))
        self.assertEqual(questions[0]['letters'],['A','B','C','D'])

    def test_number_back_to_one_starts_a_new_paper_without_heading(self):
        rows=[]
        for no in (1,2,3,4,1,2):rows+= [(90,'%d.【小黑政治理论】第%d题干：'%(no,no)),(90,'A.甲'),(90,'B.乙'),(90,'C.丙'),(90,'D.丁')]
        papers,questions,_=self.parse([rows],'无标题.pdf');self.assertEqual(len(papers),2);self.assertEqual([q['paper'] for q in questions],[0,0,0,0,1,1])


@unittest.skipIf(fitz is None,'缺PDF组件')
class AnswerImportTests(unittest.TestCase):
    """导入的套卷原PDF没有答案时，另给答案文字/答案页PDF补上；按套卷内题号对应，只改这一套。"""
    def setUp(self):
        import base64,tempfile
        from pathlib import Path
        from rpg import politics_import
        self.politics,self.base64=politics,base64
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);root=Path(t.name)
        from rpg import paths
        from tests.test_politics361 import atlas_data
        self.pp=paths.Paths(root,'行测');self.pp.ensure_train_dir()
        politics.atomic_json(self.pp.train/'时政知识地图/内容.json',atlas_data())
        rows=PAGE1+PAGE2
        with make([rows[:len(PAGE1)],PAGE2]) as doc:data=doc.tobytes()
        self.report=politics_import.import_pdf(self.pp,{'mode':'practice','name':'自编十套卷.pdf','data':base64.b64encode(data).decode()})
        self.atlas=politics.atlas(self.pp,politics.DEFAULT_EXAM)
        self.papers=[m for m in self.atlas['materials'] if m.get('practice_only')]

    def questions(self,paper):
        return {q['no']:q for q in politics.atlas(self.pp,politics.DEFAULT_EXAM)['questions'] if q['material']==paper['id'] and q.get('no')}

    def test_text_answers_fill_only_that_paper_and_report_missing(self):
        one,two=self.papers[:2]
        self.assertTrue(all(not q['answer'] for q in self.questions(one).values()),'原PDF没带答案')
        out=self.politics_exam.apply_answers(self.pp,{'material':one['id'],'text':'1.A 2.B 3.AB 9.C'})
        self.assertEqual((out['filled'],out['changed'],out['unknown'],out['missing']),(3,0,[9],[]))
        self.assertEqual({n:q['answer'] for n,q in self.questions(one).items()},{1:'A',2:'B',3:'AB'})
        self.assertTrue(all(not q['answer'] for q in self.questions(two).values()),'别的套卷不受影响')
        again=self.politics_exam.apply_answers(self.pp,{'material':one['id'],'text':'1-3 ACD'})
        self.assertEqual((again['filled'],again['changed']),(0,2),'再导入按新答案覆盖并报告改了几题')
        part=self.politics_exam.apply_answers(self.pp,{'material':two['id'],'text':'1.B'})
        self.assertEqual(part['missing'],[2])

    def test_answer_page_pdf_and_bad_input(self):
        one=self.papers[0]
        with make([[(90,'1.【答案】A。解析：2025年增长。'),(90,'2.【答案】C。解析：1.5倍。'),(90,'3.【答案】D')]]) as doc:pdf=doc.tobytes()
        out=self.politics_exam.apply_answers(self.pp,{'material':one['id'],'pdf':self.base64.b64encode(pdf).decode()})
        self.assertEqual(out['filled'],3);self.assertEqual({n:q['answer'] for n,q in self.questions(one).items()},{1:'A',2:'C',3:'D'})
        for body in ({'material':one['id'],'text':''},{'material':one['id'],'text':'没有答案'},{'material':'nope','text':'1.A'}):
            with self.assertRaises(self.politics.PoliticsError):self.politics_exam.apply_answers(self.pp,body)

    def test_batch_answers_keep_paper_numbers_separate_and_repeat_safely(self):
        out=exam.apply_answers(self.pp,{'material':'all','text':'1.A 2.B 3.C\n1.D 2.A'})
        self.assertEqual(out['filled'],5)
        self.assertEqual([self.questions(p)[1]['answer'] for p in self.papers[:2]],['A','D'])
        again=exam.apply_answers(self.pp,{'material':'all','text':'1.A 2.B 3.C\n1.D 2.A'})
        self.assertEqual((again['filled'],again['changed'],again['same']),(0,0,5))

    def test_batch_files_match_titles_in_any_order_and_fail_atomically(self):
        one,two=self.papers[:2]
        out=exam.apply_answers(self.pp,{'material':'all','batches':[{'name':two['title']+'.txt','text':'1.D 2.C'}, {'name':one['title']+'.txt','text':'1.A 2.B 3.C'}]})
        self.assertEqual(out['filled'],5)
        self.assertEqual(self.questions(two)[1]['answer'],'D')
        before=self.questions(one)
        with self.assertRaises(politics.PoliticsError):
            exam.apply_answers(self.pp,{'material':'all','batches':[{'name':one['title']+'.txt','text':'1.B'}, {'name':one['title']+'.txt','text':'1.C'}]})
        self.assertEqual(self.questions(one),before)
        with self.assertRaises(politics.PoliticsError):
            exam.apply_answers(self.pp,{'material':one['id'],'text':'1.B 2.C\n1.D'})
        self.assertEqual(self.questions(one),before)

    politics_exam=exam

