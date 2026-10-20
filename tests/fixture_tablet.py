"""平板布局回归的自编PDF；调用方提供临时Game，只在其训练目录生成。"""
import pymupdf


def install(game):
    path = game.paths.train / '手札' / '自编平板讲义.pdf'
    path.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open() as doc:
        for number in range(4):
            page = doc.new_page()
            page.insert_text((50, 70), 'Tablet layout fixture - page %d' % (number + 1), fontsize=18)
            for line in range(25):
                page.insert_text((50, 110 + line * 22), 'Original sample paragraph %d: read, annotate and retain position.' % line)
        doc.save(str(path))
