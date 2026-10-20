"""时政地图与批注的自编资料；不含上传讲义、原题或答案。"""


def atlas_data():
    paragraph = '为了保障供给，在主产区布局产能。支持主产区发展产业。'
    themes = [{'id': 't' + str(i), 'name': '自编主题' + str(i), 'question': '如何理解对象？',
               'meaning': '辨清对象和条件。', 'pitfall': '不能随意替换对象。', 'category': key}
              for i, key in enumerate(['goal', 'engine', 'people', 'support', 'world'])]
    categories = [{'id': key, 'name': '自编主线' + str(i), 'question': '关注什么？', 'desc': '自编说明',
                   'color': '#a8791c', 'themes': ['t' + str(i)]}
                  for i, key in enumerate(['goal', 'engine', 'people', 'support', 'world'])]
    material = {'id': 'm1', 'title': '自编政策材料', 'date': '2026-10-20', 'tags': ['t0'], 'why': '政策支持谁？',
                'how': ['识别对象'], 'trap': '不要混淆生产和销售对象', 'chapter': 0, 'original': paragraph,
                'questions': [1], 'originalEmphasis': [[paragraph.index('主产区'), paragraph.index('主产区') + 3]],
                'understanding': {'context': '这是自编的理解练习。', 'actions': ['识别政策对象'],
                                  'distinctions': ['主产区与主销区不是同一个对象'],
                                  'recall': [{'question': '支持谁？', 'answer': '文中指定的对象'}]}}
    return {'categories': categories, 'themes': themes, 'materials': [material],
            'chapters': ['自编会议', '自编讲话', '自编指示', '自编文件'],
            'questions': [{'id': 1, 'material': 'm1', 'text': '自编题：本段支持谁？A.主产区 B.主销区 C.其他 D.全部',
                           'answer': 'A', 'tags': ['t0']}]}
