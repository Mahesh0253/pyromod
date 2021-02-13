"""
pyromod - A monkeypatcher add-on for Pyrogram
Copyright (C) 2020 Cezar H. <https://github.com/usernein>

This file is part of pyromod.

pyromod is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

pyromod is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with pyromod.  If not, see <https://www.gnu.org/licenses/>.
"""

import inspect
import asyncio
import functools
from contextlib import suppress

import pyrogram
from pyrogram.errors import QueryIdInvalid

from ..utils import patch, patchable

import logging
logger = logging.getLogger(__name__)


@patch(pyrogram.client.Client)
class Client:

    @patchable
    def __init__(self, *args, **kwargs):
        self.listening = {}
        self.using_mod = True

        self.old__init__(*args, **kwargs)

    @patchable
    async def listen(self, chat_id, filters=None, timeout=None):
        if type(chat_id) != int:
            chat = await self.get_chat(chat_id)
            chat_id = chat.id

        future = asyncio.get_event_loop().create_future()
        future.add_done_callback(functools.partial(self.clear_listener, chat_id))
        self.listening.update({chat_id: {"future": future, "filters": filters}})
        return await asyncio.wait_for(future, timeout)

    @patchable
    async def ask(self, chat_id, text, filters=None, timeout=None, *args, **kwargs):
        request = await self.send_message(chat_id, text, *args, **kwargs)
        response = await self.listen(chat_id, filters, timeout)
        response.request = request
        return response

    @patchable
    def clear_listener(self, chat_id, future):
        if future == self.listening[chat_id]['future']:
            self.listening.pop(chat_id, None)
            logger.info(f'Closed conversation: {chat_id}')

    @patchable
    def cancel_listener(self, chat_id):
        listener = self.listening.get(chat_id)
        if not listener or listener['future'].done():
            return

        listener['future'].set_exception(asyncio.CancelledError())
        self.clear_listener(chat_id, listener['future'])


@patch(pyrogram.handlers.callback_query_handler.CallbackQueryHandler)
class CallbackQueryHandler:

    @patchable
    def __init__(self, callback: callable, filters=None):
        self.user_callback = callback
        self.old__init__(self.resolve_listener, filters)

    @patchable
    async def resolve_listener(self, client, update, *args):
        try:
            await self.user_callback(client, update, *args)
        except (QueryIdInvalid) as e:
            logger.warning(f'{e.__class__.__name__}')


@patch(pyrogram.handlers.message_handler.MessageHandler)
class MessageHandler:

    @patchable
    def __init__(self, callback: callable, filters=None):
        self.user_callback = callback
        self.old__init__(self.resolve_listener, filters)

    @patchable
    async def resolve_listener(self, client, message, *args):
        # stop outgoing or edited messages
        if message.outgoing or message.edit_date:
            message.stop_propagation()

        listener = client.listening.get(message.chat.id)
        if listener and not listener['future'].done() and not listener['filters']:
            listener['future'].set_result(message)
            return

        elif listener and listener['future'].done():
            client.clear_listener(message.chat.id, listener['future'])

        with suppress(QueryIdInvalid):
            await self.user_callback(client, message, *args)

    @patchable
    async def check(self, client, update):
        listener = client.listening.get(update.chat.id)

        if listener and not listener['future'].done():
            result = await listener['filters'](client, update) if callable(listener['filters']) else True
            if result:
                listener['filters'] = None
                return True

        if callable(self.filters):
            if inspect.iscoroutinefunction(self.filters.__call__):
                return await self.filters(client, update)
            else:
                return await client.loop.run_in_executor(
                    client.executor,
                    self.filters,
                    client, update
                )

        return True


@patch(pyrogram.types.user_and_chats.chat.Chat)
class Chat(pyrogram.types.Chat):

    @patchable
    def listen(self, *args, **kwargs):
        return self._client.listen(self.id, *args, **kwargs)

    @patchable
    def ask(self, *args, **kwargs):
        return self._client.ask(self.id, *args, **kwargs)

    @patchable
    def cancel_listener(self):
        return self._client.cancel_listener(self.id)


@patch(pyrogram.types.user_and_chats.user.User)
class User(pyrogram.types.User):

    @patchable
    def listen(self, *args, **kwargs):
        return self._client.listen(self.id, *args, **kwargs)

    @patchable
    def ask(self, *args, **kwargs):
        return self._client.ask(self.id, *args, **kwargs)

    @patchable
    def cancel_listener(self):
        return self._client.cancel_listener(self.id)


@patch(pyrogram.types.messages_and_media.message.Message)
class Message(pyrogram.types.Message):

    @patchable
    def listen(self, *args, **kwargs):
        return self._client.listen(self.chat.id, *args, **kwargs)

    @patchable
    def ask(self, *args, **kwargs):
        quote = kwargs.pop('quote', None)
        if quote:
            kwargs['reply_to_message_id'] = self.message_id
        return self._client.ask(self.chat.id, *args, **kwargs)

    @patchable
    def cancel_listener(self):
        return self._client.cancel_listener(self.chat.id)