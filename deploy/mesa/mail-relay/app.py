"""Verified Resend notifications -> stock Rails ActionMailbox MIME ingress."""
import os
import json
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from email import policy
from email.parser import BytesHeaderParser
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from svix.webhooks import Webhook, WebhookVerificationError

MAX_WEBHOOK_BYTES = 256 * 1024
MAX_EMAIL_BYTES = 25 * 1024 * 1024


@dataclass(frozen=True)
class Settings:
    api_key: str
    webhook_secret: str
    ingress_password: str
    mailbox: str

    @classmethod
    def from_env(cls):
        return cls(*(os.environ[name] for name in (
            'RESEND_API_KEY', 'RESEND_WEBHOOK_SECRET',
            'RAILS_INBOUND_EMAIL_PASSWORD', 'SUPPORT_EMAIL',
        )))

    def recipient(self, data):
        # received_for is the SMTP envelope (also covers BCC/forwarded messages).
        addresses = data.get('received_for') or data.get('to', [])
        domain = self.mailbox.split('@')[1]
        for address in addresses:
            if not isinstance(address, str):
                continue
            address = address.lower()
            if address == self.mailbox:
                return address
            if re.fullmatch(r'reply\+[0-9a-f-]{36}@' + re.escape(domain), address):
                try:
                    UUID(address.split('@')[0][6:])
                    return address
                except ValueError:
                    pass
        return None


def envelope_header(raw, recipient):
    # Preserve the original MIME bytes, attachment encodings, message ID and
    # references. Only replace routing headers with the authenticated envelope.
    separator = b'\r\n\r\n' if b'\r\n\r\n' in raw else b'\n\n'
    if separator not in raw:
        raise HTTPException(502, 'Received email has no MIME header separator')
    head, body = raw.split(separator, 1)
    newline = b'\r\n' if separator == b'\r\n\r\n' else b'\n'
    lines, keep = [], True
    for line in head.split(newline):
        if not line.startswith((b' ', b'\t')):
            keep = line.split(b':', 1)[0].lower() != b'x-original-to'
        if keep:
            lines.append(line)
    headers = BytesHeaderParser(policy=policy.default).parsebytes(head + separator)
    if not headers.get('To'):
        lines.append(b'To: ' + recipient.encode('ascii'))
    lines.append(b'X-Original-To: ' + recipient.encode('ascii'))
    return newline.join(lines) + separator + body


def create_app(settings, transport=None):
    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(45, connect=10), follow_redirects=False,
            limits=httpx.Limits(max_connections=4), transport=transport,
        ) as client:
            app.state.client = client
            yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    verifier = Webhook(settings.webhook_secret)

    @app.get('/health')
    async def health():
        return {'status': 'ok'}

    @app.post('/email-ingress/resend')
    async def receive(request: Request):
        payload = bytearray()
        async for chunk in request.stream():
            payload.extend(chunk)
            if len(payload) > MAX_WEBHOOK_BYTES:
                raise HTTPException(413, 'Webhook too large')
        try:
            body = bytes(payload).decode('utf-8')
            verifier.verify(body, dict(request.headers))
            event = json.loads(body)
        except (WebhookVerificationError, ValueError, UnicodeDecodeError):
            raise HTTPException(401, 'Invalid webhook signature') from None
        if not isinstance(event, dict):
            raise HTTPException(422, 'Invalid event')
        if event.get('type') != 'email.received':
            return Response(status_code=204)
        data = event.get('data')
        if not isinstance(data, dict):
            raise HTTPException(422, 'Missing event data')
        recipient = settings.recipient(data)
        if not recipient:
            return Response(status_code=204)
        try:
            email_id = str(UUID(data['email_id']))
        except (KeyError, ValueError, TypeError, AttributeError):
            raise HTTPException(422, 'Invalid email ID') from None
        client = request.app.state.client
        try:
            metadata = await client.get(
                'https://api.resend.com/emails/receiving/' + email_id,
                headers={'Authorization': 'Bearer ' + settings.api_key},
            )
            metadata.raise_for_status()
            email = metadata.json()
            if email['id'] != email_id or settings.recipient(email) != recipient:
                raise HTTPException(502, 'Received email envelope mismatch')
            download_url = email['raw']['download_url']
            url = urlsplit(download_url)
            # Resend returns a signed URL on its CDN (or a CloudFront distribution).
            if (url.scheme != 'https' or url.username or url.password or
                url.port not in (None, 443) or not url.hostname or
                not (url.hostname == 'cdn.resend.app' or
                     url.hostname.endswith(('.cloudfront.net', '.resend.com')))):
                raise HTTPException(502, 'Unexpected raw email host')
            raw = bytearray()
            async with client.stream('GET', download_url) as download:
                download.raise_for_status()
                async for chunk in download.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > MAX_EMAIL_BYTES:
                        raise HTTPException(413, 'Email too large')
            result = await client.post(
                'http://rails:3000/rails/action_mailbox/relay/inbound_emails',
                content=envelope_header(bytes(raw), recipient),
                auth=('actionmailbox', settings.ingress_password),
                headers={'Content-Type': 'message/rfc822', 'X-Forwarded-Proto': 'https'},
            )
            result.raise_for_status()
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            # No message bodies, URLs, credentials or customer details in logs.
            # A non-2xx response lets Resend retry. Rails deduplicates MIME deliveries.
            raise HTTPException(502, 'Email transfer failed; retry delivery') from None
        return Response(status_code=204)

    return app


def app_factory():
    return create_app(Settings.from_env())
