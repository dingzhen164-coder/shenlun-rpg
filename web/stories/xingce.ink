// 原创剧情，生成自rpg/data/narrative.json；修改该源后重新编译。
VAR learned = false
VAR tower = false
VAR boss = false
-> END
=== prologue_start ===
青衡宗山门重开。沈清禾在竹下等你，将一卷竹简放在石案上。
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
山风拂过竹叶。你把今日的方向记在心中，沿着石阶走向修炼殿。宗门纪事可以随时重读。
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
山风拂过竹叶。你把今日的方向记在心中，沿着石阶走向修炼殿。宗门纪事可以随时重读。
-> END
