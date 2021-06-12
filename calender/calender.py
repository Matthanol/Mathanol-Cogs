from redbot.core import commands
from discord import File, TextChannel
from os import path, getcwd
from datetime import datetime, timedelta
from dateutil import tz
import io
import ics

# Format the ics module expects the dates to be in
date_format = '%Y-%m-%d %H:%M:%S'


def getGuildName(guild):
    return str(guild.id)


def createEmptyCalender(name):
    c = ics.Calendar()
    saveCalender(name, c)


def getFilePath(name):
    return getcwd()+"/calender/calenders/"+str(name)+".ics"


def saveCalender(name, c):
    with open(getFilePath(name), 'w+') as f:
        f.write(str(c))


def openCalender(name):
    return ics.Calendar((open(getFilePath(name), "r")).read())


class Calender(commands.Cog):
    """Calender cog to make and manage events"""

    def __init__(self, bot):
        self.bot = bot

    # @commands.command()
    # async def hello(self, ctx):
    #     c = Calendar()
    #     with open('my.ics', 'w') as f:
    #         f.write(str(c))
    #     file = File(fp = (open('my.ics', "rb")), spoiler = False)
    #     await ctx.send("world", file=file)

    @commands.command()
    async def createCalender(self, ctx):

        if(ctx.guild == None):
            await ctx.send("Command should be run in a guild")
            return
        cName = getGuildName(ctx.guild)

        if(path.isfile(getFilePath(cName))):
            await ctx.send("There is already a calender for this guild, to overwrite it use [p]forceCreateCalender")
            return
        createEmptyCalender(cName)
        await ctx.send("Calender created")

    @commands.command()
    async def forceCreateCalender(self, ctx):
        if(ctx.guild == None):
            await ctx.send("Command should be run in a guild")
            return
        cName = getGuildName(ctx.guild)
        createEmptyCalender(cName)
        await ctx.send("Calender created")

    @commands.command()
    async def getServerCalenderFile(self, ctx):
        file = File(fp=(open(getFilePath(ctx.guild.id), "rb")),
                    filename=ctx.guild.name + "_calender.ics", spoiler=False)
        await ctx.send("Here's the whole server calender", file=file)

    @commands.command(attrs=["name", "time", "date", "channel"])
    async def createEvent(self, ctx, name, time, date, channel: TextChannel = None):
        """[p]createEvent <eventName> <hh:mm> <yyyy-mm-dd> [channel] """
        cal = openCalender(ctx.guild.id)
        event = ics.Event()

        event.name = name
        start_str = date + " " + time+":00"
        start_dt = datetime.strptime(start_str, date_format).replace(
            tzinfo=tz.gettz('Europe/Brussels'))
        start_dt = start_dt.astimezone(tz.tzutc())

        event.begin = start_dt.strftime(date_format)
        event.end = (start_dt + timedelta(hours=1)).strftime(date_format)
        cal.events.add(event)
        saveCalender(ctx.guild.id, cal)
        file = io.StringIO(str(ics.Calendar(events=[event])))
        if channel != None:
            print(channel)
            await channel.send("Event created", file=File(fp=file, filename=event.name+".ics"))

        else:
            await ctx.send("Event created", file=File(fp=file, filename=event.name+".ics"))
