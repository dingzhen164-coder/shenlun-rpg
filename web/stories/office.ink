// 原创剧情，生成自rpg/data/narrative.json；修改该源后重新编译。
VAR learned = false
VAR tower = false
VAR boss = false
-> END
=== prologue_start ===
政务大厅的晨光落在案卷上。直属领导抬头，示意你在桌前坐下。
欢迎回到政务大厅。先读材料，把问题与依据理清，再动笔。你想先了解什么？
+ [我想先梳理方法] # choice:understand
  -> prologue_understand
+ [我想先试着作答] # choice:practice
  -> prologue_practice
+ {learned} [聊聊已有的学习记录] # choice:recorded
  -> prologue_recorded
=== prologue_understand ===
她翻开工作簿：“先读题干的对象、范围与要求。把材料中的核心含义归并清楚，再进入办理中心按题型练习。”
+ [记下这个方向] # choice:continue
  -> prologue_end
=== prologue_practice ===
她递来一张空白答题卡：“先独立作答，再看批示。字数、材料批注与笔迹继续由原作答页保存，不必急着看参考。”
+ [带着问题去练习] # choice:continue
  -> prologue_end
=== prologue_recorded ===
你已经留下学习记录。回看材料、要点和自己的表达，再确定下一步安排。
+ [继续前行] # choice:continue
  -> prologue_end
=== prologue_end ===
大厅的钟声响起。她把工作簿交还给你：“准备好了，就从眼前的一项办理开始。”工作纪事可以随时重读。
-> END
=== study_echo_start ===
你已经留下学习记录。回看材料、要点和自己的表达，再确定下一步安排。
这段对话因已有学习记录开放；阅读与选项不会改变成绩或学习时长。
+ [我想先梳理方法] # choice:understand
  -> study_echo_understand
+ [我想先试着作答] # choice:practice
  -> study_echo_practice
+ {learned} [聊聊已有的学习记录] # choice:recorded
  -> study_echo_recorded
=== study_echo_understand ===
她翻开工作簿：“先读题干的对象、范围与要求。把材料中的核心含义归并清楚，再进入办理中心按题型练习。”
+ [记下这个方向] # choice:continue
  -> study_echo_end
=== study_echo_practice ===
她递来一张空白答题卡：“先独立作答，再看批示。字数、材料批注与笔迹继续由原作答页保存，不必急着看参考。”
+ [带着问题去练习] # choice:continue
  -> study_echo_end
=== study_echo_recorded ===
你已经留下学习记录。回看材料、要点和自己的表达，再确定下一步安排。
+ [继续前行] # choice:continue
  -> study_echo_end
=== study_echo_end ===
大厅的钟声响起。她把工作簿交还给你：“准备好了，就从眼前的一项办理开始。”工作纪事可以随时重读。
-> END
