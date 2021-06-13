import uuid
from redbot.core import commands, Config
from discord import File, TextChannel
from datetime import datetime, timedelta
from dateutil import tz
import ics
import io
from enum import Enum
import typing

timeFormat = "%Y-%m-%d %H:%M"
icsFormat =  "%Y-%m-%d %H:%M:%S"
class Calender(commands.Cog):
    """Calender cog to make and manage events"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=176359585513209856)
        default_guild = {
            "events": {},
            "serverTimezone": "UTC",
            "additionalTimezones": []
        }
        default_user = {
            "timezone": "UTC",
            "events": {}
        }
        self.config.register_guild(**default_guild)
        self.config.register_user(**default_user)

    @commands.command()
    async def createEvent(self, ctx, name, time, date, duration:typing.Optional[int]=1, channel: TextChannel = None):
        """[p]createEvent <eventName> <hh:mm> <yyyy-mm-dd> duration=[hours] channel=[#channel] \n Used to create a new event that will be added to the guild calendar. An invite will be returned so it can be added to your personal agenda."""

        event = Event()
        event.name = name
        event.startDateTime = datetime.strptime(date+" "+time, timeFormat)
        event.endDateTime = event.startDateTime + timedelta(hours=duration)
        event.organizer = Attendee(ctx.author.id)
        event.timeZone = await self.config.user(ctx.author).timezone()
        async with self.config.user(ctx.author).events() as events:
            events[event.id] = event.toJsonSerializable()
        async with self.config.guild(ctx.guild).events() as events:
            events[event.id] = event.toJsonSerializable()
        print(event.toJsonSerializable())
        file = io.StringIO(str(ics.Calendar(events=[event.toICSEvent()])))
        if channel != None:
            await channel.send("Event created", file=File(fp=file, filename=event.name+".ics"))
        else:
            await ctx.send("Event created", file=File(fp=file, filename=event.name+".ics"))

    @commands.command()
    async def setPersonalTimezone(self, ctx, timezone):
        """Set your personal timezone"""
        if(tz.gettz(timezone) != None):
            await self.config.user(ctx.author).timezone.set(timezone)
            await ctx.send("The time zone of " + ctx.author.mention + " is now set to: " + timezone)
        else:
            await ctx.send("That time zone or time zone format is not supported")


class Status(Enum):
    COMMING = "y"
    MAYBE = "m"
    DECLINED = "n"

class Attendee():
    userIdL: int
    status: Status = Status.COMMING

    def __init__(self, userId):
        self.userId = userId

    def setStatus(self, status: Status):
        self.status = status
        return self

    def __repr__(self):
        items = ("%s = %r" % (k, v) for k, v in self.__dict__.items())
        return "<%s: {%s}>" % (self.__class__.__name__, ', '.join(items))

class Event():
    id: str
    name: str
    startDateTime: datetime
    endDateTime: datetime
    timeZone: str
    organizer: Attendee
    attendees: [Attendee] = []

    def __init__(self):
        self.id = uuid.uuid4().hex

    def toJsonSerializable(self):
        result = dict(self.__dict__)
        result["startDateTime"] = self.startDateTime.strftime(timeFormat)
        result["endDateTime"] = self.endDateTime.strftime(timeFormat)
        result["organizer"] = self.organizer.__dict__
        result["attendees"] = [attendee.__dict__ for attendee in self.attendees]
        return result

    def fromJsonSerializable(self, input:dict):
        input["startDateTime"] = datetime.strptime(result["startDateTime"], timeFormat)
        input["endDateTime"] = datetime.strptime(result["endDateTime"], timeFormat)


    

    def toICSEvent(self):
        event = ics.Event()
        event.name = self.name
        start_dt = self.startDateTime.replace(tzinfo=tz.gettz(self.timeZone))
        start_dt = start_dt.astimezone(tz.tzutc())
        event.begin = start_dt.strftime(icsFormat)
        end_dt = self.endDateTime.replace(tzinfo=tz.gettz(self.timeZone))
        end_dt = end_dt.astimezone(tz.tzutc())
        event.end = end_dt.strftime(icsFormat)
        return event




