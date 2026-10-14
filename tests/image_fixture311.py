"""临时自编资料用于实际浏览器验收，不读真实库或AI。"""
from rpg import api, question_images as images
from test_question_images import QuestionImagesTest


def install(g):
    p=g.paths
    fixture=QuestionImagesTest();fixture.p=p;fixture.pm=images._pm()
    pdf,script=fixture.fixture()
    figure=fixture.png();header=fixture.png(300,45)
    d=p.seasons/'第38季';att=d/'attachments';att.mkdir(parents=True)
    (att/'S38-Q076-1.png').write_bytes(header);(att/'S38-Q076-2.png').write_bytes(figure)
    body='![[S38-Q076-1.png]]\n![[S38-Q076-2.png]]\n\n从四个选项中选出合适的图形，使其呈现一定规律。\n'
    (d/'07-图形推理.md').write_text('### 76. ❌\n'+body+'\n> 正确答案：**B**　我的答案：**A**\n> [!note] 复盘\n> 自编解析：比较图形规律。\n---\n',encoding='utf-8')
    for board,name,data in [('图形推理','粉笔38季-076.png',header),('图形推理','粉笔38季-076-2.png',figure),('数量关系','粉笔38季-077.png',header),('定义判断','冗余.png',header)]:
        f=p.train/'题库/图片'/board/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(data)
    records=[('图形推理','图形规律','![[训练/题库/图片/图形推理/粉笔38季-076.png]]\n![[训练/题库/图片/图形推理/粉笔38季-076-2.png]]\n从四个选项中选出合适的图形，使其呈现一定规律。',dict(zip('ABCD','ABCD'))),
        ('数量关系','分数计算','已知总量的一半为3，请选择剩余比例。\n![[训练/题库/图片/数量关系/粉笔38季-077.png]]',dict(A='1/2',B='1/3',C='2/3',D='3/4')),
        ('定义判断','定义判断','自编文字定义：符合甲条件且不符合乙条件。以下哪项符合定义？\n![[训练/题库/图片/定义判断/冗余.png]]',dict(A='符合甲，不符合乙',B='符合甲和乙',C='只符合乙',D='都不符合'))]
    for board,topic,stem,opts in records:
        api.bank_add(dict(board=board,topic=topic,source='自编测试',stem=stem,options=opts,answer='A',analysis='逐项比较自编条件。'))
