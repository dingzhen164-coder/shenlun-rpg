"""成绩识图解析：仅自编文字/假OCR，保留小数与排名，不猜丢失的点号。"""
import unittest
from unittest.mock import patch
from rpg import report


class ReportDecimalTest(unittest.TestCase):
    def test_decimal_formats_and_split_font(self):
        for text in ('得分\n70.6','得分 70 . 6','得分７０．６','得分70·6','得分70,6','得分\n70\n.6','得分\n70.\n6','70.6/100得分','70.6/100\n我的得分'):
            with self.subTest(text=text):self.assertEqual(report.parse(text)['fields']['score'],'70.6')

    def test_rank_and_two_decimal_score_not_truncated(self):
        f=report.parse('得分70.45\n93.7 55.8 10791/44774\n最高分 平均分 排名')['fields']
        self.assertEqual((f['score'],f['top'],f['avg'],f['rank'],f['people']),('70.45','93.7','55.8','10791','44774'))
        self.assertNotEqual(report.parse('得分\n70 6')['fields'].get('score'),'70.6')

    def test_fake_image_ocr_pipeline_keeps_decimal(self):
        with patch.object(report,'ocr',return_value='得分\n70\n.6'):
            self.assertEqual(report.scan([b'fake-image'])['fields']['score'],'70.6')

    def test_optional_question_time_format_shared_with_law(self):
        from rpg import vault
        for text,value in [('1分25秒',85),('0秒',0),('1:25',85),('未知',None)]:self.assertEqual(vault.parse_seconds(text),value)
