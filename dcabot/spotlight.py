from collections import OrderedDict
import logging

import discord
from discord.ext import commands

from .utils import LRUCache


_log = logging.getLogger(__name__)

TRACKER_COLOR = 0xFFE657

# no variadic args makes this stupid annoying, so don't support slash commands for now


def maybe_quote(s):
    return f'"{s}"' if " " in s else s


EMOJI_CHECKED = ":ballot_box_with_check:"
EMOJI_UNCHECKED = ":black_large_square:"
SPOTLIGHT_HEADER = "__Spotlight checklist__"
SHUTDOWN_MESSAGE = "Clearing the spotlight tracker; goodnight!"


class NoSpotlightError(ValueError):
    pass


class Spotlight(commands.Cog):
    # this will remember stuff per channel, and recover it if the bot died
    # it's not safe for multiple simultaneous workers as-is
    def __init__(self, bot, cache_size=128):
        self.bot = bot
        self._cache = LRUCache(cache_size)

    async def cog_command_error(self, ctx, exception, /):
        _log.error("Ignoring exception in command %s", ctx.command, exc_info=exception)
        m = "Something broke " + "\N{LOUDLY CRYING FACE}" * 3
        if str(exception):
            m = m + f"\n```{exception}```"
        await ctx.reply(m)

    async def get_spotlight(self, channel, message_limit=200):
        if channel in self._cache:
            return self._cache[channel]

        async for message in channel.history(limit=message_limit):
            if message.author != self.bot.user:
                continue

            if message.content == SHUTDOWN_MESSAGE:
                self._cache[channel] = {}

            if len(message.embeds) != 1:
                continue
            (embed,) = message.embeds
            if embed.title != SPOTLIGHT_HEADER:
                continue

            state = {}
            for line in embed.description.strip().splitlines():
                if line.startswith(EMOJI_CHECKED):
                    p = line[len(EMOJI_CHECKED) :].strip()
                    state[p] = True
                elif line.startswith(EMOJI_UNCHECKED):
                    p = line[len(EMOJI_UNCHECKED) :].strip()
                    state[p] = False
                else:
                    break  # message at the end, or confusion
            self._cache[channel] = state
            return state

        raise NoSpotlightError("No spotlight found in this channel's recent history")

    async def send_tracker(self, ctx, state, message=None):
        self._cache[ctx.channel] = state  # be safe
        await ctx.send(
            message,
            embed=discord.Embed(
                title=SPOTLIGHT_HEADER,
                color=TRACKER_COLOR,
                description="\n".join(
                    f"{EMOJI_CHECKED if st else EMOJI_UNCHECKED} {p}"
                    for p, st in state.items()
                ),
            ),
        )

    async def find_participant(self, ctx, par):
        state = await self.get_spotlight(ctx.channel)
        matches = [p for p in state.keys() if p.lower().startswith(par.lower())]
        if len(matches) > 1:
            await ctx.send(
                f'Error: "{par}" could mean '
                + " or ".join(maybe_quote(p) for p in matches)
                + "; be more specific, please!"
            )
            raise ValueError()
        elif not matches:
            await ctx.send(f"{maybe_quote(par)} doesn't seem to be in the tracker")
            raise ValueError()

        (par,) = matches
        return par

    @commands.group(invoke_without_command=True, aliases=["sp"])
    async def spotlight(self, ctx, *args):
        if not args:
            try:
                state = await self.get_spotlight(ctx.channel)
            except NoSpotlightError:
                await self.start(ctx)
            else:
                await self.send_tracker(ctx, state)

        elif len(args) == 1:
            return await self.mark(ctx, args[0])

        else:
            await ctx.send("Error: not sure how to interpret this command, sorry....")

    @spotlight.command(aliases=["shutdown", "off", "stop", "finish"])
    async def close(self, ctx):
        "Shut down a spotlight tracker."
        self._cache[ctx.channel] = {}
        await ctx.send(SHUTDOWN_MESSAGE)

    @spotlight.command(aliases=["on", "begin"])
    async def start(self, ctx, *participants):
        """
        Start a spotlight tracker.
        You can set participants directly, or add them later.
        If any names have spaces, make sure to use quotes.
        """
        # default to the non-bot people present

        self._cache[ctx.channel] = {}
        await self.add(ctx, *participants)

    @spotlight.command()
    async def add(self, ctx, *participants):
        "Add some new participants to the tracker."
        try:
            state = await self.get_spotlight(ctx.channel)
        except NoSpotlightError:
            state = self._cache[ctx.channel] = {}

        # TODO: refuse to let one person be prefix of another?
        #       that'd break everything...

        to_add = []
        messages = []
        for p in participants:
            if p in state:
                messages.append(
                    f"Warning: {maybe_quote(p)} was already "
                    "in the tracker, ignoring."
                )
            else:
                to_add.append(p)

        if (n := len(state) + len(to_add)) > 15:
            msg = f"{n} is too many spotlight participants, sorry...."
            return await ctx.send(msg)

        for p in to_add:
            state[p] = False
        await self.send_tracker(ctx, state, message="\n".join(messages))

    @spotlight.command()
    async def mark(self, ctx, *participants):
        """
        Check some participants off.
        If you're just doing one, you can just do `spotlight [name]`.
        """
        state = await self.get_spotlight(ctx.channel)

        to_mark = []
        messages = []

        for p in participants:
            try:
                par = await self.find_participant(ctx, p)
            except ValueError:
                return
            if state[par]:
                messages.append(f"{maybe_quote(par)} was already checked.")
            to_mark.append(par)

        for par in to_mark:
            state[par] = True

        if all(state.values()):
            for p in state:
                state[p] = False
            messages.append("Everyone's been checked; wrapping around.")
        return await self.send_tracker(ctx, state, message="\n".join(messages))

    @spotlight.command(aliases=["uncheck", "reset"])
    async def clear(self, ctx, *participants):
        """
        Uncheck some participants (default all).
        """
        state = await self.get_spotlight(ctx.channel)

        warn_on_unchecked = True
        if not participants:
            participants = state.keys()
            warn_on_unchecked = False

        to_unmark = []
        messages = []
        for p in participants:
            try:
                par = await self.find_participant(ctx, p)
            except ValueError:
                return
            if warn_on_unchecked and not state[par]:
                messages.append(f"{maybe_quote(par)} was already unchecked.")
            to_unmark.append(par)

        for par in to_unmark:
            state[par] = False

        return await self.send_tracker(ctx, state, message="\n".join(messages))

    @spotlight.command()
    async def remove(self, ctx, *participants):
        "Delete some participants from the tracker."
        state = await self.get_spotlight(ctx.channel)

        for p in participants:
            try:
                par = await self.find_participant(ctx, p)
            except ValueError:
                pass
            else:
                del state[par]

        return await self.send_tracker(ctx, state)

    @spotlight.command()
    async def rename(self, ctx, old_name, new_name):
        "Rename someone."
        state = await self.get_spotlight(ctx.channel)

        try:
            old_p = await self.find_participant(ctx, old_name)
        except ValueError:
            return

        if new_name in state:
            await ctx.send(
                f"{maybe_quote(new_name)} is already in the tracker! Not renaming."
            )
            return

        state[new_name] = state[old_p]
        del state[old_p]

        return await self.send_tracker(ctx, state)

    @spotlight.command()
    async def sort(self, ctx):
        "Alphabetize the entries in the checklist."
        state = await self.get_spotlight(ctx.channel)
        self._cache[ctx.channel] = new = OrderedDict()
        for k, v in sorted(state.items(), key=lambda kv: kv[0].lower()):
            new[k] = v
        return await self.send_tracker(ctx, new)


async def setup(bot):
    await bot.add_cog(Spotlight(bot))
