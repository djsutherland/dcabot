import enum
import operator
from pathlib import Path
import random

import lark


with open(Path(__file__).parent / "dice.lark") as f:
    parser = lark.Lark(f)  # grammar apparently isn't LALR, not sure why not but oh well


# transforms the parse tree into an abstract dice tree, classes below
class DiceTreeExtractor(lark.Transformer):
    def POSINT(self, tok):
        return int(tok)

    def NATURAL(self, tok):
        return int(tok)

    def DECIMAL(self, tok):
        return float(tok)

    def pre_comment(self, args):
        pre_comment, expr, post_comment = args
        pre_comment = pre_comment.strip()  # probably an easy way to do in lark but eh
        if post_comment:
            post_comment = post_comment.strip()
        return CommentedExpr(expr, pre_comment, post_comment)

    def post_comment(self, args):
        expr, post_comment = args
        post_comment = post_comment.strip()
        return CommentedExpr(expr, post_comment=post_comment)

    def roll(self, args):
        return DiceRoll(*args)

    def roll_explode(self, args):
        return ExplodingDiceRoll(*args)

    def roll_highest(self, args):
        return DiceRollKeepHighest(*args)

    def roll_lowest(self, args):
        return DiceRollKeepLowest(*args)

    def roll_reroll(self, args):
        return DiceRollRerollLowest(*args)

    def hits_cmp(self, args):
        roll, cmp, thresh = args
        if cmp == "≠":
            cmp = "!="
        return NumHits(roll, cmp, thresh)

    def nb_easy(self, args):
        return NumHits(DiceRoll(args[0], 6), ">=", 4)

    def nb_normal(self, args):
        return NumHits(DiceRoll(args[0], 6), ">=", 5)

    def nb_hard(self, args):
        return NumHits(DiceRoll(args[0], 6), ">=", 6)

    def pow(self, args):
        a, b = args
        if is_random(a) or is_random(b):
            return MathOp(Op.POW, [a, b])
        else:
            return a**b

    def neg(self, args):
        (a,) = args
        try:
            return -a
        except TypeError:
            return MathOp(Op.PROD, [-1, a])

    def product(self, args):
        random_parts = []
        value = 1

        it = iter(args)

        arg = next(it)
        if is_random(arg):
            random_parts.append(arg)
        else:
            value *= arg

        while True:
            try:
                op = next(it)
            except StopIteration:
                break
            arg = next(it)

            if op == "/":
                if is_random(arg):
                    random_parts.append(MathOp(Op.POW, [arg, -1]))
                else:
                    value /= arg
            else:
                if is_random(arg):
                    random_parts.append(arg)
                else:
                    value *= arg

        if random_parts:
            if value != 1:
                random_parts.append(value)

            if len(random_parts) == 1:
                return random_parts[0]
            else:
                return MathOp(Op.PROD, random_parts)
        else:
            return value

    def sum(self, args):
        random_parts = []
        value = 0

        it = iter(args)

        arg = next(it)
        if is_random(arg):
            random_parts.append(arg)
        else:
            value += arg

        while True:
            try:
                op = next(it)
            except StopIteration:
                break
            arg = next(it)

            if op == "-":
                if is_random(arg):
                    random_parts.append(MathOp(Op.PROD, [-1, arg]))
                else:
                    value -= arg
            else:
                if is_random(arg):
                    random_parts.append(arg)
                else:
                    value += arg

        if random_parts:
            if value != 0:
                random_parts.append(value)

            if len(random_parts) == 1:
                return random_parts[0]
            else:
                return MathOp(Op.SUM, random_parts)
        else:
            return value

    def list(self, args):
        return Concat(args)


transformer = DiceTreeExtractor()


def get_dice_tree(spec):
    parse_tree = parser.parse(spec)
    if isinstance(parse_tree, lark.Token):  # trasform crashes, bug in lark I guess
        return transformer._call_userfunc_token(parse_tree)
    else:
        return transformer.transform(parse_tree)


################################################################################
### Abstract dice trees


def is_random(obj):
    return getattr(obj, "is_random", False)


def get_eval(obj):
    return obj.eval() if hasattr(obj, "eval") else obj


def get_result_str(obj):
    return obj.result_str() if hasattr(obj, "result_str") else str(obj)


class DiceRoll:
    def __init__(self, num, sides):
        if num is None:
            num = 1
        self.num = num
        self.sides = sides
        self.is_random = True

    def __str__(self):
        return f"{self.num}d{self.sides}"

    def eval(self):
        self.results = [random.randint(1, self.sides) for _ in range(self.num)]
        self.inds_to_keep = frozenset(range(len(self.results)))
        return self._set_total()


    def _set_total(self):
        self.total = sum(r for i, r in enumerate(self.results) if i in self.inds_to_keep)
        return self.total

    def format_single_roll(self, i, r):
        return str(r) if i in self.inds_to_keep else f"~~{r}~~"

    def result_str(self):
        if not hasattr(self, "results"):
            raise ValueError("Roll the dice with eval() first")
        if len(self.results) == 1:
            return f"(**{self.results[0]}**)"
        else:
            bits = [self.format_single_roll(i, r) for i, r in enumerate(self.results)]
            return f"({' + '.join(bits)} => **{self.total}**)"


