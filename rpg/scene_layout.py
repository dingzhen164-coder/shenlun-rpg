"""主页排布备份：API在存档锁内调用，state.scene_layouts[地图]={desktop,narrow,names}。
本机优先，存档作为换地址/更新后丢失浏览器存储时的默认值；seed仅首次备份，不覆盖已有。
不包含图片/路径，不改学习记录；行测/申论/法考依原存档隔离。
"""
import math
import re


def save(state, body):
    ident = body.get('map')
    if ident not in ('xingce', 'guantu', 'mage', 'fakao'):
        raise ValueError('未知地图')
    source = body.get('layout')
    if not isinstance(source, dict):
        raise ValueError('排布格式不正确')
    result = {'desktop': {}, 'narrow': {}, 'names': {}}
    for profile in ('desktop', 'narrow'):
        points = source.get(profile, {})
        if not isinstance(points, dict) or len(points) > 40:
            raise ValueError('排布格式不正确')
        for key, point in points.items():
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', key) or not isinstance(point, dict):
                raise ValueError('地点格式不正确')
            xy = [point.get(k) for k in ('x', 'y')]
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 100 for v in xy):
                raise ValueError('地点坐标需在0到100之间')
            result[profile][key] = dict(zip(('x', 'y'), xy))
    names = source.get('names', {})
    if not isinstance(names, dict) or len(names) > 40:
        raise ValueError('地点名称格式不正确')
    for key, value in names.items():
        if re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', key) and isinstance(value, str):
            value = re.sub(r'[\x00-\x1f\x7f]', '', value).strip()[:24]
            if value:
                result['names'][key] = value
    layouts = state.setdefault('scene_layouts', {})
    if not body.get('seed') or ident not in layouts:
        layouts[ident] = result
    return layouts[ident]
