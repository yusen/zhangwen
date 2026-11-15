"""Legacy native WebIM live channel; fixed path, no redirects or reconnection.

Wire reference: espressif/esp-claw@f95614dca7b5b5230d1fadf518d87d0a4cda9ecb.
The caller validates a numeric private IPv4 base before opening this channel.
No history, boot identity, execution status or request deduplication is supplied
by this firmware. Only matching chat_id replies are consumed by the service.
"""
import asyncio
import json

import aiohttp
from fastapi import HTTPException


async def deny_redirect(*_):
    # aiohttp's websocket handshake otherwise follows HTTP redirects.
    raise HTTPException(502, '设备实时接口发生重定向，已拒绝；请填写设备直接地址。')


class LegacyChannel:
    def __init__(self, session, socket):
        self.session = session
        self.socket = socket

    @classmethod
    async def open(cls, base, chat_id):
        trace = aiohttp.TraceConfig()
        trace.on_request_redirect.append(deny_redirect)
        session = aiohttp.ClientSession(trust_env=False, timeout=aiohttp.ClientTimeout(total=8, connect=4), trace_configs=[trace])
        try:
            socket = await asyncio.wait_for(session.ws_connect(
                base+'/ws/webim', heartbeat=15, autoping=True, max_msg_size=65536,
                timeout=aiohttp.ClientWSTimeout(ws_close=2)), timeout=8)
            await socket.send_json({'type':'hello', 'chat_id':chat_id})
            return cls(session, socket)
        except BaseException as exc:
            await session.close()
            if isinstance(exc, asyncio.CancelledError):
                raise
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(502, '旧版WebIM状态可读，但实时通道无法连接。请关闭多余设备聊天页后重试，并核对局域网连接。') from exc

    @property
    def closed(self):
        return self.socket.closed

    async def __aiter__(self):
        async for message in self.socket:
            if message.type == aiohttp.WSMsgType.TEXT:
                value = json.loads(message.data)
                if not isinstance(value, dict):
                    raise ValueError('Invalid WebIM event')
                yield value
            elif message.type in {aiohttp.WSMsgType.BINARY, aiohttp.WSMsgType.ERROR}:
                raise ValueError('Invalid WebIM frame')

    async def close(self):
        try:
            await self.socket.close()
        finally:
            await self.session.close()
