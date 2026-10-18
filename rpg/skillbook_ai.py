"""藏经阁·心法的 AI 辅助（都是用户点一下才调用一次，不做后台自动请求）：
- organize：整理向导。读库里原 skill 及其引用资料，起草成标准 6 个文件，存成待审建议，用户逐文件采纳；不覆盖已有文件。
- note：解惑后「记入心法」。按这道题和师傅的讲解，判断现有方法要不要补；要补就起草最少的修改，存成待审建议。
结果都先存 训练/技能/.待审/，采纳前不改任何方法文件；同一来源同一内容不重复花钱（按 key 复用）。
输出是 JSON，程序校验（路径、动作、长度）后才保存；校验不过重试一次，仍失败就不保存。
"""
import hashlib

from . import ai, prompts, skillbook, vault

ORGANIZE_LIMIT = 60000       # 整理向导读入的资料上限（字）；超出直接拒绝，不喂残缺资料


class AIUnavailable(skillbook.SkillError):
    pass


def _call(messages, **kw):
    if not ai.available():
        raise AIUnavailable("还没有填写 AI 的 API key（设置里填写后才能用）")
    last = None
    for _ in range(2):                       # 校验不过重试一次
        try:
            r = ai.chat_json(messages, **kw)
            if isinstance(r, dict):
                return r
        except ai.AIError as e:
            last = e
    raise skillbook.SkillError("AI 没有给出可用的结果：%s" % (last or "格式不对"))


def organize(paths, board, source):
    d = vault.skill_dir(paths, source)
    if not d:
        raise skillbook.SkillError("库里没有原 skill「%s」，没有东西可整理" % (source or "未配置"))
    text, used = vault.skill_material(paths, source)
    if len(text) > ORGANIZE_LIMIT:
        raise skillbook.SkillError("资料太长（%d 字，上限 %d 字），请先拆分成更小的板块再整理；没有生成残缺草稿" % (len(text), ORGANIZE_LIMIT))
    key = "organize:" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    for p in skillbook.proposals(paths, board):
        if p.get("key") == key:
            return p                           # 同样的资料已经整理过，不重复花钱
    r = _call(prompts.skillbook_organize(board, text), temperature=0.2, max_tokens=6000, timeout=240)
    files = [{"path": f.get("path"), "action": "new", "text": f.get("text"), "reason": "整理自原 skill"}
             for f in (r.get("files") or []) if isinstance(f, dict) and f.get("path") in prompts.SKILLBOOK_FILES]
    if not any(f["path"] == "SKILL.md" for f in files):
        raise skillbook.SkillError("AI 的整理结果里没有入口 SKILL.md，没有保存；可以再点一次")
    return skillbook.add_proposal(paths, board, "organize", r.get("summary") or "整理成标准结构", files,
                                  {"label": "整理向导（读了 %d 份资料）" % (1 + len(used))}, key)


def note(paths, board, source, ctx, label):
    """ctx：question、answer、mine、explain；label：来源说明（如“试炼复盘 粉笔33季-001”）。返回 (建议或 None, 说明)"""
    plan = skillbook.reading_plan(paths, board, source)
    current = plan["text"][:20000]
    key = "note:" + hashlib.sha1((board + str(ctx.get("question")) + str(ctx.get("explain"))).encode("utf-8")).hexdigest()[:12]
    for p in skillbook.proposals(paths, board):
        if p.get("key") == key:
            return p, "这道题已经有一条待审建议了"
    r = _call(prompts.skillbook_note(board, current, ctx), temperature=0.2, max_tokens=2500, timeout=180)
    if not r.get("needed"):
        return None, "现有心法已经覆盖这道题（或只是个别情况），不用改"
    prop = skillbook.add_proposal(paths, board, "note", r.get("summary") or "补充一条方法", r.get("edits"), {"label": label}, key)
    return prop, "已生成一条待审建议"
