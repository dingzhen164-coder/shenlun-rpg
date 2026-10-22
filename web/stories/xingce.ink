// 原创剧情，生成自rpg/data/narrative.json；修改该源后重新编译。
VAR learned = false
VAR tower = false
VAR boss = false
-> END
=== prologue_start ===
行测宗山门重开。沈清禾在竹下等你，将一卷竹简放在石案上。
先明理，再举例，最后以真题验之。你愿从何处开始？
+ [我想先梳理方法] # choice:understand
  -> prologue_understand
+ [我想先试着作答] # choice:practice
  -> prologue_practice
+ {learned} [聊聊已有的学习记录] # choice:recorded
  -> prologue_recorded
=== prologue_understand ===
清禾把竹简展开：“先选一门功法，用自己的话讲清思路，再举一例。藏经阁与修炼殿会保留你原来的进度。”
+ [记下这个方向] # choice:continue
  -> prologue_end
=== prologue_practice ===
清禾轻叩竹卷：“一道题做错，也会留下真实记录。层数看历练，正确率看成效；先弄清失误，再走下一程。”
+ [带着问题去练习] # choice:continue
  -> prologue_end
=== prologue_recorded ===
你已留下真实修行记录。慢一些无妨，重要的是知道每一步为何如此。
+ [继续前行] # choice:continue
  -> prologue_end
=== prologue_end ===
山风拂过竹叶。你把今日的方向记在心中，沿着石阶走向修炼殿。任务大殿可以随时重读。
-> END
=== study_echo_start ===
你已留下真实修行记录。慢一些无妨，重要的是知道每一步为何如此。
这段对话因已有学习记录开放；阅读与选项不会改变成绩或学习时长。
+ [我想先梳理方法] # choice:understand
  -> study_echo_understand
+ [我想先试着作答] # choice:practice
  -> study_echo_practice
+ {learned} [聊聊已有的学习记录] # choice:recorded
  -> study_echo_recorded
=== study_echo_understand ===
清禾把竹简展开：“先选一门功法，用自己的话讲清思路，再举一例。藏经阁与修炼殿会保留你原来的进度。”
+ [记下这个方向] # choice:continue
  -> study_echo_end
=== study_echo_practice ===
清禾轻叩竹卷：“一道题做错，也会留下真实记录。层数看历练，正确率看成效；先弄清失误，再走下一程。”
+ [带着问题去练习] # choice:continue
  -> study_echo_end
=== study_echo_recorded ===
你已留下真实修行记录。慢一些无妨，重要的是知道每一步为何如此。
+ [继续前行] # choice:continue
  -> study_echo_end
=== study_echo_end ===
山风拂过竹叶。你把今日的方向记在心中，沿着石阶走向修炼殿。任务大殿可以随时重读。
-> END
=== peer_method_start ===
明理殿的竹简还未写满。你想先理清方法，还是试一道题？
这是内置同伴对话，选择只影响后续台词与纪念；正式学习仍使用原功能。
+ [先梳理与回忆] # choice:method
  -> peer_method_method
+ [先独立练习] # choice:practice
  -> peer_method_practice
=== peer_method_method ===
陆衡留下一卷空白竹简：“把适用条件与边界讲清，不必只背方法名字。”
+ [记下这个方向] # choice:continue
  -> peer_method_end
=== peer_method_practice ===
陆衡指向试炼塔：“先独立作答，再看判断依据；错了也能留下真实练习记录。”
+ [带着问题去学习] # choice:continue
  -> peer_method_end
=== peer_method_end ===
这次交谈已经记下。学习入口随时开放；交付首段真实学习成果后，已读支线可留下同伴纪念。
-> END
=== peer_review_start ===
任务大殿前，苏苓留出两条路：温一张玉简，或复练一道题。你想从哪边开始？
这是内置同伴对话，选择只影响后续台词与纪念；正式学习仍使用原功能。
+ [先梳理与回忆] # choice:method
  -> peer_review_method
+ [先独立练习] # choice:practice
  -> peer_review_practice
=== peer_review_method ===
苏苓展开玉简：“先回忆，再翻看；忘记了就按真实表现评分。”
+ [记下这个方向] # choice:continue
  -> peer_review_end
=== peer_review_practice ===
苏苓轻指旧题：“复练看依据，不重复发通关奖励，也不替你改正确率。”
+ [带着问题去学习] # choice:continue
  -> peer_review_end
=== peer_review_end ===
这次交谈已经记下。学习入口随时开放；交付首段真实学习成果后，已读支线可留下同伴纪念。
-> END
