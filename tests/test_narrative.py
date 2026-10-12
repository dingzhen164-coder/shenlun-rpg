"""纪事：旧档迁移、服务端学习条件、CAS并发、续读/重播与数据边界。用内存假库。"""
import copy
import datetime as dt
import unittest
from types import SimpleNamespace
from rpg import narrative


class NarrativeTest(unittest.TestCase):
    def game(self, world=None, **state):
        wid = world or next(iter(narrative.DEFINITIONS))
        return SimpleNamespace(subject={'mage':'法考', 'xingce':'行测', 'office':'申论'}[wid],
                               state=state, today=dt.date(2026, 10, 12), persona={'导师名':'周静宜'})

    def command(self, g, action, cid='prologue', choice=None):
        r = narrative.act(g, {}, {'action':'open', 'world':narrative.world_id(g), 'chapter':cid})
        body = dict(world=r['world'], action=action, chapter=cid, node=r['scene']['node'], revision=r['revision'])
        if choice: body['choice'] = choice
        return narrative.act(g, {}, body)

    def test_initialized_items_and_xp_do_not_unlock(self):
        g = self.game(items={'x':{'last':None, 'level':0}}, xp=9999, seconds={'d':float('inf')})
        r = narrative.view(g, {})
        self.assertFalse(r['facts']['learned'])
        self.assertEqual(r['memories'], [])
        with self.assertRaises(ValueError): self.command(g, 'skip', 'study_echo')
        self.assertEqual(g.state['xp'], 9999)

    def test_choice_gate_cannot_be_forged(self):
        g = self.game(xp=18, bank={'records':{}}, seconds={})
        before = copy.deepcopy(g.state)
        with self.assertRaises(ValueError): self.command(g, 'choose', choice='recorded')
        with self.assertRaises(ValueError): self.command(g, 'finish')
        for k in before: self.assertEqual(before[k], g.state[k])
        self.assertEqual(narrative.view(g,{})['revision'], 0)
        g.state['seconds']['today']=30
        r=self.command(g,'choose',choice='recorded')
        self.assertEqual(r['scene']['node'],'prologue_recorded')
        self.assertEqual(len(r['memories']),1)

    def test_resume_conflict_and_duplicate_finish(self):
        g=self.game(xp=23, seconds={}, plan={'tasks':[]})
        r=self.command(g,'choose',choice='practice')
        saved=copy.deepcopy(g.state)
        clone=self.game(**saved)
        reopened=narrative.act(clone,{},dict(world=r['world'],action='open',chapter='prologue'))
        self.assertEqual(reopened['scene'],r['scene'])
        stale=dict(world=r['world'],chapter='prologue',node=r['scene']['node'],revision=r['revision'],action='choose',choice='continue')
        r=narrative.act(g,{},stale)
        after=copy.deepcopy(g.state)
        with self.assertRaises(ValueError): narrative.act(g,{},stale)
        self.assertEqual(g.state,after)
        r=self.command(g,'finish')
        finish=dict(world=r['world'],chapter='prologue',node=r['scene']['node'],revision=r['revision']-1,action='finish')
        with self.assertRaises(ValueError): narrative.act(g,{},finish)
        self.assertTrue(r['scene']['read'])
        self.assertEqual(g.state['xp'],23)
        self.assertEqual(g.state['seconds'],{})
        self.assertEqual(g.state['plan'],{'tasks':[]})

    def test_skip_replay_retains_first_dialogue_and_memory(self):
        g=self.game(seconds={'d':1},xp=4)
        self.command(g,'choose',choice='understand')
        self.command(g,'choose',choice='continue')
        completed=self.command(g,'finish')
        record=copy.deepcopy(completed['scene']['record'])
        replay=self.command(g,'replay')
        self.assertEqual(replay['scene']['node'],'prologue_start')
        self.assertTrue(replay['scene']['read'])
        self.command(g,'choose',choice='practice')
        result=self.command(g,'skip')
        self.assertEqual(result['scene']['record'],record)
        self.assertEqual(len(result['memories']),1)
        self.assertEqual(g.state['xp'],4)

    def test_unlock_persists_and_world_is_checked(self):
        g=self.game(seconds={'d':60})
        r=narrative.view(g,{})
        self.assertTrue(r['chapters'][1]['unlocked'])
        g.state['seconds']={}
        self.assertTrue(narrative.view(g,{})['chapters'][1]['unlocked'])
        with self.assertRaises(ValueError):
            narrative.act(g,{},dict(world='unknown',chapter='prologue',action='skip',revision=r['revision']))
        for cid in (['prologue'],'missing',None):
            with self.assertRaises(ValueError): self.command(g,'open',cid)

    def test_legacy_five_chapters_preserved(self):
        if 'xingce' not in narrative.DEFINITIONS: self.skipTest('法考没有宗门旧剧情')
        legacy={'schema':1,'unlocked':['arrival','five_paths','tower'], 'read':['arrival','five_paths','tower']}
        g=self.game('xingce',sect_story=copy.deepcopy(legacy))
        r=narrative.view(g,{})
        self.assertTrue(all(c['read'] for c in r['chapters']))
        self.assertEqual(g.state['sect_story'],legacy)
        self.command(g,'replay');self.command(g,'skip')
        self.assertEqual(g.state['sect_story'],legacy)

    def test_office_leader_and_subject_data_are_separate(self):
        if 'office' not in narrative.DEFINITIONS: self.skipTest('法考无申论领导')
        a=self.game('xingce',seconds={'d':1})
        b=self.game('office')
        self.command(a,'skip')
        r=narrative.view(b,{'career':{'leader':{'name':'陈知微','title':'主任'}}})
        self.assertEqual(r['profile']['character'],'陈知微')
        self.assertEqual(r['profile']['role'],'主任')
        self.assertFalse(r['chapters'][0]['read'])
        self.assertEqual(r['memories'],[])

    def test_unknown_future_schema_is_not_overwritten(self):
        g=self.game(narrative={'schema':99,'worlds':{}})
        old=copy.deepcopy(g.state)
        with self.assertRaises(ValueError): narrative.view(g,{})
        self.assertEqual(old,g.state)

if __name__=='__main__': unittest.main()
