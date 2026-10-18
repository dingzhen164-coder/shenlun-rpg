"""行测模考入库批次回收/恢复，供/api/import/season/remove、restore调用。

仅移除训练/题库中编号严格为粉笔N季-数字的题块（含已做题与待修）；
不改原PDF/HTML、复盘、图片、存档及学习历史。训练/导入回收/<UUID>保存
原文件与清单，先预览摘要再提交，原子替换、冲突拒绝、失败回滚；恢复时
优先逐字还原，无关后续编辑保留，同编号内容冲突不覆盖。所有路径限训练内。
"""
import hashlib
import json
import os
import re
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from . import importer


def _hash(data):
    return hashlib.sha256(data if data is not None else b'').hexdigest()


def _guard(paths):
    if getattr(paths,'subject','')!='行测':raise importer.ImportError_('此入口仅管理行测模考入库批次')
    if not paths.vault:raise importer.ImportError_('请先选择行测学习库')
    if paths.train.is_symlink():raise importer.ImportError_('训练目录不能是符号链接')


def _safe(paths,relative):
    p=Path(relative)
    if p.is_absolute() or '..' in p.parts:raise importer.ImportError_('回收记录路径无效')
    file=paths.train/p
    try:file.resolve().relative_to(paths.train.resolve())
    except ValueError:raise importer.ImportError_('回收路径不能越出训练目录')
    current=file
    while current!=paths.train:
        if current.is_symlink():raise importer.ImportError_('回收路径不能包含符号链接')
        current=current.parent
    return file


def _read(file):
    return file.read_bytes() if file.exists() else None


def _atomic(file,data):
    if data is None:
        file.unlink()
        return
    file.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.import-',dir=str(file.parent))
    try:
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(name,file)
    finally:
        if os.path.exists(name):os.unlink(name)


def _json(file,value):
    _atomic(file,json.dumps(value,ensure_ascii=False,indent=1).encode('utf-8'))


def _number(value):
    if type(value) is not int or not 1<=value<=9999:raise importer.ImportError_('请选择有效的模考季号')
    return value


def _files(paths):
    bank=paths.train/'题库'
    candidates=list(bank.glob('*真题*.md'))+list((bank/importer.FIX_DIR).glob('*.md'))
    return sorted({_safe(paths,f.relative_to(paths.train)) for f in candidates if f.is_file()})


def _text(data):
    try:return (data or b'').decode('utf-8')
    except UnicodeDecodeError:raise importer.ImportError_('题库文件不是UTF-8，未改动文件')


def _plan(paths,season):
    _guard(paths);_number(season)
    changes,signature,ids=[],[],set()
    for f in _files(paths):
        before=f.read_bytes();relative=f.relative_to(paths.train).as_posix()
        signature.append([relative,_hash(before)])
        text=_text(before);blocks=[b for b in importer.parse_blocks(text) if re.fullmatch(r'粉笔%d季-\d+'%season,b['id'])]
        if not blocks:continue
        after=text
        for b in reversed(blocks):after=after[:b['start']]+after[b['end']:]
        ids.update(b['id'] for b in blocks)
        changes.append(dict(path=relative,before=before,after=after.encode('utf-8'),count=len(blocks)))
    digest=_hash(json.dumps([season,signature],ensure_ascii=False).encode('utf-8'))
    return changes,digest,len(ids)


def check(g,season):
    """已有PDF/HTML/旧库复盘直接核分，读取当前季，不要求重新入库。"""
    from . import mock,mock_score,vault
    _guard(g.paths);_number(season)
    directory=next((d for n,d in vault.seasons(g.paths) if n==season),None)
    if directory is None:raise importer.ImportError_('找不到第%d季复盘'%season)
    counts=mock.season_counts(g.paths,directory)
    rec=g.state.get('mocks',{}).get(str(season),{})
    return dict(season=season,total=sum(c['total'] for c in counts.values()),
                estimate=mock_score.estimate(g,directory,counts,rec),
                reported_score=(rec.get('html_import') or {}).get('reported_score'),
                saved_score=rec.get('score') if rec.get('score') is not None else mock._boss_score(g,season))


def archives(paths):
    if getattr(paths,'subject','')!='行测':return []
    root=_safe(paths,'导入回收')
    out=[]
    for file in sorted(root.glob('*/清单.json')) if root.exists() else []:
        try:
            if not re.fullmatch('[0-9a-f]{32}',file.parent.name):continue
            file=_safe(paths,file.relative_to(paths.train))
            item=json.loads(file.read_text(encoding='utf-8'))
            if not isinstance(item,dict) or type(item.get('removed')) is not int or item['removed']<0:continue
            if item.get('state') not in ('deleted','prepared','recovery'):continue
            out.append(dict(token=file.parent.name,season=_number(item['season']),removed=item['removed'],
                            created=item.get('created',''),recovery=item['state']!='deleted'))
        except (ValueError,KeyError,TypeError,OSError,importer.ImportError_):continue
    return sorted(out,key=lambda x:x['created'],reverse=True)


def _apply(changes):
    """提交前再次核对；IO失败只回滚仍等于本次输出的文件，不盖外部修改。"""
    applied=[]
    try:
        for f,before,after in changes:
            if _read(f)!=before:raise importer.ImportError_('题库已变化，请重新检查后操作')
            _atomic(f,after);applied.append((f,before,after))
    except Exception:
        for f,before,after in reversed(applied):
            if _read(f)==after:
                try:_atomic(f,before)
                except OSError:pass
        raise


