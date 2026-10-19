"""藏经阁·心法的 AI 辅助（都是用户点一下才调用一次，不做后台自动请求）：
- organize：整理成学习版。读这个板块现在的心法（含引用资料），改写成人能学的 6 个新文件（怎么用 / 识别信号 / 方法卡 / 陷阱 / 示范 / 速查），
  存成待审建议，用户逐文件采纳；不改、不覆盖已有文件。示范用你题库里的真题（先挑做错过的）。
- note：解惑后「记入心法」。按这道题和师傅的讲解，判断现有方法要不要补；要补就起草最少的修改，存成待审建议。
结果都先存 训练/技能/.待审/，采纳前不改任何方法文件；同一来源同一内容不重复花钱（按 key 复用）。
输出是 JSON，程序校验（路径、动作、长度）后才保存；校验不过重试一次，仍失败就不保存。
"""
import hashlib
import re

from . import ai, prompts, skillbook, vault



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


FILE_CHARS = (1800, 900)        # 每个文件的字数上限；回复被截断时用第二个更紧的上限重试一次
DEMO_CHARS = (1200, 700)
DEMO_COUNT = 2                 # 示范几道题
DEMO_FILE = "04-示范.md"
VERSION = "learn1"             # 改了提示词就换一个，已经生成过的建议不再被当成“同样的资料”复用


def _fence(text):
    t = (text or "").strip()
    m = re.match(r"^```[a-zA-Z]*\n(.*?)\n```$", t, re.S)
    return (m.group(1) if m else t).strip()


def _write(make, limits):
    """调一次 AI 写一段文字：回复被截断（超过长度上限）就换更紧的字数上限重试一次；还不行就放弃"""
    last = None
    for limit in limits:
        try:
            text = _fence(ai.chat(make(limit), temperature=0.2, max_tokens=3500, timeout=240))
        except ai.AIError as e:
            last = e
            if "长度上限" in str(e):
                continue
            raise skillbook.SkillError("AI 没有回复：%s" % e)
        return None if (not text or text.strip("（）() ") == "无") else text
    raise skillbook.SkillError("AI 两次都没写完（%s）" % last)


def pick_examples(g, board, n=DEMO_COUNT):
    """示范用的真题：先挑你做错过的（回炉中的），再挑有解析的，凑够 n 道；都没有就是空"""
    from . import question_bank
    try:
        qs, _ = question_bank.read(g.paths, board)
    except Exception:
        return []
    recs = question_bank.state(g).get("records", {})
    qs = [q for q in qs if q.get("answer") and set(q.get("options") or {}) == set("ABCD")]
    qs.sort(key=lambda q: (not (recs.get(q["key"]) or {}).get("wrong"), not q.get("analysis"), q["id"]))
    return qs[:n]


def organize(paths, board, source, examples=()):
    """整理成“学习版”：在心法里新增 00-怎么用 / 01-识别信号 / 02-方法卡 / 03-陷阱 / 04-示范 / 05-速查，存成待审建议。
    不改原来的任何文件；已有同名文件的这次不重写。材料就是这个板块现在的心法（不含给 AI 总调度的那一节）。"""
    plan = skillbook.reading_plan(paths, board, source)
    if plan["mode"] == "none":
        raise skillbook.SkillError("这个板块还没有心法，没有东西可整理；可以先新建标准模板")
    if any(not i["read"] for i in plan["items"]):
        raise skillbook.SkillError("资料太长（超过 %d 字上限），请先精简或拆分；没有生成残缺草稿" % plan["limit"])
    text = plan["text"]
    have = set(skillbook.own_files(paths, board))
    todo = [f for f in prompts.LEARN_ORDER if f not in have]
    demos = [] if DEMO_FILE in have else list(examples)
    if not todo and not demos:
        raise skillbook.SkillError("这个板块的学习版文件都已经有了（想重新生成，先把对应文件删掉，旧的会留在历史里）")
    key = "organize:" + VERSION + hashlib.sha1((text + "|".join(sorted(todo)) + "|".join(q["key"] for q in demos)).encode("utf-8")).hexdigest()[:12]
    for p in skillbook.proposals(paths, board):
        if p.get("key") == key:
            return p                           # 同样的资料已经整理过，不重复花钱
    if not ai.available():
        raise AIUnavailable("还没有填写 AI 的 API key（设置里填写后才能用）")
    files, skipped, cards = [], [], ""
    for path in todo:                          # 一次只写一个文件：一起写会超过 AI 的回复长度上限
        try:
            body = _write(lambda lim, path=path: prompts.skillbook_learn_file(board, text, path, lim, cards), FILE_CHARS)
        except skillbook.SkillError:
            if path == "02-方法卡.md":
                raise
            skipped.append(path)
            continue
        if body is None:
            continue
        if path == "02-方法卡.md":
            cards = body[:3500]
        files.append({"path": path, "action": "new", "text": body, "reason": "学习版"})
    if cards or "02-方法卡.md" in have:
        if not cards:
            cards = skillbook._read(skillbook.board_dir(paths, board) / "02-方法卡.md")[:3500]
        parts = []
        for k, q in enumerate(demos, 1):
            try:
                body = _write(lambda lim, q=q: prompts.skillbook_learn_demo(board, text, cards, q, lim), DEMO_CHARS)
            except skillbook.SkillError:
                skipped.append("示范第 %d 道" % k)
                continue
            if body:
                opts = "\n".join("- %s. %s" % (a, b) for a, b in q["options"].items())
                parts.append("## 示范 %d：真题 %s\n\n**题目**：%s\n\n%s\n\n**正确答案**：%s\n\n**思考过程**\n\n%s" % (k, q["id"], q["stem"].strip(), opts, q["answer"], body))
        if parts:
            files.append({"path": DEMO_FILE, "action": "new", "text": "# 示范：用方法卡做真题\n\n" + "\n\n---\n\n".join(parts), "reason": "用你题库里的真题示范"})
    if not any(f["path"] == "02-方法卡.md" for f in files) and "02-方法卡.md" not in have:
        raise skillbook.SkillError("AI 没有写出方法卡，没有保存；可以再点一次")
    if not files:
        raise skillbook.SkillError("AI 没有写出可用的内容，没有保存；可以再点一次")
    summary = "生成学习版（%d 个文件%s）" % (len(files), "，%s 没能生成" % "、".join(skipped) if skipped else "")
    return skillbook.add_proposal(paths, board, "organize", summary, files, {"label": "学习版（读了 %d 份资料）" % len(plan["items"])}, key)


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
