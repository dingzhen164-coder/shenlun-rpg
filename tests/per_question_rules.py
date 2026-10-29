"""默认做题不再按题数发修为（只按学习时间）；用非旧默认的数值，免得被规则迁移改回 0；测“按题奖励/防重复发奖”的用例用它显式打开旧数值。"""
import re

from rpg import api, paths


def enable(vault, subject="行测"):
    with api.open_game(save=False):
        pass                                           # 先让规则文件落盘
    try:
        f = paths.Paths(vault, subject).rules
    except TypeError:                                  # 法考的 Paths 只有一个库参数
        f = paths.Paths(vault).rules
    text = f.read_text(encoding="utf-8")
    for key, val in (("经验.实战答对", 6), ("经验.实战答错", 2), ("经验.实战通关", 31)):
        text, n = re.subn(r"(?m)^(\s*[-*]?\s*%s\s*[:：]\s*)\S+" % re.escape(key), r"\g<1>%s" % val, text)
        if not n:
            text += "\n- %s: %s\n" % (key, val)
    f.write_text(text, encoding="utf-8")