class ExplodingDiceRoll(DiceRoll):
    def __init__(self, num, sides, explode_thresh, explosions_cap=100):
        super().__init__(num, sides)
        self.explode_thresh = explode_thresh
        self.explosions_cap = explosions_cap
        if self.explode_thresh < 2:
            raise ValueError(
                f"Must explode on at least 2 to avoid infinite dice...got {explode_thresh}"
            )

    def __str__(self):
        return f"{super().__str__()} explode {self.explode_thresh}"

    def eval(self):
        new_results = [random.randint(1, self.sides) for _ in range(self.num)]
        self.results = new_results.copy()
        for explode_iter in range(self.explosions_cap):
            # do any relevant games say "explode <= 10 dice" or something?
            n_to_explode = sum(1 for r in new_results if r >= self.explode_thresh)
            if n_to_explode == 0:
                break
            new_results = [random.randint(1, self.sides) for _ in range(n_to_explode)]
            self.results.extend(new_results)
        else:
            pass  # could warn that we hit the explosions cap

        self.inds_to_keep = frozenset(range(len(self.results)))
        return self._set_total()

    def format_single_roll(self, i, r):
        return f"_{r}_" if r >= self.explode_thresh else str(r)


class DiceRollKeepHighest(DiceRoll):
    def __init__(self, num, sides, num_highest):
        super().__init__(num, sides)
        self.num_highest = num_highest

    def __str__(self):
        return f"{super().__str__()} highest {self.num_highest}"

    def eval(self):
        super().eval()
        argsort = sorted(range(len(self.results)), key=self.results.__getitem__, reverse=True)
        self.inds_to_keep = frozenset(argsort[: self.num_highest])
        return self._set_total()



class DiceRollKeepLowest(DiceRoll):
    def __init__(self, num, sides, num_lowest):
        super().__init__(num, sides)
        self.num_lowest = num_lowest

    def __str__(self):
        return f"{super().__str__()} lowest {self.num_lowest}"

    def eval(self):
        super().eval()
        argsort = sorted(range(len(self.results)), key=self.results.__getitem__)
        self.inds_to_keep = frozenset(argsort[: self.num_lowest])
        return self._set_total()


class DiceRollRerollLowest(DiceRollKeepHighest):
    def __init__(self, num, sides, num_reroll):
        super().__init__(num, sides, num - num_reroll)
        self.num_reroll = num_reroll

    def __str__(self):
        return f"{super().__str__()} reroll {self.num_lowest}"

    def eval(self):
        super().eval()
        new = [random.randint(1, sides) for _ in range(self.num_reroll)]
        self.inds_to_keep = self.inds_to_keep | range(len(self.results), len(self.results) + len(new))
        self.results.extend(new)
        return self._set_total()


class Comparator(enum.StrEnum):
    GT = ">"
    GE = ">="
    LT = "<"
    LE = "<="
    EQ = "="
    NE = "!="


class NumHits:
    def __init__(self, roll: DiceRoll, comp: Comparator, thresh: int):
        self.roll = roll
        self.comp = Comparator(comp)
        self.thresh = thresh
        self.is_random = True

    def __str__(self):
        return f"({self.roll} {self.comp} {self.thresh})"

    def eval(self):
        self.roll.eval()
        op = getattr(operator, self.comp.name.lower())
        self.results = [i in self.roll.inds_to_keep and op(r, self.thresh) for i, r in enumerate(self.roll.results)]
        self.n_hits = sum(1 if is_hit else 0 for is_hit in self.results)
        return self.n_hits

    def result_str(self):
        if not hasattr(self, "results"):
            raise ValueError("Roll the dice with eval() first")

        parts = []
        for i, (r, is_hit) in enumerate(zip(self.roll.results, self.results)):
            if is_hit:
                parts.append(f"**{self.roll.format_single_roll(i, r)}**")
            else:
                parts.append(f"~~{r}~~")
        return f"({' '.join(parts)} => **{self.n_hits} hit{'' if self.n_hits == 1 else 's'}**)"


class Op(enum.StrEnum):
    SUM = "+"
    PROD = "*"
    POW = "^"


class MathOp:
    def __init__(self, op: Op, args):
        self.op = Op(op)
        self.args = args
        self.is_random = any(is_random(a) for a in args)
        # ^ should always be True, otherwise would just be a number, but allowing otherwise

        if self.op == Op.POW and len(self.args) != 2:
            raise ValueError("Raising to a power needs exactly two arguments")

    def __str__(self):
        # TODO: special case - and /
        return f" {self.op} ".join(
            f"({arg})" if isinstance(arg, MathOp) else str(arg) for arg in self.args
        )

    def eval(self):
        evaled_args = [get_eval(arg) for arg in self.args]
        if self.op == Op.SUM:
            return sum(evaled_args)
        elif self.op == Op.PROD:
            prod = 1
            for arg in evaled_args:
                prod *= arg
            return prod
        else:
            assert self.op == Op.POW
            a, b = evaled_args
            return a**b

    def result_str(self):
        return f" {self.op} ".join(
            f"({get_result_str(arg)})"
            if isinstance(arg, MathOp)
            else get_result_str(arg)
            for arg in self.args
        )

class CommentedExpr:
    def __init__(self, roll, pre_comment=None, post_comment=None):
        self.roll = roll
        self.pre_comment = pre_comment
        self.post_comment = post_comment

    def __str__(self):
        s = [str(self.roll)]
        if pre_comment is not None:
            s.insert(0, f"{pre_comment} : ")
        if post_comment is not None:
            s.append(f" # {post_comment}")
        return ''.join(s)

    def eval(self):
        return get_eval(self.roll)

    def result_str(self):
        return get_result_str(self.roll)


class Concat:
    def __init__(self, args):
        self.args = args
        self.is_random = any(is_random(a) for a in args)

    def __str__(self):
        return ",  ".join(str(arg) for arg in self.args)

    def eval(self):
        return [get_eval(arg) for arg in self.args]

    def result_str(self):
        return ",  ".join(get_result_str(arg) for arg in self.args)
