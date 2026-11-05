import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import urllib.error
from fastapi.testclient import TestClient
from builtii.provider import Gemini, ProviderError
from builtii.web import create_app
from builtii.pdf import Image, render
from .helpers import FakeProvider, make_pdf, page


class ProviderTests(unittest.TestCase):
    def provider(self, transport):
        with patch.dict(os.environ, {"GEMINI_API_KEY":"synthetic-test-key"}):
            return Gemini(opener=transport, sleeper=lambda seconds:None)

    def test_request_contains_no_other_extractor_result_or_boq(self):
        requests=[]
        def transport(request,timeout):
            requests.append(request)
            return io.BytesIO(json.dumps({"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":json.dumps(page())}]}}]}).encode())
        provider=self.provider(transport)
        result=provider.extract("ai2",[Image("test tile",b"synthetic-png")],1,1)
        self.assertEqual(result["page"],1)
        payload=json.loads(requests[0].data)
        self.assertIn("AI2: Independently",payload["contents"][0]["parts"][-1]["text"])
        self.assertNotIn("synthetic-test-key",requests[0].full_url)
        self.assertIn("untrusted",payload["systemInstruction"]["parts"][0]["text"])

    def test_retry_transient_error_only(self):
        calls=[]
        def transport(request,timeout):
            calls.append(1)
            if len(calls)<3:raise urllib.error.HTTPError(request.full_url,429,"test",{},None)
            return io.BytesIO(json.dumps({"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":json.dumps(page())}]}}]}).encode())
        self.provider(transport).extract("ai1",[],1,1)
        self.assertEqual(len(calls),3)

    def test_forbidden_error_is_sanitized_and_not_retried(self):
        calls=[]
        def transport(request,timeout):
            calls.append(1)
            raise urllib.error.HTTPError(request.full_url,403,"secret error body",{},None)
        with self.assertRaisesRegex(ProviderError,"HTTP 403") as error:
            self.provider(transport).extract("ai1",[],1,1)
        self.assertNotIn("secret",str(error.exception))
        self.assertEqual(len(calls),1)

    def test_truncated_output_is_not_accepted(self):
        def transport(request,timeout):
            return io.BytesIO(b'{"candidates":[{"finishReason":"MAX_TOKENS"}]}')
        with self.assertRaisesRegex(ProviderError,"truncated"):
            self.provider(transport).extract("ai1",[],1,1)

    def test_missing_key_is_explicit(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY":""}):
            with self.assertRaisesRegex(ProviderError,"GEMINI_API_KEY"):Gemini()


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.pdf=self.root/"sample.pdf";make_pdf(self.pdf)

    def test_upload_processing_report_and_source_preview(self):
        with TestClient(create_app(self.root/"data",FakeProvider)) as client:
            self.assertEqual(client.get('/').status_code,200)
            self.assertEqual(client.get('/static/app.js').status_code,200)
            response=client.post('/api/jobs',files={'file':('drawing.pdf',self.pdf.read_bytes(),'application/pdf')})
            self.assertEqual(response.status_code,202,response.text)
            job=response.json()['id']
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                status=client.get('/api/jobs/'+job).json()
                if status['state'] in ('completed','incomplete','failed'):break
                time.sleep(.02)
            self.assertEqual(status['state'],'completed',status)
            report=client.get(f'/jobs/{job}/report.json')
            self.assertEqual(report.json()['summary']['supported'],1)
            self.assertIn('Evidence &amp; review',client.get(f'/jobs/{job}/report.html').text)
            self.assertTrue(client.get(f'/jobs/{job}/previews/1.png').content.startswith(b'\x89PNG'))
            self.assertEqual(client.get(f'/jobs/{job}/cache/ai1-1.json').status_code,404)
            self.assertEqual(client.get('/api/jobs/not-a-job').status_code,404)

    def test_invalid_pdf_rejected_and_cleanup(self):
        root=self.root/'data'
        with TestClient(create_app(root,FakeProvider)) as client:
            response=client.post('/api/jobs',files={'file':('fake.pdf',b'bad','application/pdf')})
            self.assertEqual(response.status_code,400,response.text)
            self.assertEqual(list(root.iterdir()),[])

    def test_missing_credentials_not_a_successful_job(self):
        with patch.dict(os.environ,{'GEMINI_API_KEY':''}):
            with TestClient(create_app(self.root/'data')) as client:
                response=client.post('/api/jobs',files={'file':('drawing.pdf',self.pdf.read_bytes(),'application/pdf')})
                self.assertEqual(response.status_code,503)

    def test_cross_origin_spending_rejected(self):
        with TestClient(create_app(self.root/'data',FakeProvider)) as client:
            response=client.post('/api/jobs',headers={'Origin':'https://untrusted.example'},files={'file':('drawing.pdf',self.pdf.read_bytes(),'application/pdf')})
            self.assertEqual(response.status_code,403)

    def test_rotated_pdf_renders_overview_and_details(self):
        import pymupdf
        rotated=self.root/'rotated.pdf'
        with pymupdf.open(self.pdf) as doc:
            doc[0].set_rotation(90);doc.save(rotated)
        images=render(rotated,1,self.root/'previews')
        self.assertGreater(len(images),1)
        self.assertTrue(all(i.data.startswith(b'\x89PNG') for i in images))


if __name__=='__main__':unittest.main()
