import discord
from discord.ext import commands
import lark

from . import dice


class Rolling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def format_result(self, roll, result):
        if isinstance(roll, dice.CommentedExpr):
            pre_comment = roll.pre_comment
            post_comment = roll.post_comment
            roll = roll.roll
        else:
            pre_comment = None
            post_comment = None

        result_str = dice.get_result_str(roll)

        # TODO: prettier
        s = f"{roll}   ::   {result_str}   =>   got **{result}**"
        if pre_comment:
            s = f"{pre_comment}:   {s}"
        if post_comment:
            s = f"{s}   # {post_comment}"

        return s

    @commands.hybrid_command(aliases=["r"])
    async def roll(
        self,
        ctx,
        *,
        spec: str = commands.parameter(
            description="The dice to roll; try 'd20+12' or '4d6>=5'"
        ),
    ):
        # can't see the slash-command after you do it...
        # ...but there's enough to see they didn't just "roll 20" instead of "roll d20"
        # if ctx.interaction:
        #     await ctx.send(f"Rolling: {spec}")

        try:
            roll = dice.get_dice_tree(spec)
            result = dice.get_eval(roll)

            if isinstance(roll, dice.Concat):
                resp = "\n".join(self.format_result(r, res) for r, res in zip(roll.args, result))
            else:
                resp = self.format_result(roll, result)

            await ctx.reply(resp)
            # TODO: underflow / other reactions

        except lark.UnexpectedInput as e:
            formatted = e.get_context(spec, span=20)
            await ctx.reply(
                f"""Sorry, I don't understand! I think the error might be here:

```
{formatted}

{e}
```"""
            )
            return
        except Exception as e:
            m = "Something broke \N{LOUDLY CRYING FACE}\N{LOUDLY CRYING FACE}\N{LOUDLY CRYING FACE}"
            if str(e):
                m = m + f"\n```{e}```"
            await ctx.reply(m)
            raise e

        



async def setup(bot):
    await bot.add_cog(Rolling(bot))
