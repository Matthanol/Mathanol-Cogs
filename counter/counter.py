from redbot.core import commands, Config


class Counter(commands.Cog):
    """Counter cog to count whatever you want"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=176359585513209856)
        default_guild = {
            "counters": {}
        }
        default_user = {

        }
        self.config.register_guild(**default_guild)
        self.config.register_user(**default_user)

    @commands.command()
    async def count(self, ctx, name, increment = 1):
        """Add an amount to a counter, if you don't specify an amount the default is adding 1"""
        async with self.config.guild(ctx.guild).counters() as counters:
            if counters.get(name) == None:
                counters[name] = 0
            counters[name] += increment
            await ctx.send("current count for {} is {}".format(name, counters[name]))
    @commands.command()
    async def resetCount(self, ctx, name):
        """Sets count back to 0"""
        async with self.config.guild(ctx.guild).counters() as counters:
            counters[name] = 0
            await ctx.send("the counter for {} has been set back to 0".format(name))

    @commands.command()
    async def setCount(self, ctx, name, amount):
        """Set the count to a certain amount"""
        async with self.config.guild(ctx.guild).counters() as counters:
            counters[name] = amount
            await ctx.send("current count for {} is {}".format(name, counters[name]))