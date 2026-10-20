"""3.5.9成语收录与清理，全部临时库/假AI；清理失败不删资料。"""
import copy,json,os,tempfile,unittest,datetime as dt
from pathlib import Path
from unittest.mock import patch
from rpg import config,engine,idioms,paths,store,trainer,question_bank,cards


class Idioms359Test(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);root=Path(t.name)
        for ctx in (patch.object(Path,'home',return_value=root/'home'),patch.dict(os.environ,{'SHENLUN_SUBJECT':'行测'})):
            ctx.start();self.addCleanup(ctx.stop)
        self.p=paths.Paths(root/'vault','行测');self.p.ensure_train_dir();day=dt.date(2026,10,20)
        self.g=engine.Game(self.p,config.Rules(),config.Persona(),config.Lines(),store.new_state(day),day)
        self.q=dict(board='逻辑填空',topic='逻辑填空',stem='自编：事业____，需要____。',options=dict(A='方兴未艾 持续',B='如火如荼 发展',C='蒸蒸日上 促进',D='崭露头角 努力'),answer='A',analysis='',key='逻辑填空::自编359',id='自编359')
    def test_tutor_immediately_harvests_idiom_and_preserves_edits(self):
        before={k:copy.deepcopy(self.g.state[k]) for k in ('xp','seconds','boss')}
        with patch.object(trainer.ai,'chat',return_value='第一空，“方兴未艾”形容事物正在兴起。第二空关注语境。') as chat:
            trainer._explain(self.g,self.q,{'answer':'B'})
        self.assertEqual(chat.call_count,1);self.assertEqual(set(idioms.data(self.g)),{'方兴未艾'})
        entry=idioms.data(self.g)['方兴未艾'];self.assertTrue(entry['sources'][0]['tutor'])
        self.assertIn('方兴未艾',self.g.state['idiom_cards'])
        idioms.edit(self.g,'方兴未艾',{'sources':{'0':{'meaning':'自己的释义','compare':'自己的辨析'}}})
        idioms.from_explanation(self.g,self.q,'重新讲解。')
        self.assertEqual((entry['sources'][0]['meaning'],entry['sources'][0]['compare']),('自己的释义','自己的辨析'))
        self.assertEqual(len(entry['sources']),1)
        for k,v in before.items():self.assertEqual(self.g.state[k],v)
        idioms.delete(self.g,'方兴未艾');idioms.from_explanation(self.g,self.q,'不要恢复主动删除。');self.assertNotIn('方兴未艾',idioms.data(self.g))
    def test_mock_review_passes_real_options_and_source_to_harvest(self):
        s=dict(board='逻辑填空',source='逻辑填空',season=33)
        q=dict(num=1,body='自编____。\n- **A.** 方兴未艾\n- **B.** 如火如荼\n- **C.** 蒸蒸日上\n- **D.** 崭露头角',correct='A',analysis='')
        pq=trainer._mreview_pq(s,q);self.assertEqual(pq['options']['A'],'方兴未艾')
        idioms.from_explanation(self.g,pq,'“方兴未艾”形容事物正在兴起。')
        self.assertEqual(idioms.data(self.g)['方兴未艾']['sources'][0]['id'],'粉笔33季-001')
    def test_cleanup_backups_short_words_cards_and_preserves_other_progress(self):
        idioms.harvest(self.g,[self.q]);valid=copy.deepcopy(idioms.data(self.g)['方兴未艾'])
        for w in ('提高','渐进性','经济发展'):
            self.g.state['idioms'][w]=dict(word=w,letter='T',added=self.g.t,sources=[dict(key='旧词',blank=1,meaning='手改',compare='旧笔记',edited=True,tutor=True)])
        ident=cards.add(self.g,dict(deck=idioms.CARD_DECK,type='问答',front='**提高**',back='旧卡'))['id']
        self.g.state.setdefault('idiom_cards',{})['提高']=ident
        self.g.state['idioms_ver']=3
        self.assertTrue(idioms.migrate(self.g));self.assertEqual(set(idioms.data(self.g)),{'方兴未艾'});self.assertEqual(idioms.data(self.g)['方兴未艾'],valid)
        backup=next((self.p.train/'词录备份').glob('*.json'));saved=json.loads(backup.read_text(encoding='utf-8'))
        self.assertEqual(set(saved['removed']),{'提高','渐进性','经济发展'});self.assertTrue(saved['files'])
        self.assertNotIn('提高',self.g.state['idiom_cards']);self.assertFalse(idioms.migrate(self.g));self.assertEqual(len(list(backup.parent.glob('*.json'))),1)
    def test_backup_failure_preserves_book_and_version(self):
        self.g.state['idioms']={'提高':dict(word='提高',sources=[])};self.g.state['idioms_ver']=3;old=copy.deepcopy(self.g.state)
        with patch.object(idioms,'backup_non_idioms',side_effect=OSError('自编磁盘失败')),self.assertRaises(OSError):idioms.migrate(self.g)
        self.assertEqual(self.g.state,old)
    def test_dictionary_excludes_short_words_and_plain_four_character_phrases(self):
        for w in ('提高','渐进性','经济发展','ABCDE'):self.assertFalse(idioms.is_word(w))
        for w in ('方兴未艾','屡禁不止','一叶障目不见泰山'):self.assertTrue(idioms.is_word(w),w)
