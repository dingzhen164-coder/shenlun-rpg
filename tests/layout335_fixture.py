"""3.3.5界面夹具：仅由隔离ui_layout_server调用，生成自编时政JSON，不读取用户资料或调用AI。"""
def install(g):
    from rpg import tianji
    if getattr(g, 'subject', '') == '申论':
        return
    def write(kind, iid, title, month=1, half='上', category='其他'):
        data=dict(id=iid,kind=kind,title=title,label=title,year=2026,month=month,half=half,category=category,overview='自编界面检查资料',groups=['自编小节'],
                  news=[dict(no=1,stars=2,tag='自编',title='自编要目',group='自编小节',paras=['用于检查阅读和排版的自编材料。'],qs=[])],cloze=[],questions=[])
        tianji._write(tianji._file(g.paths,kind,iid),data)
    for i in range(18):
        month=i//2+1;half='上' if i%2==0 else '下'
        write('month','2026-%02d-%s'%(month,half),'自编月半%d'%i,month,half)
    for n,category in enumerate(tianji.CATEGORIES[:3],1):
        for i in range(n):write('topic','自编专题%d-%d'%(n,i),'自编专题%d-%d'%(n,i),category=category)
