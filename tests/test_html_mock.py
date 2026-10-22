"""自编粉笔结构HTML与小PNG：完整导入、整组材料、缺图拒绝、重复/旧笔记及ZIP边界。"""
import base64
import io
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from rpg import html_mock, importer, paths, question_bank, vault

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')

def fixture():
    def question(i):
        return '<app-ti><div class="title-index">%d.</div><app-question-choice><app-format-html><p>自编第%d题：哪项符合条件？</p></app-format-html><app-choice-radio>%s</app-choice-radio></app-question-choice><app-solution-overall><span class="correct-answer">A</span></app-solution-overall><app-result-common><app-format-html><p>自编解析：核对条件。</p><script>不应执行或进入题库</script></app-format-html></app-result-common><app-solution-keypoint>自编考点</app-solution-keypoint></app-ti>' % (i,i,''.join('<li class="choice-radio"><div class="input-radio %s">%s</div><p class="input-text">%s</p></li>' % ('correct' if k=='A' else '',k,'自编选项'+k) for k in 'ABCD'))
    return '<html><title>自编第39季模考</title><app-answer-card><div class="chapter-title">资料分析</div>%s</app-answer-card>%s</html>' % (''.join('<button class="answer-btn">%d</button>' % i for i in range(1,11)),''.join('<div><app-materials><div class="material-content"><p>自编材料第%d组：仅用于测试的统计数据，甲乙丙丁各有不同结果。</p><img src="./自编_files/图.png"></div></app-materials><nav>%s</nav>%s</div>' % (g,''.join('%d题 ' % i for i in range(g*5+1,g*5+6)),''.join(question(i) for i in range(g*5+1,g*5+6))) for g in range(2)))


def zip_data(files):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
    return base64.b64encode(stream.getvalue()).decode()


def body():
    return dict(name='自编第39季.html',data=base64.b64encode(fixture().encode()).decode(),resources=dict(name='自编_files.zip',data=zip_data({'自编_files/图.png':PNG})))


def bmp_body():
    """自编1像素BMP及配套资源，用于单元测试和真实浏览器导入。"""
    row = b'\x00\x00\xff\x00'
    bmp = b'BM'+struct.pack('<IHHI',54+len(row),0,0,54)+struct.pack('<IiiHHIIiiII',40,1,1,1,24,0,len(row),2835,2835,0,0)+row
    text = fixture().replace('./自编_files/图.png', './自编_files/图.bmp')
    return dict(name='自编第39季.html',data=base64.b64encode(text.encode()).decode(),resources=dict(name='自编_files.zip',data=zip_data({'自编_files/图.bmp':bmp})))


