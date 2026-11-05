"""Gemini REST adapter; injectable transport for offline verification."""
import base64
import json
import os
import re
import time
import urllib.error
import urllib.request
from .prompts import SYSTEM, prompt


class ProviderError(RuntimeError):
    pass


class Gemini:
    def __init__(self, opener=None, sleeper=time.sleep):
        self.key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not self.key:
            raise ProviderError("Set GEMINI_API_KEY securely in the server environment")
        self.models = {"ai1": os.environ.get("GEMINI_MODEL", "gemini-2.5-pro"),
                       "ai2": os.environ.get("GEMINI_AUDIT_MODEL", os.environ.get("GEMINI_MODEL", "gemini-2.5-pro"))}
        if any(not re.fullmatch(r"[A-Za-z0-9._-]+", m) for m in self.models.values()):
            raise ProviderError("Invalid model identifier")
        self.opener, self.sleep = opener or urllib.request.urlopen, sleeper

    def extract(self, stage, images, page, total):
        parts = []
        for image in images:
            parts.extend([{"text": image.label}, {"inlineData": {"mimeType": "image/png",
                           "data": base64.b64encode(image.data).decode("ascii")}}])
        parts.append({"text": prompt(stage, page, total)})
        payload = {"systemInstruction": {"parts": [{"text": SYSTEM}]},
                   "contents": [{"role": "user", "parts": parts}],
                   "generationConfig": {"temperature": 0, "responseMimeType": "application/json",
                                        "maxOutputTokens": 32768}}
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.models[stage]}:generateContent",
            data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": self.key})
        for attempt in range(3):
            try:
                with self.opener(req, timeout=180) as response:
                    body = json.load(response)
                break
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                    self.sleep(2 ** (attempt + 1))
                    continue
                raise ProviderError(f"Gemini HTTP {exc.code}; check access, model, quota and billing") from None
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt < 2:
                    self.sleep(2 ** (attempt + 1))
                    continue
                raise ProviderError("Gemini connection failed; check proxy, TLS trust and network access") from None
        candidates = body.get("candidates", [])
        if len(candidates) != 1 or candidates[0].get("finishReason") != "STOP":
            raise ProviderError("Model response blocked, incomplete or truncated; page requires review")
        text = "".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", []) if not p.get("thought"))
        try:
            return json.loads(text, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
        except (ValueError, TypeError):
            raise ProviderError("Model returned invalid JSON; page requires review") from None
