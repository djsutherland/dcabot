import asyncio
import logging

import discord
from discord.ext import commands


class DCABot(commands.Bot):
    "Some helpers for Daemon Capture Academy."

    def __init__(
        self,
        *,
        command_prefix="~",
        add_when_mentioned=True,
        noprefix_dms=True,
        **kwargs,
    ):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True

        self.base_prefix = command_prefix
        if noprefix_dms:

            def command_prefix(bot, msg):
                if isinstance(msg.channel, discord.channel.DMChannel):
                    return ""
                elif add_when_mentioned:
                    return commands.when_mentioned(bot, msg) + [self.base_prefix]
                else:
                    return self.base_prefix

        elif add_when_mentioned:
            command_prefix = commands.when_mentioned_or(self.base_prefix)

        super().__init__(intents=intents, command_prefix=command_prefix, **kwargs)
        self.initial_extensions = [
            "dcabot.basics",
            "dcabot.rolling",
            "dcabot.spotlight",
        ]

    async def setup_hook(self):
        async with asyncio.TaskGroup() as tg:
            for ext in self.initial_extensions:
                tg.create_task(self.load_extension(ext))

            if self.base_prefix == "~":
                # don't trigger if a message starts with ~~, i.e. is crossed out
                @self.command(name="~", hidden=True)
                async def noop(ctx):
                    pass

    async def on_ready(self):
        logging.info(f"Logged in as {self.user} ({self.user.id})")
