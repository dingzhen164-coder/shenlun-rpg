"""发布保护：只接受同SHA已成功validate构建，草稿三端资源完整才公开。"""
import unittest
from tools.publish_validated import validated_run,verify_assets


class PublishValidatedTest(unittest.TestCase):
    def run_info(self,**values):
        data=dict(id=1,head_sha='source',head_branch='validate/3.3.10-source',event='push',status='completed',conclusion='success');data.update(values);return data
    def test_failed_wrong_commit_or_non_validation_cannot_publish(self):
        for change in [dict(head_sha='old'),dict(head_branch='dev'),dict(conclusion='failure'),dict(status='in_progress'),dict(event='pull_request')]:
            with self.assertRaises(RuntimeError):validated_run([self.run_info(**change)],'source')
    def test_selects_latest_successful_validation_of_same_commit(self):
        self.assertEqual(validated_run([self.run_info(id=1),self.run_info(id=2),self.run_info(id=3,head_sha='old')],'source')['id'],2)
    def test_assets_must_all_match_before_publication(self):
        expected={'app.exe':(10000,'abc'),'app.apk':(20000,'def'),'app-mac.zip':(30000,'ghi')}
        assets=[dict(name=n,size=size,digest='sha256:'+digest) for n,(size,digest) in expected.items()]
        verify_assets(assets,expected)
        with self.assertRaises(RuntimeError):verify_assets(assets[:-1],expected)
        with self.assertRaises(RuntimeError):verify_assets(assets+[dict(name='old.zip',size=2)],expected)
        for field,value in [('size',9999),('digest','sha256:wrong')]:
            changed=[dict(a) for a in assets];changed[0][field]=value
            with self.assertRaises(RuntimeError):verify_assets(changed,expected)
