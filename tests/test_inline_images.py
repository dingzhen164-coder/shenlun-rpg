"""标准库尺寸识别、公式与大图分流，临时自编图，不改原题/图片。"""
import datetime as dt,struct,tempfile,unittest,zlib
from pathlib import Path
from unittest.mock import patch
from rpg import config,engine,inline_images,paths,store,trainer,vault


def png(w,h):
    def chunk(t,d):return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
    raw=b''.join(b'\0'+b'\xff\xff\xff'*w for _ in range(h))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')


class InlineImagesTest(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);root=Path(t.name)
        ctx=patch.object(Path,'home',return_value=root/'home');ctx.start();self.addCleanup(ctx.stop)
        self.p=paths.Paths(root/'vault');self.p.ensure_train_dir();self.folder=self.p.train/'题库/图片/题目图';self.folder.mkdir(parents=True,exist_ok=True)
        for name,w,h in [('小公式.png',70,48),('统计表.png',800,550),('图形.png',450,180)]: (self.folder/name).write_bytes(png(w,h))
        self.rel=lambda n:(self.folder/n).relative_to(self.p.vault).as_posix()
        day=dt.date(2026,10,20);self.g=engine.Game(self.p,config.Rules(),config.Persona(),config.Lines(),store.new_state(day),day)
    def test_formula_stays_in_same_sentence_and_options_not_merged(self):
        rel=self.rel('小公式.png');text='自编值为\n![[%s]]\n倍，选正确项。\nA. 甲\nB. 乙'%rel
        before=(self.folder/'小公式.png').read_bytes()
        for result in (trainer._bank_blocks(self.g,next(iter(self.g.boards)),text),vault.text_blocks(self.p,None,text)):
            self.assertEqual([b['t'] for b in result],['text']);self.assertIn('值为![[%s]]倍'%rel,result[0]['v']);self.assertIn('\nA. 甲\nB. 乙',result[0]['v'])
        self.assertEqual(before,(self.folder/'小公式.png').read_bytes())
    def test_cropper_blank_lines_inside_sentence_do_not_split_formula(self):
        rel=self.rel('小公式.png');text='值为\n\n![[%s]]\n\n倍，继续读。'%rel
        for result in (trainer._bank_blocks(self.g,next(iter(self.g.boards)),text),vault.text_blocks(self.p,None,text)):
            self.assertIn('值为![[%s]]倍'%rel,result[0]['v'])

    def test_tables_and_figures_remain_full_blocks(self):
        for name in ('统计表.png','图形.png'):
            text='自编图：\n![[%s]]\n阅读后回答。'%self.rel(name)
            for result in (trainer._bank_blocks(self.g,next(iter(self.g.boards)),text),vault.text_blocks(self.p,None,text)):
                self.assertEqual([b['t'] for b in result],['text','img','text'])
    def test_new_file_revision_invalidates_size_cache(self):
        rel=self.rel('小公式.png');self.assertTrue(inline_images.small(self.p,rel));(self.folder/'小公式.png').write_bytes(png(500,200));self.assertFalse(inline_images.small(self.p,rel))
    def test_invalid_and_outside_images_not_guessed(self):
        (self.folder/'坏图.png').write_bytes(b'bad');self.assertIsNone(inline_images.small(self.p,self.rel('坏图.png')))
        self.assertIsNone(inline_images.small(self.p,'../outside.png'))
    def test_multiple_inline_images_keep_text_and_paragraphs(self):
        rel=self.rel('小公式.png');text='甲![[%s]]乙![[%s]]丙\n\nA. ![[%s]]\nB. 乙'%(rel,rel,rel)
        result=vault.text_blocks(self.p,None,text);self.assertEqual(len(result),1);self.assertEqual(result[0]['v'].count('![['),3);self.assertIn('\n\nA.',result[0]['v']);self.assertIn('\nB.',result[0]['v'])
