"""更新下载回归：仅临时文件/假响应，验证截断续传、坏分段隔离和完整性保护。"""
import hashlib
import http.client
import io
import tempfile
import threading
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch

from rpg import download
from rpg import update


class Response(io.BytesIO):
    def __init__(self, body, status=200, headers=None):
        super().__init__(body)
        self.status = status
        self.headers = headers or {}


class DownloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name)/'new.zip'
        self.data = b'0123456789'
        self.digest = 'sha256:'+hashlib.sha256(self.data).hexdigest()
        delay=patch.object(download, 'RETRY_DELAY', 0)
        delay.start();self.addCleanup(delay.stop)

    def get(self, responses, size=10, digest=None):
        with patch.object(download.net,'urlopen',side_effect=responses) as request:
            result=download.archive('https://example.test/new.zip',self.file,size,self.digest if digest is None else digest)
        return result,request

    def test_truncated_body_resumes_at_actual_offset(self):
        n,request=self.get([Response(b'0123',headers={'Content-Length':'10'}),
            Response(b'456789',206,{'Content-Range':'bytes 4-9/10'})])
        self.assertEqual(n,10);self.assertEqual(self.file.read_bytes(),self.data)
        self.assertEqual(request.call_args_list[1].args[0].get_header('Range'),'bytes=4-')

    def test_ignored_range_restarts_without_duplicating_prefix(self):
        _,request=self.get([Response(b'0123'),Response(self.data)])
        self.assertEqual(self.file.read_bytes(),self.data)
        self.assertEqual(request.call_count,2)

    def test_wrong_range_is_discarded_before_clean_restart(self):
        _,request=self.get([Response(b'0123'),Response(b'WRONG',206,{'Content-Range':'bytes 5-9/10'}),Response(self.data)])
        self.assertIsNone(request.call_args_list[2].args[0].get_header('Range'))
        self.assertEqual(self.file.read_bytes(),self.data)

    def test_incomplete_read_retains_exception_partial(self):
        class Interrupted(Response):
            def read(self, size=-1):
                raise http.client.IncompleteRead(b'0123',6)
        _,request=self.get([Interrupted(b''),Response(b'456789',206,{'Content-Range':'bytes 4-9/10'})])
        self.assertEqual(request.call_args_list[1].args[0].get_header('Range'),'bytes=4-')
        self.assertEqual(self.file.read_bytes(),self.data)

    def test_digest_failure_restarts_full_download(self):
        _,request=self.get([Response(b'XXXXXXXXXX'),Response(self.data)])
        self.assertIsNone(request.call_args_list[1].args[0].get_header('Range'))
        self.assertEqual(self.file.read_bytes(),self.data)

    def test_finite_failures_report_actual_and_expected_bytes(self):
        with patch.object(download.net,'urlopen',side_effect=[Response(b'0123'),
                Response(b'4',206,{'Content-Range':'bytes 4-9/10'}),
                Response(b'5',206,{'Content-Range':'bytes 5-9/10'})]) as request:
            with self.assertRaisesRegex(download.DownloadError,'已收到6字节，应收10字节；已尝试3次'):
                download.archive('https://example.test/new.zip',self.file,10,self.digest)
            self.assertEqual(request.call_count,3)

    def test_partial_content_metadata_must_match_release_size(self):
        _,request=self.get([Response(b'0123',206,{'Content-Range':'bytes 0-3/999'}),Response(self.data)])
        self.assertIsNone(request.call_args_list[1].args[0].get_header('Range'))
        self.assertEqual(self.file.read_bytes(),self.data)

    def test_size_can_be_inferred_and_stale_destination_is_not_resumed(self):
        self.file.write_bytes(b'previous interrupted download')
        _,request=self.get([Response(b'0123',headers={'Content-Length':'10'}),
            Response(b'456789',206,{'Content-Range':'bytes 4-9/10'})],size=0)
        self.assertIsNone(request.call_args_list[0].args[0].get_header('Range'))
        self.assertEqual(self.file.read_bytes(),self.data)

    def test_not_found_is_not_retried(self):
        error=urllib.error.HTTPError('https://example.test/new.zip',404,'not found',{},None)
        with patch.object(download.net,'urlopen',side_effect=error) as request:
            with self.assertRaisesRegex(download.DownloadError,'HTTP 404'):
                download.archive('https://example.test/new.zip',self.file)
            self.assertEqual(request.call_count,1)

    def test_total_deadline_stops_trickling_download_and_reports_progress(self):
        now=[0]
        def clock():
            now[0]+=4
            return now[0]
        with patch.object(download.time,'monotonic',side_effect=clock),patch.object(download.net,'urlopen',return_value=Response(b'0123')) as request:
            with self.assertRaisesRegex(download.DownloadError,'下载超时'):
                download.archive('https://example.test/new.zip',self.file,10,self.digest,max_seconds=5)
            self.assertEqual(request.call_count,1)
        progress=Mock()
        with patch.object(download.net,'urlopen',return_value=Response(self.data)):
            download.archive('https://example.test/new.zip',self.file,10,self.digest,progress=progress)
        progress.assert_called_once_with(10,10,1)

    def test_oversize_or_bad_checksum_never_succeeds(self):
        for data in (b'overlong data',b'XXXXXXXXXX'):
            with patch.object(download.net,'urlopen',side_effect=lambda *a,**k:Response(data)):
                with self.assertRaises(download.DownloadError):
                    download.archive('https://example.test/new.zip',self.file,10,self.digest)
            self.assertEqual(self.file.read_bytes(),b'')

    def test_real_http_truncation_resumes_and_verifies(self):
        payload=self.data;ranges=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                value=self.headers.get('Range');ranges.append(value)
                self.send_response(206 if value else 200)
                self.send_header('Content-Length','6' if value else '10')
                if value:self.send_header('Content-Range','bytes 4-9/10')
                self.end_headers();self.wfile.write(payload[4:] if value else payload[:4])
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            download.archive('http://127.0.0.1:%d/new.zip'%server.server_port,self.file,10,self.digest)
            self.assertEqual(ranges,[None,'bytes=4-'])
            self.assertEqual(self.file.read_bytes(),payload)
        finally:
            server.shutdown();server.server_close();thread.join(2)


