import asyncio
import logging

import discord
from discord.ext import commands


class Basics(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(hidden=True)
    @commands.is_owner()
    async def sync(self, ctx):
        await self.bot.tree.sync()
        await ctx.send("Global command tree synced")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def localsync(self, ctx):
        self.bot.tree.copy_global_to(guild=ctx.guild)
        await self.bot.tree.sync(guild=ctx.guild)
        await ctx.send("Command tree synced locally")

    # https://github.com/Rapptz/RoboDanny/blob/master/cogs/admin.py
    @commands.command(hidden=True)
    @commands.is_owner()
    async def load(self, ctx, *, module : str):
        """Loads a module."""
        try:
            await self.bot.load_extension(module)
        except Exception as e:
            await ctx.send('\N{PISTOL}')
            await ctx.send('{}: {}'.format(type(e).__name__, e))
        else:
            await ctx.send('\N{OK HAND SIGN}')

    @commands.command(hidden=True)
    @commands.is_owner()
    async def unload(self, ctx, *, module : str):
        """Unloads a module."""
        try:
            await self.bot.unload_extension(module)
        except Exception as e:
            await ctx.send('\N{PISTOL}')
            await ctx.send('{}: {}'.format(type(e).__name__, e))
        else:
            await ctx.send('\N{OK HAND SIGN}')

    @commands.command(name='reload', hidden=True)
    @commands.is_owner()
    async def _reload(self, ctx, *, module : str):
        """Reloads a module."""
        try:
            await self.bot.unload_extension(module)
            await self.bot.load_extension(module)
        except Exception as e:
            await ctx.send('\N{PISTOL}')
            await ctx.send('{}: {}'.format(type(e).__name__, e))
        else:
            await ctx.send('\N{OK HAND SIGN}')


class DCABot(commands.Bot):
    "Some helpers for Daemon Capture Academy."

    def __init__(self, *, command_prefix="~", **kwargs):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True

        super().__init__(intents=intents, command_prefix=command_prefix, **kwargs)
        self.initial_extensions = ["dcabot.rolling"]

    async def setup_hook(self):
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.add_cog(Basics(self)))
            for ext in self.initial_extensions:
                tg.create_task(self.load_extension(ext))

    async def on_ready(self):
        logging.info(f"Logged in as {self.user} ({self.user.id})")