def remove(paths,body):
    with importer.LOCK:
        season=_number(body.get('season'));changes,digest,count=_plan(paths,season)
        rep=dict(season=season,removed=count,blocks=sum(c['count'] for c in changes),files=len(changes),digest=digest,
                 scope='仅移除该季题库及待修题块；原试卷、复盘笔记、图片、成绩、学习记录和未完成练习保留',dry=not body.get('commit'))
        if not count:raise importer.ImportError_('这一季当前没有已入库或待修题目，无需删除')
        if 'commit' in body and type(body['commit']) is not bool:raise importer.ImportError_('删除确认须为布尔值')
        if not body.get('commit'):return rep
        if body.get('digest')!=digest:raise importer.ImportError_('题库在预览后发生变化，请重新检查删除范围')
        token=uuid.uuid4().hex;folder=_safe(paths,'导入回收/'+token);folder.mkdir(parents=True)
        entries=[]
        for i,c in enumerate(changes):
            _atomic(folder/('%d.before'%i),c['before'])
            entries.append(dict(path=c['path'],before=_hash(c['before']),after=_hash(c['after'])))
        meta=dict(schema=1,season=season,removed=count,state='prepared',created=datetime.now().isoformat(timespec='seconds'),entries=entries)
        manifest=folder/'清单.json';_json(manifest,meta)
        try:
            _apply([(_safe(paths,c['path']),c['before'],c['after']) for c in changes])
            meta['state']='deleted';_json(manifest,meta)
        except Exception as e:
            # 清单提交失败时也尝试回滚整批，回收副本始终保留。
            clean=True
            for c in reversed(changes):
                f=_safe(paths,c['path']);current=_read(f)
                if current==c['after']:
                    try:_atomic(f,c['before'])
                    except OSError:clean=False
                elif current!=c['before']:clean=False
            meta['state']='cancelled' if clean else 'recovery'
            try:_json(manifest,meta)
            except OSError:pass
            raise importer.ImportError_('删除未完成（%s）；原文件已回滚或保留在导入回收/%s，可从恢复入口处理'%(e,token))
        return dict(rep,token=token)


def restore(paths,body):
    with importer.LOCK:
        _guard(paths);token=str(body.get('token') or '')
        if not re.fullmatch('[0-9a-f]{32}',token):raise importer.ImportError_('恢复记录无效')
        folder=_safe(paths,'导入回收/'+token);manifest=folder/'清单.json'
        try:meta=json.loads(_safe(paths,manifest.relative_to(paths.train)).read_text(encoding='utf-8'))
        except (ValueError,OSError):raise importer.ImportError_('恢复清单缺失或损坏')
        if not isinstance(meta,dict) or meta.get('schema')!=1 or type(meta.get('removed')) is not int:
            raise importer.ImportError_('恢复清单结构无效')
        if not isinstance(meta.get('entries'),list) or len(meta['entries'])>2000:
            raise importer.ImportError_('恢复文件清单无效')
        season=_number(meta.get('season'))
        if meta.get('state')=='restored':return dict(season=season,restored=0,already=True)
        if meta.get('state') not in ('deleted','prepared','recovery'):raise importer.ImportError_('此批次没有待恢复的删除')
        all_ids={}
        for f in _files(paths):
            text=_text(f.read_bytes())
            for b in importer.parse_blocks(text):all_ids.setdefault(b['id'],[]).append((f,text[b['start']:b['end']]))
        changes=[]
        try:
            for i,entry in enumerate(meta['entries']):
                relative=Path(entry['path'])
                bank_file=len(relative.parts)==2 and relative.parts[0]=='题库' and '真题' in relative.name
                pending=len(relative.parts)==3 and relative.parts[:2]==('题库',importer.FIX_DIR)
                if not (bank_file or pending) or relative.suffix!='.md':raise ValueError('文件类型无效')
                f=_safe(paths,relative);original=_safe(paths,folder.relative_to(paths.train)/('%d.before'%i)).read_bytes()
                if _hash(original)!=entry['before']:raise ValueError('回收副本校验失败')
                current=_read(f);text=_text(original)
                blocks=[b for b in importer.parse_blocks(text) if re.fullmatch(r'粉笔%d季-\d+'%season,b['id'])]
                missing=[]
                for b in blocks:
                    block=text[b['start']:b['end']];existing=all_ids.get(b['id'],[])
                    if existing and any(value!=block for _,value in existing):
                        raise importer.ImportError_('题号%s已有不同内容，未覆盖；请先核对或保留回收副本'%b['id'])
                    if not existing:missing.append(block)
                if current==original:continue
                if _hash(current)==entry['after'] and len(missing)==len(blocks):after=original
                elif missing:
                    prefix=_text(current)
                    if current is None:prefix=text[:blocks[0]['start']] if blocks else ''
                    after=(prefix+('\n\n' if prefix and not prefix.endswith('\n\n') else '')+''.join(missing)).encode('utf-8')
                else:continue
                changes.append((f,current,after))
        except (KeyError,TypeError,ValueError,OSError) as e:raise importer.ImportError_('恢复副本不可用：%s'%e)
        try:
            _apply(changes);meta['state']='restored';_json(manifest,meta)
        except Exception as e:
            for f,before,after in reversed(changes):
                if _read(f)==after:
                    try:_atomic(f,before)
                    except OSError:pass
            raise importer.ImportError_('恢复未完成（%s）；回收副本仍保留，可再次恢复'%e)
        return dict(season=season,restored=meta['removed'],already=False)
