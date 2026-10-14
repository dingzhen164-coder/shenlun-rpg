"""3.1.1行测截图：使用自编PDF、临时题库和假拆卷器，检查实际裁图与旧/新入口，不读取真实库。"""
import base64
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rpg import question_images as images, paths, vault, trainer, importer

SCRIPT = '''from types import SimpleNamespace as N
from pathlib import Path
import sys
ALWAYS_SNAP={'数量关系','图形推理'}
def extract_lines(doc):
 return [N(x0=43)]
def parse(lines,left):
 q=N(num=76,board='图形推理',section='判断推理',start=N(page=0,y0=650,y1=670),ans_line=N(page=1,y0=280),stem_lines=[('Choose the pattern',43)],opt_lines=[],material=None)
 n=N(num=77,board='数量关系',section='数量关系',start=N(page=1,y0=310,y1=330),ans_line=N(page=1,y0=400),stem_lines=[('Compute 1/2 + 1/3',43)],opt_lines=[],material=None)
 return [q,n],[]
def split_options(lines):
 return dict(A='A',B='B',C='C',D='D')
def join_stem(lines,left):
 return ' '.join(x[0] for x in lines)
def classify(q,stem):
 return q.board
def region_segments(doc,start,page,y):
 return [(p,start.y0 if p==start.page else 70,y if p==page else 785) for p in range(start.page,page+1)]
def has_images(doc,segs):
 return True
def snap(doc,segs,folder,stem):
 raise AssertionError('must replace the old screenshot generator')
def main():
 import pymupdf as pm
 out=Path(sys.argv[sys.argv.index('--out')+1]);att=out/'attachments';att.mkdir(parents=True,exist_ok=True)
 with pm.open(sys.argv[1]) as doc:
  for q in parse([],43)[0]:
   pics=snap(doc,region_segments(doc,q.start,q.ans_line.page,q.ans_line.y0),att,'S38-Q%03d'%q.num)
   (out/('%02d-'%q.num+q.board+'.md')).write_text(' '.join(pics),encoding='utf-8')
'''


class QuestionImagesTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.p=paths.Paths(Path(self.tmp.name),'行测')
        self.p.ensure_train_dir()
        self.pm=images._pm()
        if not self.pm:self.skipTest('需要原有PyMuPDF拆卷组件')
        images._CACHE.clear()
    def tearDown(self):
        self.tmp.cleanup()
    def png(self,w=80,h=55):
        d=self.pm.open();page=d.new_page(width=w,height=h)
        page.draw_rect(self.pm.Rect(4,4,w-4,h-4),color=(0,0,0))
        page.draw_circle(self.pm.Point(w/2,h/2),10,color=(0,0,0))
        raw=page.get_pixmap().tobytes('png');d.close();return raw
    def fixture(self):
        script=self.p.vault/'copilot/skills/xingce-mokao-split/scripts/split_mokao.py'
        script.parent.mkdir(parents=True,exist_ok=True);script.write_text(SCRIPT,encoding='utf-8')
        folder=self.p.vault/'FB模考试卷复盘/模考试卷';folder.mkdir(parents=True,exist_ok=True)
        pdf=folder/'第38季-自编.pdf';d=self.pm.open()
        p=d.new_page(width=595,height=842);p.insert_text((43,670),'76. Choose the pattern.')
        p=d.new_page(width=595,height=842);p.insert_image(self.pm.Rect(43,90,343,245),stream=self.png())
        p.insert_text((50,262),'A');p.insert_text((140,262),'B');p.insert_text((220,262),'C');p.insert_text((310,262),'D')
        p.insert_text((43,335),'77. Compute 1/2 + 1/3.')
        p.insert_image(self.pm.Rect(100,350,110,374),stream=self.png(10,24)) # 小公式不是几何图。
        d.save(pdf);d.close();return pdf,script
    def test_missing_fraction_glyph_is_kept_inline_at_original_position(self):
        from types import SimpleNamespace as N
        d=self.pm.open();page=d.new_page(width=300,height=250)
        page.insert_text((43,120),'A share is');page.insert_text((160,120),'of B.')
        fraction=self.pm.open();f=fraction.new_page(width=16,height=32)
        f.insert_text((5,11),'1',fontsize=9);f.draw_line(self.pm.Point(3,16),self.pm.Point(13,16));f.insert_text((5,29),'2',fontsize=9)
        png=f.get_pixmap().tobytes('png');fraction.close()
        page.insert_image(self.pm.Rect(115,103,131,135),stream=png)
        line=N(page=0,y0=108,y1=123,x0=43,text='A share is of B.')
        updated,recipes=images._symbol_lines(self.p,d,[line],[(0,80,170)],[],'self-test',True)
        self.assertEqual(len(recipes),1);self.assertIn('![[',updated[0].text)
        self.assertLess(updated[0].text.index('A share is'),updated[0].text.index('![['));self.assertIn('of B.',updated[0].text)
        self.assertEqual(line.text,'A share is of B.')
        blocks=vault.text_blocks(self.p,None,updated[0].text)
        self.assertEqual([b['t'] for b in blocks],['text']);self.assertIn('/符号/',blocks[0]['v'])
        self.assertTrue((self.p.vault/recipes[0]['path']).exists());d.close()

    def test_small_formula_numbers_underlines_and_background_are_not_figures(self):
        d=self.pm.open();p=d.new_page(width=595,height=842)
        p.insert_text((43,120),'ABCD 1234 1/2 56%')
        p.insert_image(self.pm.Rect(50,140,61,164),stream=self.png(11,24))
        p.draw_line(self.pm.Point(40,170),self.pm.Point(110,170))
        p.insert_image(self.pm.Rect(0,0,595,842),stream=self.png(100,100))
        self.assertEqual(images.graphics(d,[(0,70,400)]),[]);d.close()
    def test_raster_figure_ignores_previous_page_text_and_includes_options(self):
        pdf,_=self.fixture();m=images.prepare(self.p,pdf)
        clips=m['questions']['Q076']['clips'];self.assertEqual(len(clips),1);self.assertEqual(clips[0][0],1)
        self.assertLess(clips[0][2],95);self.assertGreater(clips[0][4],262)
        self.assertEqual(m['questions']['Q077']['clips'],[])
    def test_vector_geometry_kept_but_fraction_bar_not_kept(self):
        d=self.pm.open();p=d.new_page(width=300,height=300)
        p.draw_line(self.pm.Point(10,50),self.pm.Point(30,50))
        shape=p.new_shape();shape.draw_polyline([self.pm.Point(70,90),self.pm.Point(180,90),self.pm.Point(130,190),self.pm.Point(70,90)]);shape.finish(color=(0,0,0));shape.commit()
        clips=images.graphics(d,[(0,20,250)]);self.assertEqual(len(clips),1);self.assertGreater(clips[0][1],60);d.close()
    def test_borderless_statistics_table_kept(self):
        d=self.pm.open();p=d.new_page(width=500,height=500)
        p.insert_text((40,80),'Year');p.insert_text((160,80),'Count');p.insert_text((260,80),'Rate')
        for i in range(4):
            for x,t in [(40,str(2020+i)),(160,str(100+i)),(260,str(20+i)+'%')]:p.insert_text((x,110+i*25),t)
        self.assertEqual(images.graphics(d,[(0,60,260)]),[])
        clips=images.graphics(d,[(0,60,260)],table=True);self.assertEqual(len(clips),1);self.assertLess(clips[0][2],80);d.close()
    def test_multipage_graphs_combined_once_without_rescaling(self):
        d=self.pm.open()
        for i in range(2):
            p=d.new_page(width=200,height=300);p.insert_image(self.pm.Rect(30,90,150,180),stream=self.png())
        clips=images.graphics(d,[(0,80,200),(1,80,200)])
        self.assertEqual(len(clips),2)
        raw=images._capture(d,clips);pix=self.pm.Pixmap(raw)
        self.assertGreater(pix.height,350);self.assertLess(pix.width,300);self.assertGreater(max(pix.samples)-min(pix.samples),200);d.close()
    def test_old_bank_and_review_use_one_cropped_image_preserve_source(self):
        pdf,_=self.fixture()
        folder=self.p.seasons/'第38季';(folder/'attachments').mkdir(parents=True)
        for n in (1,2):(folder/'attachments'/('S38-Q076-%d.png'%n)).write_bytes(self.png())
        text='![[S38-Q076-1.png]]\n![[S38-Q076-2.png]]\n\n从四个选项中选择最合适的图形，使其呈现一定规律。\nA. A\nB. B\nC. C\nD. D'
        q=dict(body=text,source='图形推理',dir=str(folder))
        before={p:p.read_bytes() for p in (folder/'attachments').iterdir()}
        blocks=vault.render_blocks(self.p,q,False);pics=[b for b in blocks if b['t']=='img']
        self.assertEqual(len(pics),1);self.assertIn('_净化/',pics[0]['v'])
        self.assertNotIn('A. A','\n'.join(b['v'] for b in blocks if b['t']=='text'))
        stub=type('G',(),{'paths':self.p})()
        f=self.p.train/'题库/图片/数量关系/粉笔38季-077.png';f.parent.mkdir(parents=True);f.write_bytes(self.png())
        original='\n'.join('A. '+v for v in ['1/2','1/3'])+'\n关于比例的文字题，选择一个符合条件的结果。\n![[训练/题库/图片/数量关系/粉笔38季-077.png]]'
        rendered=trainer._bank_blocks(stub,'数量关系',original,question=True)
        self.assertFalse(any(b['t']=='img' for b in rendered));self.assertIn('1/2',rendered[0]['v'])
        self.assertEqual({p:p.read_bytes() for p in before},before)
        cached=vault.render_blocks(self.p,q,False);self.assertEqual(cached,blocks)
    def test_text_only_board_and_image_only_fallback_and_subject_scope(self):
        text='纯文字定义题：下列哪项符合上述定义，请根据文字作答。 A. 甲 B. 乙 C. 丙 D. 丁\n![[普通题图.png]]'
        self.assertNotIn('![[',images.clean_text(self.p,'定义判断',text))
        self.assertEqual(images.clean_text(self.p,'图形推理','![[缺少原PDF.png]]'),'![[缺少原PDF.png]]')
        incomplete='（粉笔第38季模考）\n![[S38-Q090.png]]\nA. A\nB. B\nC. C\nD. D'
        self.assertIn('![[',images.clean_text(self.p,'定义判断',incomplete))
        self.assertEqual(images.clean_text(paths.Paths(self.p.vault,'申论'),'定义判断',text),text)
    def test_analysis_images_not_removed(self):
        p=self.p.train/'题库/图片/定义判断/解析.png';p.parent.mkdir(parents=True);p.write_bytes(self.png())
        text='这是解析中的关系示意图，需要结合完整解析阅读。\n![[训练/题库/图片/定义判断/解析.png]]'
        blocks=trainer._bank_blocks(type('G',(),{'paths':self.p})(),'定义判断',text)
        self.assertTrue(any(b['t']=='img' for b in blocks))
    def test_new_splitter_uses_same_rules_and_training_output(self):
        pdf,script=self.fixture();out=self.p.train/'模考复盘/第38季';out.mkdir(parents=True)
        with patch.dict(os.environ,{'XINGCE_CLEAN_VAULT':str(self.p.vault)}),patch.object(sys_module(),'argv',list(sys_module().argv)):
            images.run_splitter(script,[str(pdf),'--out',str(out)])
        self.assertEqual(len(list((out/'attachments').glob('*.png'))),1)
        self.assertEqual(script.read_text(encoding='utf-8'),SCRIPT)
        self.assertIn((38,out),vault.seasons(self.p))
    def test_existing_season_import_does_not_rerun_splitter_or_overwrite_notes(self):
        pdf,script=self.fixture();d=self.p.seasons/'第38季';d.mkdir(parents=True)
        f=d/'02-常识判断.md';raw='### 21. ✅\n根据下列文字作答，选择符合条件的一项。\n- **A.** 甲\n- **B.** 乙\n- **C.** 丙\n- **D.** 丁\n> 正确答案：**A**　我的答案：**A**\n> [!note] 复盘\n> 我的个人笔记\n---\n';f.write_text(raw,encoding='utf-8')
        with patch('subprocess.run',side_effect=AssertionError('不重拆已有复盘')):
            r=importer.split_pdf(self.p,dict(file=pdf.name))
        self.assertEqual(r['ready'],1);self.assertEqual(f.read_text(encoding='utf-8'),raw)


def sys_module():
    import sys
    return sys

if __name__=='__main__':unittest.main()
