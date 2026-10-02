"""
本机设置的读写（网页“设置”页用）：库路径、API key、接口地址、模型。

存在 ~/.shenlun-rpg/settings.json（不同步、不进仓库）。api_key 对外只给打码版本，写入时留空表示不改。
谁调用：core/api.py（GET/POST /api/settings、POST /api/settings/test）。
"""
from pathlib import Path

from . import ai, paths


def mask(key):
    key = key or ""
    return "" if not key else (key[:3] + "…" + key[-4:] if len(key) > 10 else "已填写")


def get():
    s = paths.load_settings()
    cur = ai.settings()
    return {
        "vault": s.get("vault") or "",
        "vault_in_use": str(paths.find_vault()),
        "has_key": bool(cur["api_key"]),
        "key_mask": mask(cur["api_key"]),
        "base_url": cur["base_url"],
        "model": cur["model"],
    }


def put(body):
    """保存设置；返回需要调用方处理的变化：{"vault_changed": bool}。出错抛 ValueError（消息给用户看）"""
    upd, changed = {}, False
    if "vault" in body:
        v = str(body["vault"] or "").strip().strip('"')
        if v and not Path(v).is_dir():
            raise ValueError("库路径不存在：%s（请确认文件夹已创建，路径可以直接从资源管理器地址栏复制）" % v)
        upd["vault"] = v
        changed = v != (paths.load_settings().get("vault") or "")
    key = str(body.get("api_key") or "").strip()
    if key:
        upd["api_key"] = key
    for k in ("base_url", "model"):
        if k in body:
            upd[k] = str(body[k] or "").strip()
    paths.save_settings(upd)
    return {"vault_changed": changed}


def test():
    """试连 AI：返回 (ok, 说明)"""
    try:
        out = ai.chat([{"role": "user", "content": "只回复两个字：好的"}], max_tokens=20, timeout=30)
        return True, "连接成功，模型回复：" + out.strip()[:30]
    except ai.AIError as e:
        return False, str(e)
