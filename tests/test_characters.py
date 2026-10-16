"""人物配置、相遇、双立绘、独立上下文和赠礼事务；临时库、假HOME，不连接AI。"""
import copy
import datetime as dt
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

_import_home = tempfile.TemporaryDirectory()
with patch.object(Path, 'home', return_value=Path(_import_home.name)):
    from rpg import characters, store


class CharactersTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = patch.object(Path, 'home', return_value=self.root / 'home')
        self.home.start(); self.addCleanup(self.home.stop)
        env = patch.dict(os.environ, {'DEEPSEEK_API_KEY':'', 'XINGCE_VAULT':'', 'SHENLUN_VAULT':'', 'SHENLUN_AI_BASE_URL':''})
        env.start(); self.addCleanup(env.stop)
        vault = self.root / '自编行测库'; vault.mkdir()
        self.g = SimpleNamespace(subject='行测', t='2026-10-16', today=dt.date(2026, 10, 16),
            state={'bag':{'护心丹':3}, 'xp':123, 'items':{}, 'seconds':{}},
            paths=SimpleNamespace(vault=vault, train=vault/'训练', subject='行测',
                                  save_dir=vault/'训练/存档', save_file=vault/'训练/存档/存档.json'),
            boards={'资料分析':{}, '数量关系':{}}, final_items=lambda board:[{'name':'自编知识点'}])
        root = characters.install(self.g)
        (root/'规则.md').write_text('- 相遇间隔分钟：30\n- 同场人数：3\n- 空场概率：0\n', encoding="utf-8")

    def body(self, g=None, scene='home'):
        g = g or self.g
        enc = characters.encounter(g, scene)
        cid = enc['characters'][0]['id']
        body = dict(id=cid, scene=scene, token=enc['token'])
        data = characters.view(g, body)
        return dict(body, revision=data['revision'], request_id='request-test-0001')

    def test_twelve_templates_and_edit_without_overwrite(self):
        p, warnings = characters.profiles(self.g)
        self.assertEqual(len(p), 12); self.assertEqual(warnings, [])
        f = characters._root(self.g)/'xc-wenjie/人物卡.md'
        f.write_text(f.read_text(encoding="utf-8").replace('文姐','自定义师姐'), encoding="utf-8")
        characters.install(self.g)
        self.assertEqual(characters.profiles(self.g)[0]['xc-wenjie']['name'], '自定义师姐')
        self.assertFalse((self.root/'home').exists())

    def test_other_subjects_and_private_scenes_do_not_initialize_state(self):
        for scene in ('notes','dwelling','settings','../home','chat'):
            with self.assertRaises(ValueError): characters.encounter(self.g, scene)
        self.assertNotIn('characters', self.g.state)
        for subject in ('申论','法考'):
            g=copy.copy(self.g);g.subject=subject;g.state={}
            with self.assertRaises(ValueError): characters.install(g)
            self.assertEqual(g.state,{})

    def test_encounter_stable_on_refresh_and_restart(self):
        one=characters.encounter(self.g,'home')
        self.assertEqual(one,characters.encounter(self.g,'home'))
        clone=copy.copy(self.g);clone.state=json.loads(json.dumps(self.g.state))
        self.assertEqual(one,characters.encounter(clone,'home'))
        self.assertTrue(all(c['id'] in characters.profiles(self.g)[0] for c in one['characters']))
        with patch.object(characters.time,'time',return_value=0):
            later=characters.encounter(clone,'home')
        self.assertNotEqual(one['token'],later['token'])

    def test_scene_allowlist_and_disabled_character(self):
        body=self.body();f=characters._root(self.g)/body['id']/'人物卡.md'
        f.write_text(f.read_text(encoding="utf-8").replace('- 启用：是','- 启用：否'), encoding="utf-8")
        with self.assertRaises(ValueError): characters.view(self.g,body)
        with self.assertRaises(ValueError): characters.view(self.g,dict(body,scene='notes'))
        with self.assertRaises(ValueError): characters.view(self.g,dict(body,id=[]))
        with self.assertRaises(ValueError): characters.view(self.g,dict(body,token='fake'))

    def test_two_portraits_and_path_boundaries(self):
        root=characters._root(self.g); cid='xc-wenjie'; d=root/cid/'立绘'
        for kind in ('three-quarter','bust'):
            (d/(cid+'-'+kind+'.png')).write_bytes(b'fake-image')
        profile=characters.profiles(self.g)[0][cid]
        self.assertEqual(set(profile['portraits']),{'three_quarter','bust'})
        self.assertIn('three-quarter',profile['portraits']['three_quarter'])
        f=root/cid/'人物卡.md';s=f.read_text(encoding="utf-8");f.write_text(s.replace('立绘/'+cid+'-bust.png','../../外部.png'), encoding="utf-8")
        p,warnings=characters.profiles(self.g)
        self.assertNotIn(cid,p);self.assertTrue(warnings)
        f.write_text(s, encoding="utf-8")
        (d/(cid+'-bust.png')).unlink()
        outside=self.root/'secret.png';outside.write_bytes(b'outside')
        try:(d/(cid+'-bust.png')).symlink_to(outside)
        except OSError:self.skipTest('不支持符号链接')
        self.assertNotIn(cid,characters.profiles(self.g)[0])

    def test_gift_deducts_once_and_survives_store_restart(self):
        b=dict(self.body(),action='gift',item='护心丹')
        r=characters.action(self.g,b)
        self.assertEqual(self.g.state['bag']['护心丹'],2)
        self.assertEqual(len(r['gifts']),1)
        self.assertEqual(characters.action(self.g,b),r)
        st=store.Store(self.g.paths);st.save(self.g.state,self.g.today)
        self.g.state=st.load(self.g.today)
        self.assertEqual(characters.action(self.g,b)['gifts'],r['gifts'])
        self.assertEqual(self.g.state['bag']['护心丹'],2)
        self.assertEqual(self.g.state['xp'],123)
        self.assertEqual(self.g.state['seconds'],{})
        with self.assertRaises(ValueError): characters.action(self.g,dict(b,item='不存在的礼物'))

    def test_gift_conflict_empty_bag_and_preferences(self):
        b=self.body(); cid=b['id'];f=characters._root(self.g)/cid/'人物卡.md'
        s=f.read_text(encoding="utf-8");s=__import__('re').sub(r'^- 喜欢礼物：.*$', '- 喜欢礼物：护心丹',s,flags=__import__('re').M);f.write_text(s, encoding="utf-8")
        r=characters.action(self.g,dict(b,action='gift',item='护心丹'))
        self.assertEqual(r['gifts'][0]['feeling'],'喜欢')
        with self.assertRaises(ValueError): characters.action(self.g,dict(b,action='gift',item='护心丹',request_id='second-request'))
        self.g.state['bag']['护心丹']=0
        current=dict(b,revision=r['revision'],request_id='third-request',action='gift',item='护心丹')
        with self.assertRaises(ValueError): characters.action(self.g,current)
        self.assertEqual(len(characters.view(self.g,b)['gifts']),1)

    def test_private_context_isolation_and_edited_persona(self):
        b=self.body();enc=characters.encounter(self.g,'home');other=next(p for p in enc['characters'] if p['id']!=b['id'])
        record=characters._person(self.g,other['id']);record['memory']='别人的私聊暗号'
        own=characters._person(self.g,b['id']);own['memory']='我的约定'
        own['messages']=[dict(role='user' if i%2==0 else 'assistant',content='消息'+str(i)) for i in range(30)]
        f=characters._root(self.g)/b['id']/'人物卡.md';f.write_text(f.read_text(encoding="utf-8").replace('- 核心表达：','- 核心表达：自定义口吻标记；'), encoding="utf-8")
        prepared=characters.prepare_chat(self.g,dict(b,action='chat',mode='dao',text='解释一个方法'))
        prompt=json.dumps(prepared['messages'],ensure_ascii=False)
        self.assertIn('我的约定',prompt);self.assertNotIn('别人的私聊暗号',prompt)
        self.assertIn('自定义口吻标记',prompt);self.assertIn('当前地点',prompt)
        self.assertEqual(len(prepared['messages']),14)
        self.assertEqual(len(own['messages']),30)

    def test_chat_commit_idempotence_empty_response_and_conflict(self):
        b=dict(self.body(),action='chat',mode='chat',text='今天有点累')
        p=characters.prepare_chat(self.g,b)
        with self.assertRaises(ValueError): characters.finish_chat(self.g,b,p,'')
        self.assertEqual(characters.view(self.g,b)['messages'],[])
        reply='<img src=x onerror=alert(1)> 自编回复'
        r=characters.finish_chat(self.g,b,p,reply)
        self.assertEqual(len(r['messages']),2)
        self.assertTrue(characters.prepare_chat(self.g,b)['duplicate'])
        self.assertEqual(characters.finish_chat(self.g,b,p,reply),r)
        next_body=dict(b,revision=r['revision'],request_id='another-request')
        p2=characters.prepare_chat(self.g,next_body)
        characters.action(self.g,dict(next_body,action='memory',memory='新的约定',request_id='memory-request'))
        with self.assertRaises(ValueError): characters.finish_chat(self.g,next_body,p2,'迟到回复')
        self.assertEqual(len(characters.view(self.g,b)['messages']),2)

    def test_memory_save_clear_and_unknown_schema_preserved(self):
        b=self.body();r=characters.action(self.g,dict(b,action='memory',memory='约定'))
        self.assertEqual(r['memory'],'约定')
        r=characters.action(self.g,dict(b,action='memory',memory='',revision=r['revision'],request_id='clear-memory'))
        self.assertEqual(r['memory'],'')
        self.g.state['characters']['schema']=999;before=copy.deepcopy(self.g.state)
        with self.assertRaises(ValueError):characters.view(self.g,b)
        self.assertEqual(before,self.g.state)

    def test_invalid_card_does_not_hide_other_people(self):
        f=characters._root(self.g)/'xc-wenjie/人物卡.md';f.write_bytes(b'\xff')
        people,warnings=characters.profiles(self.g)
        self.assertEqual(len(people),11);self.assertTrue(warnings)


if __name__ == '__main__':
    unittest.main()
