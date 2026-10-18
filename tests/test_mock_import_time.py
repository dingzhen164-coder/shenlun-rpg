"""模考入库计时：临时库/假HOME，首次一次、补导入零次，兼容缺标记的旧记录。"""
import copy
import datetime as dt
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from rpg import api,config,engine,importer,mock,paths,store


class MockImportTimeTest(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);root=Path(t.name)
        ctx=patch.object(Path,'home',return_value=root/'home');ctx.start();self.addCleanup(ctx.stop)
        self.p=paths.Paths(root/'vault');self.p.ensure_train_dir()
        today=dt.date(2026,10,18)
        self.g=engine.Game(self.p,config.Rules(),config.Persona(),config.Lines(),store.new_state(today),today)
        @contextmanager
        def game(**kwargs):yield self.g
        for ctx in (patch.object(api,'open_game',game),patch.object(api,'_import_paths',return_value=self.p),patch.object(api.tutor,'enrich',side_effect=lambda g,e:e)):
            ctx.start();self.addCleanup(ctx.stop)

    def test_first_import_once_even_if_followed_by_pdf_or_html(self):
        first=api._mock_imported({},33);self.assertEqual(first['practice_minutes'],120)
        before=copy.deepcopy(self.g.state)
        self.assertNotIn('practice_minutes',api._mock_imported({},33))
        self.assertEqual(self.g.state,before)
        api._mock_imported({},34);self.assertEqual(self.g.minutes(self.g.t),240)
        self.assertEqual(len(self.g.state['practice']),2)

    def test_supplement_without_marker_never_adds_minutes_xp_or_events(self):
        before=copy.deepcopy(self.g.state)
        with patch.object(importer,'commit',return_value={'ready':2,'dup':128}):
            for _ in range(2):
                rep=api.import_commit({'kind':'season','season':33});self.assertNotIn('practice_minutes',rep);self.assertNotIn('events',rep)
        for key in ('seconds','practice','xp','events','boss'):self.assertEqual(self.g.state[key],before[key],key)
        self.assertEqual(self.g.state['mock_practice'],['33'])
        api._mock_imported({},33);self.assertEqual(self.g.state['seconds'],before['seconds'])

    def test_old_practice_log_or_integer_marker_prevents_recredit(self):
        self.g.state['practice'].append(dict(d=self.g.t,minutes=120,source='粉笔第33季模考',board='模考',total=130,correct=90))
        before=copy.deepcopy(self.g.state)
        api._mock_imported({},33)
        for key in ('seconds','practice','xp','events'):self.assertEqual(self.g.state[key],before[key])
        self.g.state['mock_practice']=[34]
        before=copy.deepcopy(self.g.state);api._mock_imported({},34);self.assertEqual(self.g.state,before)

    def test_failed_supplement_never_marks_or_counts(self):
        before=copy.deepcopy(self.g.state)
        with patch.object(importer,'commit',side_effect=importer.ImportError_('自编失败')),self.assertRaises(api.ApiError):api.import_commit({'kind':'season','season':33})
        self.assertEqual(self.g.state,before)
