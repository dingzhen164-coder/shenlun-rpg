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
=== peer_method_start ===
工作台上留着一张便笺。你想先梳理材料要点，还是先独立写一份答案？
这是内置同伴对话，选择只影响后续台词与纪念；正式学习仍使用原功能。
+ [先梳理与回忆] # choice:method
  -> peer_method_method
+ [先独立练习] # choice:practice
  -> peer_method_practice
=== peer_method_method ===
许知宁留出要点栏：“先看材料中的依据与范围，再决定如何表达；不要补造材料事实。”
+ [记下这个方向] # choice:continue
  -> peer_method_end
=== peer_method_practice ===
许知宁整理好空白答题纸：“独立作答后提交原正式批改；草稿与剧情都不能替代评分。”
+ [带着问题去学习] # choice:continue
  -> peer_method_end
=== peer_method_end ===
这次交谈已经记下。学习入口随时开放；交付首段真实学习成果后，已读支线可留下同伴纪念。
-> END
=== peer_review_start ===
林悦把复盘页留在卷宗旁。你想先复习一张便笺，还是重新整理后再正式作答？
这是内置同伴对话，选择只影响后续台词与纪念；正式学习仍使用原功能。
+ [先梳理与回忆] # choice:method
  -> peer_review_method
+ [先独立练习] # choice:practice
  -> peer_review_practice
=== peer_review_method ===
林悦翻开便笺夹：“先独立回忆，再核对背面，按实际记忆情况评分。”
+ [记下这个方向] # choice:continue
  -> peer_review_end
=== peer_review_practice ===
林悦留出修订页：“根据已有材料和批改反馈修改，再提交正式批改；原评分标准不变。”
+ [带着问题去学习] # choice:continue
  -> peer_review_end
=== peer_review_end ===
这次交谈已经记下。学习入口随时开放；交付首段真实学习成果后，已读支线可留下同伴纪念。
-> END
