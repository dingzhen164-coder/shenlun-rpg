"""3.5.9界面隔离自编音乐/公式/大图与假导师；只写调用方临时库。"""
import math,struct,wave
from pathlib import Path
from rpg import api,ai
from tests.test_inline_images import png


def install(g):
    music=g.paths.train/'外观/音乐';music.mkdir(parents=True,exist_ok=True)
    for name,freq in [('自编甲.wav',220),('自编乙.wav',330)]:
        with wave.open(str(music/name),'wb') as f:
            f.setparams((1,2,8000,0,'NONE','not compressed'))
            f.writeframes(b''.join(struct.pack('<h',int(800*math.sin(2*math.pi*freq*i/8000))) for i in range(32000)))
    folder=g.paths.train/'题库/图片/题目图';folder.mkdir(parents=True,exist_ok=True)
    for name,w,h in [('自编小公式.png',70,48),('自编大图.png',800,450)]: (folder/name).write_bytes(png(w,h))
    subject=getattr(g,'subject','法考')
    board='数量关系' if subject=='行测' else next(iter(g.boards))
    root='训练/题库/图片/题目图/'
    stem='自编计算：总量为\n![[%s自编小公式.png]]\n倍，哪项满足条件？'%root
    if subject!='申论':api.bank_add(dict(board=board,topic='自编359',stem=stem,options=dict(A='甲',B='乙',C='丙',D='丁'),answer='A',analysis='自编解析。'))
    if subject=='行测':
        api.bank_add(dict(board='逻辑填空',topic='逻辑填空',stem='自编：这项事业____，需要继续努力。',options=dict(A='方兴未艾',B='如火如荼',C='蒸蒸日上',D='崭露头角'),answer='A',analysis=''))
    ai.available=lambda:True
    ai.chat=lambda *a,**k:'“方兴未艾”形容事物正在兴起。结合语境选择A，其余成语分别对应不同语义。'
    print('UI-359 '+__import__('json').dumps(dict(board=board,formula=root+'自编小公式.png',large=root+'自编大图.png'),ensure_ascii=False),flush=True)
