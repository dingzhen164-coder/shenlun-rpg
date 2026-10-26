"""多老师ZIP分发、完整正文、旧数据保留、历史与讲题隔离；只用临时库/假AI。"""
import io
import hashlib
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from rpg import api, paths, skillbook, trainer


def package(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buf.getvalue()


class TeachersTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for ctx in (patch.object(Path, 'home', return_value=root/'home'), patch.dict(os.environ, {'SHENLUN_SUBJECT':'行测'}),
                    patch.object(paths, 'SETTINGS_DIR', root/'settings'), patch.object(paths, 'SETTINGS_FILE', root/'settings/settings.json')):
            ctx.start(); self.addCleanup(ctx.stop)
        self.p = paths.Paths(root/'vault', '行测'); (self.p.vault/'copilot/skills').mkdir(parents=True);self.p.ensure_train_dir()
        paths.save_settings({'subject':'行测','vaults':{'行测':str(self.p.vault)}})
        with api.open_game(save=False) as g:
            self.boards = api._skill_boards(g)

    def test_filename_combinations_and_unknown_names(self):
        for name, who, boards in [('大懒猫-言语.md','大懒猫',{'逻辑填空','片段阅读'}),
                                  ('句号-资料言语.md','句号',{'资料分析','逻辑填空','片段阅读'})]:
            t, bs = skillbook.filename_teacher(name, self.boards)
            self.assertEqual(t, who); self.assertEqual(set(bs), boards)
        _, bs = skillbook.filename_teacher('青菜白玉汤-判断.md', self.boards)
        self.assertTrue({'图形推理','定义判断','类比推理','论证逻辑','形式逻辑'}.issubset(bs))
        for bad in ['文档.md','老师-未知言语.md','../-言语.md','原有心法-言语.md']:
            with self.assertRaises(skillbook.SkillError):
                skillbook.filename_teacher(bad, self.boards)

    def test_actual_package_aliases_years_and_collection(self):
        expected={'刘一恒-图推.md':('刘一恒',{'图形推理'}),'聂佳-类比.md':('聂佳',{'类比推理'}),
                  '李焕-逻辑.md':('李焕',{'论证逻辑','形式逻辑','一拖五'}),
                  '小P-27资料.md':('小P',{'资料分析'}),'薛睿-判断（最新）.md':('薛睿',{'论证逻辑','形式逻辑','一拖五','定义判断','类比推理','图形推理'}),
                  '小黑-政常.md':('小黑',{'政治理论','常识判断'}),'小y-政治.md':('小y',{'政治理论'})}
        for filename,(who,bs) in expected.items():
            teacher,boards=skillbook.filename_teacher(filename,self.boards)
            self.assertEqual(teacher,who);self.assertEqual(set(boards),bs)
        teacher,boards=skillbook.filename_teacher('超格全家桶.md',self.boards)
        self.assertEqual(teacher,'超格全家桶');self.assertEqual(len(boards),10)
        self.assertNotIn('政治理论',boards)
        for filename in ('老师-申论.md','老师-面试.md','老师-综应A.md','老师-公安专业科目.md'):
            with self.assertRaises(skillbook.SkillError):skillbook.filename_teacher(filename,self.boards)

    def test_mac_zip_utf8_names_without_flag_are_not_misdecoded_as_gbk(self):
        raw=bytearray(package({'大懒猫-言语.md':'完整原文\r\n第二行\r\n','__MACOSX/._大懒猫-言语.md':'系统附带数据'}))
        for marker,offset in ((b'PK\x03\x04',6),(b'PK\x01\x02',8)):
            pos=0
            while True:
                pos=raw.find(marker,pos)
                if pos<0:break
                flags=int.from_bytes(raw[pos+offset:pos+offset+2],'little')&~0x800
                raw[pos+offset:pos+offset+2]=flags.to_bytes(2,'little');pos+=4
        entries,skipped=skillbook._package_entries('Mac.zip',bytes(raw),True)
        self.assertEqual(entries,[('大懒猫-言语.md','完整原文\r\n第二行\r\n')]);self.assertEqual(skipped,[])
        result=skillbook.import_teachers(self.p,self.boards,'Mac.zip',bytes(raw))
        self.assertEqual(result['items'][0]['teacher'],'大懒猫');self.assertEqual(len(result['added']),2)
        repeated=skillbook.import_teachers(self.p,self.boards,'Mac.zip',bytes(raw))
        self.assertEqual(len(repeated['same']),2);self.assertEqual(repeated['overwritten'],[])

    def test_preview_full_copies_and_legacy_not_overwritten(self):
        skillbook.save(self.p, '逻辑填空', 'SKILL.md', '# 原有内容', '')
        text = '# 完整文档\n资料与言语所有内容\n' + '不是节选。'*300
        raw = package({'bundle/句号-资料言语.md':text,'bundle/大懒猫-言语.md':'# 猫老师','bundle/未知.md':'不要猜','bundle/../../越界-言语.md':'坏路径'})
        preview = skillbook.import_teachers(self.p,self.boards,'老师.zip',raw,True)
        self.assertEqual(len(preview['items']),2); self.assertEqual(len(preview['skipped']),2)
        self.assertEqual(skillbook.own_files(self.p,'资料分析'),[])
        result = skillbook.import_teachers(self.p,self.boards,'老师.zip',raw)
        self.assertEqual(len(result['added']),5)
        for b in ('资料分析','逻辑填空','片段阅读'):
            self.assertEqual(skillbook.read_file(self.p,b,'老师/句号/句号-资料言语.md')['text'],text)
        self.assertEqual(skillbook.read_file(self.p,'逻辑填空','SKILL.md')['text'],'# 原有内容')
        self.assertEqual(skillbook.tutor_material(self.p,'逻辑填空')[0],'=== SKILL.md ===\n# 原有内容')
        digest, _ = skillbook.tutor_material(self.p,'逻辑填空','句号')
        self.assertIn(text,digest); self.assertNotIn('猫老师',digest); self.assertNotIn('原有内容',digest)

    def test_reimport_history_no_duplicate_and_cache_is_per_teacher(self):
        raw=package({'大懒猫-言语.md':'猫老师旧版','句号-言语.md':'句号内容'})
        skillbook.import_teachers(self.p,self.boards,'老师.zip',raw)
        self.assertEqual(len(skillbook.import_teachers(self.p,self.boards,'老师.zip',raw)['same']),4)
        p1=skillbook.plan(self.p,'逻辑填空','大懒猫');p2=skillbook.plan(self.p,'逻辑填空','句号')
        self.assertNotEqual(p1['items'][0]['rel'],p2['items'][0]['rel'])
        r=skillbook.import_teachers(self.p,self.boards,'大懒猫-言语.md','猫老师新版'.encode())
        self.assertEqual(len(r['overwritten']),2)
        hist=skillbook.history(self.p,'逻辑填空','老师/大懒猫/大懒猫-言语.md')
        self.assertEqual(skillbook.history_text(self.p,'逻辑填空','老师/大懒猫/大懒猫-言语.md',hist[0]['id']),'猫老师旧版')
        with self.assertRaises(skillbook.SkillError):
            skillbook.tutor_material(self.p,'资料分析','大懒猫')

    def test_teacher_choice_does_not_call_ai_and_explain_only_reads_selected(self):
        skillbook.import_teachers(self.p,self.boards,'老师.zip',package({'大懒猫-言语.md':'猫专属标记','句号-言语.md':'句号专属标记'}))
        with api.open_game(save=False) as g:
            s=trainer.new_session('wrong','自编复盘',{},board='逻辑填空')
            self.addCleanup(lambda:trainer.SESSIONS.pop(s['id'],None))
            with patch.object(trainer.ai,'chat',side_effect=AssertionError('选择不能调用AI')):
                r=trainer.action(g,s['id'],'skill_teacher:句号')
            self.assertEqual(r['mentor']['name'],'句号');self.assertEqual(r['skill_teachers']['selected'],'句号')
            self.assertTrue(r['mentor']['avatar'].endswith('full-stop.png'))
            with self.assertRaises(trainer.TrainError):
                trainer.action(g,s['id'],'skill_teacher:不存在')
            with patch.object(trainer.ai,'chat',return_value='自编讲解') as chat, patch.object(trainer.idioms,'from_explanation'):
                trainer._explain(g,{'board':'逻辑填空','stem':'自编题干','options':{'A':'自编A','B':'自编B'},'answer':'绝密答案','analysis':'绝密解析'}, {}, '句号')
                sent=str(chat.call_args[0][0]);self.assertIn('句号专属标记',sent);self.assertNotIn('猫专属标记',sent)
                self.assertNotIn('绝密答案',sent);self.assertNotIn('绝密解析',sent)

    def test_input_limits_and_archive_errors(self):
        with self.assertRaises(skillbook.SkillError):
            skillbook.import_teachers(self.p,self.boards,'老师.zip',b'PKbad')
        with self.assertRaises(skillbook.SkillError):
            skillbook.import_teachers(self.p,self.boards,'老师.zip',package({'大懒猫-言语.md':'x'*(skillbook.MAX_FILE+1)}))

    def test_long_method_is_saved_in_full_and_retrieved_by_question_with_ranges(self):
        text=('# 无关章节\n天气晴朗。\n\n'*5000)+'# 增长率章节\n增长率等于增长量除以基期量。先识别现期量、基期量与同比增长。\n\n'+('其他内容。\n\n'*1000)
        raw=package({'花生-资料.md':text,'林凡-资料.md':'不能混进来的另一位老师'})
        skillbook.import_teachers(self.p,self.boards,'长文.zip',raw)
        self.assertEqual(skillbook.read_file(self.p,'资料分析','老师/花生/花生-资料.md')['text'],text)
        plan=skillbook.plan(self.p,'资料分析','花生');self.assertTrue(plan['items'][0]['retrievable']);self.assertFalse(plan['items'][0]['read'])
        digest,used=skillbook.tutor_material(self.p,'资料分析','花生','同比增长率与基期量如何计算？')
        self.assertIn('增长率等于增长量除以基期量',digest);self.assertNotIn('不能混进来',digest)
        self.assertLessEqual(len(digest),skillbook.TUTOR_LIMIT);self.assertIn('非全文',used[0]);self.assertIn('原文第',digest)
        self.assertEqual(skillbook.tutor_material(self.p,'资料分析','花生','XYZNOHITZZ')[0],'')

    def test_encodings_and_avatar_assets(self):
        raw=package({'大懒猫-言语.md':'完整GBK正文'.encode('gb18030'),'句号-资料.md':'\ufeff完整UTF8正文'})
        skillbook.import_teachers(self.p,self.boards,'老师.zip',raw)
        self.assertIn('完整GBK正文',skillbook.tutor_material(self.p,'逻辑填空','大懒猫')[0])
        self.assertIn('完整UTF8正文',skillbook.tutor_material(self.p,'资料分析','句号')[0])
        from PIL import Image
        for who in ('大懒猫','青菜白玉汤','句号'):
            f=Path(__file__).resolve().parent.parent/'web'/skillbook.teacher_avatar(who)
            with Image.open(f) as im:
                self.assertEqual(im.width,im.height);self.assertGreaterEqual(im.width,512)
                self.assertIn('A',im.getbands());self.assertEqual(im.getpixel((0,0))[-1],0)

    def test_complete_actual_teacher_catalog_has_distinct_avatar_paths(self):
        self.assertEqual(len(skillbook.AVATARS),58)
        files=[r['file'] for r in skillbook.AVATARS.values()]
        self.assertEqual(len(set(files)),58)
        for name in skillbook.AVATARS:
            self.assertTrue(skillbook.teacher_avatar(name).startswith('assets/teachers/'))
        web=Path(__file__).resolve().parent.parent/'web'
        provenance=json.loads((web/'assets/teachers/provenance.json').read_text(encoding='utf-8'))
        self.assertEqual({r['name'] for r in provenance['items']},set(skillbook.AVATARS))
        from PIL import Image
        hashes=set()
        for row in provenance['items']:
            f=web/skillbook.teacher_avatar(row['name']);digest=hashlib.sha256(f.read_bytes()).hexdigest()
            self.assertEqual(digest,row['sha256']);hashes.add(digest)
            with Image.open(f) as im:
                self.assertEqual(im.width,im.height);self.assertGreaterEqual(im.width,512)
                self.assertIn('A',im.getbands())
        self.assertEqual(len(hashes),58,'每位老师独立头像，不以重复文件占位')

