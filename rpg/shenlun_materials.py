"""真题只读材料的独立批注校验，由shenlun_bank草稿保存调用。
material_marks={SHA256材料标识:{width:800,height,strokes:[{tool,width,points:[[x,y]]}]}}。
与答案共享revision以防覆盖；不改变题库原文、答题卡确认和评分输入。
"""
import math
import re

def validate(value):
    from .shenlun_bank import BankError
    def fail():raise BankError('材料勾画数据无效或过大，请保留本机草稿后重试')
    def number(v,low,high):
        if type(v) not in (int,float) or not math.isfinite(v) or not low<=v<=high:fail()
        return v
    if not isinstance(value,dict) or len(value)>100:fail()
    result={};count=0
    for key,sheet in value.items():
        if not isinstance(key,str) or not re.fullmatch('[0-9a-f]{64}',key) or not isinstance(sheet,dict):fail()
        if sheet.get('width')!=800:fail()
        height=number(sheet.get('height'),1,30000)
        strokes=sheet.get('strokes')
        if not isinstance(strokes,list) or len(strokes)>10000:fail()
        clean=[]
        for stroke in strokes:
            if not isinstance(stroke,dict) or stroke.get('tool') not in ('pen','highlight','erase'):fail()
            width=number(stroke.get('width'),1,40);points=stroke.get('points')
            if not isinstance(points,list) or not 1<=len(points)<=10000:fail()
            count+=len(points)
            if count>100000:fail()
            pts=[]
            for point in points:
                if not isinstance(point,list) or len(point)!=2:fail()
                pts.append([number(point[0],0,800),number(point[1],0,height)])
            clean.append(dict(tool=stroke['tool'],width=width,points=pts))
        result[key]=dict(width=800,height=height,strokes=clean)
    return result
