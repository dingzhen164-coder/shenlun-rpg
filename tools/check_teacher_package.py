"""核验外部老师ZIP：只读原件，在临时训练目录试导入并比较完整正文，不提交用户资料。
用法 python3 tools/check_teacher_package.py <外部ZIP路径>；输出仅文件名/分发/字数/上限，不输出心法正文。
"""
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def check(filename):
    from rpg import config, paths, skillbook
    source=Path(filename)
    raw=source.read_bytes()
    # 不找真实库或读取本机配置。仅解析程序自带规则的行测板块表。
    rules=config.Rules((paths.DEFAULTS_DIR/'规则.md').read_text(encoding='utf-8'))
    boards=list(dict.fromkeys(list(rules.boards)+list(rules.side)))
    with tempfile.TemporaryDirectory(prefix='teacher-package-check-') as tmp:
        with patch.object(Path,'home',return_value=Path(tmp)/'home'):
            p=paths.Paths(Path(tmp)/'vault','行测');p.ensure_train_dir()
            entries,_=skillbook._package_entries(source.name,raw,strict=True)
            originals=dict(entries)
            preview=skillbook.import_teachers(p,boards,source.name,raw,preview=True)
            assert all(not skillbook.own_files(p,b) for b in boards),'预览不能写入'
            result=skillbook.import_teachers(p,boards,source.name,raw)
            for row in result['items']:
                for b in row['boards']:
                    # read_file按Python文本模式规范换行；这里直接核对UTF-8文件字节，CRLF也不能误判成丢文。
                    assert skillbook._file(p,b,row['path']).read_bytes().decode('utf-8')==originals[row['source']],row['source']
            second=skillbook.import_teachers(p,boards,source.name,raw)
            assert not second['added'] and not second['overwritten'],'重复导入不能叠加'
            over=[{'file':r['source'],'chars':len(originals[r['source']])} for r in result['items'] if len(originals[r['source']])>skillbook.TUTOR_LIMIT]
            contexts=[]
            for row in result['items']:
                if len(originals[row['source']])<=skillbook.TUTOR_LIMIT:continue
                b=row['boards'][0]
                question={'资料分析':'同比增长率、基期量、现期量、比重、倍数如何计算',
                          '图形推理':'图形推理的位置旋转、数量笔画、对称规律',
                          '论证逻辑':'结论与前提、因果论证、加强削弱如何判断'}.get(b,b)
                digest,used=skillbook.tutor_material(p,b,row['teacher'],question)
                assert digest and len(digest)<=skillbook.TUTOR_LIMIT,row['source']
                assert any('非全文' in u for u in used),row['source']
                contexts.append({'file':row['source'],'selected_chars':len(digest),'bounded':True,'ranges_reported':True})
            return {'source_sha256':hashlib.sha256(raw).hexdigest(),'documents':len(entries),
                    'teachers':len({Path(n).stem.split('-',1)[0] for n in originals}),
                    'accepted':len(result['items']),'distributed_copies':len(result['added']),
                    'items':preview['items'],'skipped':result['skipped'],'over_read_limit':over,'long_context_checks':contexts,
                    'verified_full_text':True,'verified_no_duplicates':True,'writes_to_real_vault':False}


if __name__=='__main__':
    print(json.dumps(check(sys.argv[1]),ensure_ascii=False,indent=2))
