"""整卷拆分·版面版：没有文字层的扫描试卷PDF按版面拆成“每题一张图”。自编页面（用方块代替文字）+ 假OCR，不碰真题，不连网。"""
import os
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from rpg import exam_scan as scan, mock, vault

try:
    import pymupdf as fitz
except ImportError:      # pragma: no cover
    fitz = None


def L(text, x0, y0, x1=None, h=.016):
    return {"t": text, "x0": x0, "y0": y0, "x1": x1 or min(.9, x0+.02*len(text)), "y1": y0+h}


def footer(n):
    return L("第%d页 共3页" % n, .43, .93, .57)


# 3页自编卷：政治理论3题（第1题题号丢了）、判断推理4题（图形推理+定义判断小节）、资料分析2题（一组材料）
PAGES = [
    [L("第一部分", .36, .11, .49), L("政治理论", .51, .11, .64), L("（共3题，参考时间：12分钟）", .36, .15, .64),
     L("坚持和发展中国特色社会主义的说法正确的是：", .14, .22), L("A．甲", .14, .25), L("B．乙", .14, .28), L("C．丙", .14, .31), L("D．丁", .14, .34),
     L("2．关于两个确立，下列表述正确的是：", .10, .40), L("A．甲", .14, .43), L("B．乙", .14, .46), L("C．丙", .14, .49), L("D．丁", .14, .52),
     L("3．以下说法中，错误的一项是：", .10, .80), L("A．甲", .14, .83), L("B．乙", .14, .86), footer(1)],
    [L("C．丙", .14, .09), L("D．丁", .14, .12), L("※※※第一部分结束，请继续做第二部分！", .23, .20, .67),
     L("第二部分", .36, .30, .49), L("判断推理", .51, .30, .64), L("（共4题，参考时间：30分钟）", .36, .34, .64),
     L("一、图形推理", .14, .40, .30),
     L("4．从所给的四个选项中，选择最合适的一个填入问号处：", .10, .44), L("5．把下面的图形分为两类：", .10, .66), footer(2)],
    [L("二、定义判断", .14, .09, .30),
     L("6．下列属于该定义的是：", .10, .13), L("A．甲", .14, .16), L("B．乙", .14, .19), L("C．丙", .14, .22), L("D．丁", .14, .25),
     L("7．", .10, .30), L("A．甲", .14, .33), L("B．乙", .14, .36), L("C．丙", .14, .39), L("D．丁", .14, .42),
     L("※※※第二部分结束，请继续做第三部分！", .23, .50, .67),
     footer(3)],
]
PAGES_C = [  # 资料分析部分单独一页
    [L("第三部分", .36, .11, .49), L("资料分析", .51, .11, .64), L("（共2题，参考时间：27分钟）", .36, .15, .64),
     L("一、根据所给材料，回答8～9题。", .14, .20, .50), L("某市2022年工业总产值同比增长9.6%。", .14, .24), L("请回答8～9题", .14, .30, .31),
     L("8．2022年总产值增速为：", .10, .34), L("A．甲", .14, .37), L("B．乙", .14, .40), L("C．丙", .14, .43), L("D．丁", .14, .46),
     L("9．下列说法正确的是：", .10, .50), L("A．甲", .14, .53), L("B．乙", .14, .56), L("C．丙", .14, .59), L("D．丁", .14, .62),
     L("※※※全部测验到此结束！", .30, .85, .67), footer(4)]]


def make_pdf(path, pages):
    doc = fitz.open()
    for lines in pages:
        page = doc.new_page(width=595, height=842)
        for l in lines:
            page.draw_rect(fitz.Rect(l["x0"]*595, l["y0"]*842, l["x1"]*595, l["y1"]*842), color=None, fill=(0, 0, 0))
    doc.save(str(path))
    doc.close()


