"""桌面更新包下载：有限重试、校验断点和完整性；由两项目update.py调用。

只写调用方提供的临时文件，不替换应用。收到完整数据并通过发布摘要后才返回。
Range被忽略时重新下载；错误分段、超长或摘要不符时丢弃本次数据，绝不拼接后安装。
"""
import hashlib
import http.client
import re
import time
import urllib.error
import urllib.request

from . import net

RETRY_DELAY = 0.25


class DownloadError(Exception):
    pass


def archive(url, destination, size=0, digest='', user_agent='rpg', attempts=3, max_seconds=300, progress=None):
    total = int(size or 0)
    expected = digest[7:].lower() if digest.startswith('sha256:') else ''
    if total < 0 or (expected and not re.fullmatch(r'[0-9a-f]{64}', expected)):
        raise DownloadError('发布校验信息不正确')
    destination.write_bytes(b'')
    deadline = time.monotonic() + max_seconds
    last_error = ''
    for attempt in range(attempts):
        last_error = ''
        offset = destination.stat().st_size
        headers = {'User-Agent': user_agent, 'Accept-Encoding': 'identity', 'Cache-Control': 'no-cache'}
        if offset:
            headers['Range'] = 'bytes=%d-' % offset
        restart = False
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise DownloadError('下载超时，已停止；请稍后重试或更换网络')
        try:
            req = urllib.request.Request(url, headers=headers)
            with net.urlopen(req, timeout=min(30, remaining)) as response:
                status = getattr(response, 'status', None) or 200
                fields = getattr(response, 'headers', {})
                if status == 206:
                    match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', fields.get('Content-Range', ''))
                    if not match:
                        restart = True
                        raise DownloadError('下载分段缺少有效范围')
                    first, end, length = map(int, match.groups())
                    if first != offset or end < first or end >= length or (total and length != total):
                        restart = True
                        raise DownloadError('下载分段与请求或发布大小不一致')
                    total = total or length
                    limit = end + 1
                elif status == 200:
                    # 有的下载源忽略Range，返回整个包：清空临时文件，避免重复拼接。
                    offset = 0
                    length = fields.get('Content-Length', '')
                    if not total and str(length).isdigit():
                        total = int(length)
                    limit = total
                else:
                    raise DownloadError('下载源回应HTTP %s' % status)
                with destination.open('ab' if offset else 'wb') as output:
                    def write(chunk):
                        nonlocal offset, restart
                        if time.monotonic() >= deadline:
                            raise DownloadError('下载超时')
                        if limit and offset + len(chunk) > limit:
                            restart = True
                            raise DownloadError('下载数据超过预期范围')
                        output.write(chunk)
                        offset += len(chunk)
                        if progress:
                            progress(offset, total, attempt + 1)
                    try:
                        while True:
                            chunk = response.read(1 << 16)
                            if not chunk:
                                break
                            write(chunk)
                    except http.client.IncompleteRead as error:
                        # 保留异常携带的最后一段，下一次从实际已写入的位置续传。
                        write(error.partial)
                        last_error = '连接提前结束'
        except urllib.error.HTTPError as error:
            last_error = '下载源回应HTTP %s' % error.code
            if error.code not in (408, 416, 429) and error.code < 500:
                raise DownloadError(last_error)
            if error.code == 416:
                restart = True
        except (OSError, http.client.HTTPException, DownloadError) as error:
            last_error = str(error)[:160]
        if restart:
            destination.write_bytes(b'')
        actual = destination.stat().st_size
        if time.monotonic() >= deadline:
            raise DownloadError('下载超时（已收到%d字节，应收%s）；已停止，请稍后重试或更换网络' % (actual, str(total)+'字节' if total else '完整安装包'))
        if not restart and (actual == total if total else actual > 0):
            if expected:
                checksum = hashlib.sha256()
                with destination.open('rb') as source:
                    for chunk in iter(lambda: source.read(1 << 16), b''):
                        checksum.update(chunk)
                if checksum.hexdigest() != expected:
                    last_error = '下载校验不通过'
                    destination.write_bytes(b'')
                else:
                    return actual
            elif not last_error or total:
                return actual
        if attempt + 1 < attempts:
            time.sleep(RETRY_DELAY * (attempt + 1))
    actual = destination.stat().st_size
    if last_error == '下载校验不通过':
        raise DownloadError('下载校验不通过；已尝试%d次' % attempts)
    message = '下载不完整（已收到%d字节，应收%s；已尝试%d次）' % (actual, str(total)+'字节' if total else '完整安装包', attempts)
    raise DownloadError(message + ('；' + last_error if last_error else ''))