class WindowsUpdateDownloadTest(unittest.TestCase):
    def test_resume_only_hands_off_verified_file_and_failure_keeps_old_exe(self):
        for succeed in (True,False):
            with tempfile.TemporaryDirectory() as folder:
                exe=Path(folder)/'app.exe';exe.write_bytes(b'old executable')
                data=b'0123456789'
                info=dict(newer=True,latest='9.9.9',asset_url='https://example.test/app.exe',size=10,
                    digest='sha256:'+hashlib.sha256(data).hexdigest(),page='https://example.test/release')
                replies=[Response(b'0123'),Response(b'456789',206,{'Content-Range':'bytes 4-9/10'})] if succeed else [Response(b'0123') for _ in range(3)]
                with patch.object(update,'FROZEN',True),patch.object(update,'os',SimpleNamespace(name='nt',getpid=lambda:42)),patch.object(update.sys,'executable',str(exe)),patch.object(update,'check',return_value=info),patch.object(update.net,'urlopen',side_effect=replies),patch.object(update,'launch_swap') as launch,patch.object(update.threading,'Timer') as timer,patch.object(download,'RETRY_DELAY',0):
                    if succeed:
                        self.assertTrue(update._apply()['ok'])
                        self.assertEqual(exe.with_name('app.new.exe').read_bytes(),data)
                        launch.assert_called_once();timer.return_value.start.assert_called_once()
                    else:
                        with self.assertRaisesRegex(update.UpdateError,'下载不完整'):update._apply()
                        launch.assert_not_called();timer.assert_not_called()
                        self.assertFalse(exe.with_name('app.new.exe').exists())
                    self.assertEqual(exe.read_bytes(),b'old executable')


if __name__=='__main__':unittest.main()