@unittest.skipIf(fitz is None, "缺PDF组件")
class ScanTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.pages = PAGES + PAGES_C

    def test_analyze_finds_every_question_even_when_the_number_line_is_lost(self):
        r = scan.analyze(self.pages)
        self.assertEqual([q["num"] for q in r["questions"]], list(range(1, 10)))
        self.assertEqual(r["missing"], [])
        self.assertEqual([(p["name"], p["start"], p["end"]) for p in r["parts"]], [("政治理论", 1, 3), ("判断推理", 4, 7), ("资料分析", 8, 9)])
        boards = {q["num"]: q["board"] for q in r["questions"]}
        self.assertEqual([boards[n] for n in range(1, 10)], ["政治理论"]*3+["图形推理"]*2+["定义判断"]*2+["资料分析"]*2)
        virtual = {q["num"] for q in r["questions"] if q["virtual"]}
        self.assertEqual(virtual, {1}, "题号丢了的第1题从本部分第一行内容开始")
        self.assertEqual([(m["a"], m["b"]) for m in r["materials"]], [(8, 9)])

    def test_cover_page_part_lines_without_a_count_do_not_crash(self):
        # 花生26下1期：封面/目录里有“第一部分 政治理论”这类没有“共M题”的行，下一个“第N部分”曾因 None+1 报“程序出错”
        cover = [[L("第一部分 政治理论", .1, .2, .5), L("第二部分 判断推理", .1, .25, .5), L("第三部分 资料分析", .1, .3, .5), footer(0)]]
        r = scan.analyze(cover+self.pages)
        self.assertEqual([(p["name"], p["start"], p["end"]) for p in r["parts"]], [("政治理论", 1, 3), ("判断推理", 4, 7), ("资料分析", 8, 9)])
        self.assertEqual(r["missing"], [])

    def test_part_name_and_count_on_one_line(self):
        same = [[L("第一部分 政治理论（共3题）", .1, .11, .7)]+PAGES[0][2:]]+PAGES[1:]
        r = scan.analyze(same+PAGES_C)
        self.assertEqual([(p["name"], p["start"], p["end"]) for p in r["parts"]], [("政治理论", 1, 3), ("判断推理", 4, 7), ("资料分析", 8, 9)])
        self.assertEqual(r["missing"], [])

    def test_regions_split_across_pages_and_stop_at_boundaries(self):
        r = scan.analyze(self.pages)
        q = {x["num"]: x for x in r["questions"]}
        self.assertEqual([s[0] for s in q[3]["segments"]], [0, 1], "第3题跨页：第1页下半 + 第2页开头")
        self.assertLess(q[3]["segments"][1][2], .2, "到“第一部分结束”为止，不带进下一部分")
        self.assertEqual([s[0] for s in q[4]["segments"]], [1], "第4题只有题干，选项在图里：到下一题题号为止，整块都在")
        self.assertGreater(q[4]["segments"][0][2]-q[4]["segments"][0][1], .15)
        self.assertEqual(q[7]["segments"][0][2] < .5, True, "最后一题到部分结束标记为止")
        self.assertEqual([s[0] for s in r["materials"][0]["segments"]], [3])
        self.assertLess(r["materials"][0]["segments"][0][2], q[8]["y0"]+.001, "材料到第8题开头为止，含“请回答”那行")

    def test_numbers_out_of_order_are_not_questions(self):
        pages = [[L("第一部分", .36, .11), L("政治理论", .51, .11), L("（共2题", .36, .15), L("1．题一", .10, .2), L("A．1.5倍", .14, .24), L("10．这不是题", .10, .30), L("2．题二", .10, .40), footer(1)]]
        r = scan.analyze(pages)
        self.assertEqual([q["num"] for q in r["questions"]], [1, 2])

    def test_no_numbers_is_a_clear_error(self):
        with self.assertRaises(scan.ScanError):
            scan.analyze([[L("第一部分", .36, .11), L("政治理论", .51, .11), L("（共2题", .36, .15), L("随便写点什么", .1, .3)]])

    def test_verbal_boards_follow_the_fixed_order_and_garbled_questions_do_not_break_it(self):
        labels = ["逻辑填空", None, "逻辑填空", "片段阅读", None, "片段阅读", "语句排序", "逻辑填空", "语句排序"]
        self.assertEqual(scan._monotone(labels), ["逻辑填空"]*3+["片段阅读"]*3+["语句排序"]*3)
        self.assertEqual(scan.classify_verbal("依次填入画横线部分最恰当的一项是"), "逻辑填空")
        self.assertEqual(scan.classify_verbal("将以下句子重新排列"), "语句排序")
        self.assertIsNone(scan.classify_verbal("“，‘““，8"))

    def test_split_writes_review_files_and_images_that_the_exam_room_reads(self):
        pdf = self.root/"自编扫描卷.pdf"
        make_pdf(pdf, self.pages)
        by_file = {}
        def engine(path):
            by_file[path] = 1
            return self.pages[int(re.search(r"p(\d+)\.png", path).group(1))]
        pp = SimpleNamespace(train=self.root/"训练")
        report = scan.split(pp, pdf, 1001, engine=engine)
        self.assertEqual((report["found"], report["total"], report["missing"]), (9, 9, []))
        self.assertEqual(report["modules"], {"政治理论": 3, "判断推理": 4, "资料分析": 2})
        folder = pp.train/"模考复盘/第1001季"
        files = sorted(f.name for f in folder.glob("[0-9][0-9]-*.md"))
        self.assertEqual(files, ["01-政治理论.md", "02-图形推理.md", "03-定义判断.md", "04-资料分析.md"])
        qs = {q["num"]: q for f in folder.glob("[0-9][0-9]-*.md") for q in vault.parse_board_file(f)}
        self.assertEqual(sorted(qs), list(range(1, 10)))
        self.assertTrue(all(q["icon"] == "⚪" and q["correct"] == "" for q in qs.values()), "答案都还没有")
        self.assertEqual(len(re.findall(r"!\[\[Q003-\d\.jpg\]\]", qs[3]["body"])), 2, "跨页的题两张图")
        self.assertEqual(qs[8]["material"], (8, 9))
        self.assertTrue(re.search(r"!\[\[M008-009-1\.jpg\]\]", "\n".join(qs[8]["material_lines"])))
        images = list((folder/"attachments").glob("*.jpg"))
        self.assertEqual(len(images), 11, '9题+跨页多1张+材料1张')
        self.assertTrue(all(i.stat().st_size > 300 for i in images))
        self.assertEqual(mock.MODULE_OF["图形推理"], "判断推理")
        self.assertEqual(scan.PROGRESS["stage"], "完成")
        with self.assertRaises(scan.ScanError):
            scan.split(pp, pdf, 1001, engine=engine)       # 已有复盘文件：不覆盖笔记

    def test_text_layer_pages_do_not_need_ocr(self):
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        y = 100
        for text in ["第一部分  政治理论", "（共2题，参考时间：12分钟）", "1．第一题题干，下列说法正确的是：", "A．甲", "B．乙", "C．丙", "D．丁",
                     "2．第二题题干，下列说法错误的是：", "A．甲", "B．乙", "C．丙", "D．丁"]:
            page.insert_text((60 if re.match(r"\d", text) else 80, y), text, fontname="china-s", fontsize=11)
            y += 22
        pdf = self.root/"文字卷.pdf"
        doc.save(str(pdf))
        pp = SimpleNamespace(train=self.root/"训练")
        report = scan.split(pp, pdf, 1002, engine=lambda f: self.fail("有文字层不该走OCR"))
        self.assertEqual((report["found"], report["total"]), (2, 2))

    def test_pre_ocred_pdf_works_without_a_local_ocr_even_with_a_few_picture_pages(self):
        """用户先用别的软件OCR成带文字层的PDF：本机没有OCR也能导入；个别纯图片页（没有文字）跳过，不报错。"""
        doc = fitz.open()
        rows = [(80, "第一部分  政治理论"), (80, "（共2题，参考时间：12分钟）"), (60, "1．第一题题干，下列说法正确的是："), (80, "A．甲"), (80, "B．乙"), (80, "C．丙"), (80, "D．丁"),
                (60, "2．第二题题干，下列说法错误的是："), (80, "A．甲"), (80, "B．乙"), (80, "C．丙"), (80, "D．丁")]
        for chunk in (rows[:7], rows[7:]):
            page = doc.new_page(width=595, height=842)
            y = 100
            for x, text in chunk:
                page.insert_text((x, y), text, fontname="china-s", fontsize=11)
                y += 22
        page = doc.new_page(width=595, height=842)           # 纯图片页：没有任何文字
        page.draw_rect(fitz.Rect(100, 100, 300, 300), color=None, fill=(0, 0, 0))
        for k in range(3):
            doc.new_page(width=595, height=842).insert_text((80, 100), "第%d页的一些文字，不少于三十个字的内容，用来表示这一页有文字层。" % k, fontname="china-s", fontsize=11)
        pdf = self.root/"先OCR过的卷.pdf"
        doc.save(str(pdf))
        old = scan.ocr_engine_name
        scan.ocr_engine_name = lambda: ""
        try:
            report = scan.split(SimpleNamespace(train=self.root/"训练"), pdf, 1004)
        finally:
            scan.ocr_engine_name = old
        self.assertEqual((report["found"], report["total"]), (2, 2))
        self.assertEqual(report["skipped_pages"], [3])
        self.assertIn("第3页没有文字", report["split_log"])

    def test_no_ocr_gives_a_clear_message(self):
        pdf = self.root/"扫描.pdf"
        make_pdf(pdf, PAGES[:1])
        old = scan.ocr_engine_name
        scan.ocr_engine_name = lambda: ""
        try:
            with self.assertRaises(scan.ScanError) as ctx:
                scan.split(SimpleNamespace(train=self.root/"训练"), pdf, 1003)
        finally:
            scan.ocr_engine_name = old
        self.assertIn("扫描图片", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