class HtmlMockTest(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        home=patch.object(Path,'home',return_value=Path(t.name)/'fake-home');home.start();self.addCleanup(home.stop)
        self.p=paths.Paths(Path(t.name)/'vault','行测');self.p.ensure_train_dir()

    def snapshot(self):
        return {str(f.relative_to(self.p.vault)):f.read_bytes() for f in self.p.vault.rglob('*') if f.is_file()}

    def test_preview_readonly_commit_materials_analysis_and_repeat_preserve_notes(self):
        b=body();old=self.snapshot();r=html_mock.import_file(self.p,b)
        self.assertEqual((r['ready'],r['images'],r['missing_images'],r['blocked']),(10,1,0,0));self.assertEqual(old,self.snapshot())
        b.update(commit=True,digest=r['digest']);html_mock.import_file(self.p,b)
        qs,errors=question_bank.read(self.p,'资料分析');self.assertEqual((len(qs),errors),(10,[]))
        self.assertEqual(len({question_bank._material_group(q) for q in qs}),2)
        self.assertTrue(all('自编解析' in q['analysis'] and '不应执行' not in q['analysis'] for q in qs))
        review=next(self.p.train.glob('模考复盘/第39季/*.md'))
        self.assertEqual(len(vault.parse_board_file(review)),10)
        with review.open('a',encoding='utf-8') as f:f.write('\n> 用户自编笔记：保留。\n')
        saved=self.snapshot();again=html_mock.import_file(self.p,b)
        self.assertEqual((again['ready'],again['dup'],again['review_preserved']),(0,10,True));self.assertEqual(saved,self.snapshot())

    def test_image_options_remain_displayable_in_training(self):
        from rpg import trainer
        b=body();text=fixture().replace('<p class="input-text">自编选项A</p>','<app-format-html><img src="./自编_files/图.png"></app-format-html>',1)
        b['data']=base64.b64encode(text.encode()).decode();r=html_mock.import_file(self.p,b)
        html_mock.import_file(self.p,dict(b,commit=True,digest=r['digest']))
        question=question_bank.read(self.p,'资料分析')[0][0]
        blocks,material=trainer._bank_q(type('G',(),{'paths':self.p})(),question)
        self.assertIn('训练/题库/图片/HTML/',str(blocks))
        self.assertIn('训练/题库/图片/HTML/',str(material))

    def test_bmp_images_are_accepted_and_converted(self):
        """资源包里的BMP须能预览、提交、显示，重复导入保留用户笔记。"""
        b = bmp_body()
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(b['resources']['data']))) as z:
            self.assertEqual(html_mock._image_type(z.read('自编_files/图.bmp')), '.bmp')
        self.assertEqual(html_mock._image_type(b'BMxxxx'),'', 'BM开头但不是位图头，不当作图片')
        before = self.snapshot()
        r=html_mock.import_file(self.p,b);self.assertEqual((r['ready'],r['images'],r['missing_images']),(10,1,0))
        self.assertEqual(self.snapshot(), before, '预览不得写入文件')
        html_mock.import_file(self.p,dict(b,commit=True,digest=r['digest']))
        stored=[f for f in self.p.train.rglob('图片/HTML/*') if f.is_file()];self.assertEqual(len(stored),1)
        self.assertIn(stored[0].suffix,('.png','.bmp'))
        try:
            from PIL import Image
        except ImportError:
            self.assertEqual(stored[0].suffix, '.bmp')
        else:
            self.assertEqual(stored[0].suffix, '.png')
            with Image.open(stored[0]) as image:
                self.assertEqual(image.size, (1, 1))
                self.assertEqual(image.convert('RGB').getpixel((0, 0)), (255, 0, 0))
        review = next(self.p.train.glob('模考复盘/第39季/*.md'))
        with review.open('a', encoding='utf-8') as f:
            f.write('\n> 用户自编BMP复盘笔记。\n')
        saved = self.snapshot()
        again = html_mock.import_file(self.p, dict(b, commit=True, digest=r['digest']))
        self.assertEqual((again['ready'], again['dup'], again['review_preserved']), (0, 10, True))
        self.assertEqual(self.snapshot(), saved)

    def test_bmp_import_without_pillow_keeps_original_image(self):
        """标准库源码版不强制安装Pillow，原BMP仍能导入和保存。"""
        b = bmp_body()
        with patch.dict(sys.modules, {'PIL': None, 'PIL.Image': None}):
            preview = html_mock.import_file(self.p, b)
            self.assertEqual((preview['ready'], preview['missing_images']), (10, 0))
            html_mock.import_file(self.p, dict(b, commit=True, digest=preview['digest']))
        stored = list(self.p.train.glob('题库/图片/HTML/*.bmp'))
        self.assertEqual(len(stored), 1)
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(b['resources']['data']))) as z:
            self.assertEqual(stored[0].read_bytes(), z.read('自编_files/图.bmp'))

    def test_missing_resources_reject_commit_and_no_external_fetch(self):
        b=body();b.pop('resources');r=html_mock.import_file(self.p,b);self.assertEqual(r['missing_images'],1)
        old=self.snapshot()
        with self.assertRaises(importer.ImportError_):html_mock.import_file(self.p,dict(b,commit=True,digest=r['digest']))
        self.assertEqual(old,self.snapshot())
        b['data']=base64.b64encode(fixture().replace('./自编_files/图.png','http://127.0.0.1/secret').encode()).decode()
        self.assertEqual(html_mock.import_file(self.p,b)['missing_images'],1)

    def test_full_zip_and_resources_without_parent_folder(self):
        for files in ({'自编第39季.html':fixture().encode(),'自编_files/图.png':PNG},{'报告/自编第39季.html':fixture().encode(),'报告/自编_files/图.png':PNG}):
            r=html_mock.extract(dict(name='完整包.zip',data=zip_data(files)));self.assertEqual((len(r['questions']),len(r['images']),r['missing']),(10,1,[]))
        b=body();b['resources']['data']=zip_data({'图.png':PNG});self.assertEqual(html_mock.extract(b)['missing'],[])

    def test_zip_traversal_duplicate_html_size_and_invalid_data_rejected(self):
        for files in ({'../escape.png':PNG},{'/escape.png':PNG},{'a.html':fixture(),'b.html':fixture()}):
            with self.assertRaises(importer.ImportError_):html_mock.extract(dict(name='坏.zip',data=zip_data(files)))
        with patch.object(html_mock,'MAX_EXPANDED',1),self.assertRaises(importer.ImportError_):html_mock.extract(body())
        with self.assertRaises(importer.ImportError_):html_mock.extract(dict(name='bad.html',data='not-base64'))
        with self.assertRaises(importer.ImportError_):html_mock.extract(dict(name='bad.html',data=base64.b64encode(b'<script>1</script>').decode()))

    def test_digest_binds_season_and_rejects_changed_resource(self):
        b=body();r=html_mock.import_file(self.p,b)
        with self.assertRaises(importer.ImportError_):html_mock.import_file(self.p,dict(b,season=40,commit=True,digest=r['digest']))
        b['resources']['data']=zip_data({'自编_files/图.png':PNG+b'changed'})
        with self.assertRaises(importer.ImportError_):html_mock.import_file(self.p,dict(b,commit=True,digest=r['digest']))

    def test_image_disk_failure_keeps_original_files_and_can_retry(self):
        b=body();r=html_mock.import_file(self.p,b);old=self.snapshot()
        with patch.object(html_mock.os,'replace',side_effect=OSError('模拟磁盘失败')),self.assertRaises(OSError):
            html_mock.import_file(self.p,dict(b,commit=True,digest=r['digest']))
        self.assertEqual(old,self.snapshot())
        self.assertFalse(list(self.p.train.rglob('.html-image-*')))
        self.assertEqual(html_mock.import_file(self.p,dict(b,commit=True,digest=r['digest']))['ready'],10)

    def test_interrupted_review_write_fills_missing_board_on_retry(self):
        b=body();text=fixture().replace('<button class="answer-btn">6</button>','<div class="chapter-title">常识判断</div><button class="answer-btn">6</button>')
        b['data']=base64.b64encode(text.encode()).decode();r=html_mock.import_file(self.p,b)
        original=importer._write;calls=[]
        def interrupted(file,text):
            if '模考复盘' in str(file):
                calls.append(file)
                if len(calls)==2:raise OSError('模拟第二板块中断')
            return original(file,text)
        with patch.object(importer,'_write',side_effect=interrupted),self.assertRaises(OSError):
            html_mock.import_file(self.p,dict(b,commit=True,digest=r['digest']))
        html_mock.import_file(self.p,dict(b,commit=True,digest=r['digest']))
        review=[q for f in self.p.train.glob('模考复盘/第39季/*.md') for q in vault.parse_board_file(f)]
        self.assertEqual(len(review),10)
        self.assertEqual(len(question_bank.read(self.p,'资料分析')[0])+len(question_bank.read(self.p,'常识判断')[0]),10)

    def test_partially_saved_page_is_rejected(self):
        import re
        b=body();b['data']=base64.b64encode(re.sub(r'<app-ti>.*?</app-ti>','',fixture(),count=1,flags=re.S).encode()).decode()
        with self.assertRaisesRegex(importer.ImportError_,'部分题目'):html_mock.extract(b)

    def test_other_subject_and_duplicate_numbers_rejected(self):
        with self.assertRaises(importer.ImportError_):html_mock.import_file(paths.Paths(self.p.vault,'申论'),body())
        b=body();b['data']=base64.b64encode(fixture().replace('<div class="title-index">2.</div>','<div class="title-index">1.</div>').encode()).decode()
        with self.assertRaises(importer.ImportError_):html_mock.extract(b)
