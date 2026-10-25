"""冲刺刷题PDF按套卷/题号/选项切分：自编PDF页，不访问真实资料，不调用AI。"""
import os
import unittest

from rpg import politics_exam as exam
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

    def test_numbers_inside_text_do_not_split_and_missing_headings_fall_back_to_file_name(self):
        rows=[(90,'1.【小黑政治理论】增长率达到5.2%，居世界前列：'),(90,'2024年以来GDP增长'),(90,'A.1.5倍'),(90,'B.2倍'),(90,'C.3倍'),(90,'D.4倍')]
        papers,questions,_=self.parse([rows],'专项练习.pdf')
        self.assertEqual((len(papers),papers[0]['title'],len(questions)),(1,'专项练习',1))
        self.assertEqual(questions[0]['letters'],['A','B','C','D'])

    def test_number_back_to_one_starts_a_new_paper_without_heading(self):
        rows=[]
        for no in (1,2,3,4,1,2):rows+= [(90,'%d.【小黑政治理论】第%d题干：'%(no,no)),(90,'A.甲'),(90,'B.乙'),(90,'C.丙'),(90,'D.丁')]
        papers,questions,_=self.parse([rows],'无标题.pdf');self.assertEqual(len(papers),2);self.assertEqual([q['paper'] for q in questions],[0,0,0,0,1,1])
