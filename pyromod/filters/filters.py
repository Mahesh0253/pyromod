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
import re
from typing import Pattern

import pyrogram
from pyrogram.types import Message, CallbackQuery, InlineQuery, Update


########################################## regex filter ##############################################
def regex(pattern, flags=0):
    """Filter updates that match a given regular expression pattern.

    Can be applied to handlers that receive one of the following updates:

    - :obj:`~pyrogram.types.Message`: The filter will match ``text`` or ``caption``.
    - :obj:`~pyrogram.types.CallbackQuery`: The filter will match ``data``.
    - :obj:`~pyrogram.types.InlineQuery`: The filter will match ``query``.

    When a pattern matches, all the `Match Objects <https://docs.python.org/3/library/re.html#match-objects>`_ are
    stored in the ``matches`` field of the update object itself.

    Parameters:
        pattern (``str`` | ``Pattern``):
            The regex pattern as string or as pre-compiled pattern.

        flags (``int``, *optional*):
            Regex flags.
    """

    async def func(flt, _, update: Update):
        if isinstance(update, Message):
            value = update.text
        elif isinstance(update, CallbackQuery):
            value = update.data
        elif isinstance(update, InlineQuery):
            value = update.query
        else:
            raise ValueError(f"Regex filter doesn't work with {type(update)}")

        if value:
            update.matches = list(flt.p.finditer(value)) or None

        return bool(update.matches)

    return pyrogram.filters.create(
        func,
        "RegexFilter",
        p=pattern if isinstance(pattern, Pattern) else re.compile(pattern, flags),
    )


pyrogram.filters.regex = regex


######################################### file filter ##################################################
async def file_filter(_, bot, message: Message):
    if not message.media:
        return False

    available_media = ("audio", "document", "photo", "sticker", "animation", "video", "voice", "video_note",
                       "new_chat_photo")

    for media_type in available_media:
        media = getattr(message, media_type, None)
        if media is not None:
            message.media_type = media_type
            message.file = media
            return True

    return False


pyrogram.filters.file = pyrogram.filters.create(file_filter)