import discord
from discord.ext import commands
import lark

from .dice import get_dice_tree, get_eval, get_result_str


class Rolling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(aliases=["r"])
    async def roll(
        self,
        ctx,
        *,
        spec: str = commands.parameter(
            description="The dice to roll; try 'd20+12' or '4d6>=5'"
        ),
    ):
        if ctx.interaction:
            await ctx.send(f"Rolling: {spec}")

        try:
            roll = get_dice_tree(spec)

            results = get_eval(roll)
            result_str = get_result_str(roll)
            # TODO: prettier format, especially for lists!

            await ctx.reply(f"""
            {roll}     ::      {result_str}   =>   got **{results}**
            """.strip())
            # TODO: underflow / other reactions

        except lark.UnexpectedInput as e:
            formatted = e.get_context(spec, span=20)
            await ctx.reply(f"""Sorry, I don't understand! I think the error might be here:

```
{formatted}

{e}
```""")
            return
        except Exception as e:
            await ctx.reply(f"Something broke \N{LOUDLY CRYING FACE}\N{LOUDLY CRYING FACE}\N{LOUDLY CRYING FACE}  {e}".strip())
            raise e



async def setup(bot):
    await bot.add_cog(Rolling(bot))
