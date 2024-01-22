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
    async def load(self, ctx, *, module: str):
        """Loads a module."""
        try:
            await self.bot.load_extension(module)
        except Exception as e:
            await ctx.message.add_reaction("\N{PISTOL}")
            await ctx.send(f"```{type(e).__name__}: {e}```")
        else:
            await ctx.message.add_reaction("\N{OK HAND SIGN}")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def unload(self, ctx, *, module: str):
        """Unloads a module."""
        try:
            await self.bot.unload_extension(module)
        except Exception as e:
            await ctx.message.add_reaction("\N{PISTOL}")
            await ctx.send(f"```{type(e).__name__}: {e}```")
        else:
            await ctx.message.add_reaction("\N{OK HAND SIGN}")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def reload(self, ctx, *, module: str):
        """Reloads a module."""
        try:
            await self.bot.unload_extension(module)
            await self.bot.load_extension(module)
        except Exception as e:
            await ctx.message.add_reaction("\N{PISTOL}")
            await ctx.send((f"```{type(e).__name__}: {e}```"))
        else:
            await ctx.message.add_reaction("\N{OK HAND SIGN}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if (
            payload.event_type != "REACTION_ADD"
            or payload.emoji.name != "\N{CROSS MARK}"
        ):
            return

        # TODO: in discord.py 2.4 we can get the message_author_id directly
        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        if message.author != self.bot.user:
            return

        reactor = payload.member
        if (
            reactor not in message.mentions
            and not await self.bot.is_owner(reactor)
            and not (
                (ref := message.reference)
                and ref.channel_id == payload.channel_id
                and (await channel.fetch_message(ref.message_id)).author == reactor
            )
        ):
            return

        await message.delete()


async def setup(bot):
    await bot.add_cog(Basics(bot))
