from .calender import Calender


def setup(bot):
    bot.add_cog(Calender(bot))