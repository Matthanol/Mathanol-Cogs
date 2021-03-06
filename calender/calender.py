import uuid
from redbot.core import commands, Config
from discord import File, TextChannel, PartialMessage
from discord.ext.commands import MissingPermissions
import discord
from datetime import datetime, timedelta
from dateutil import tz
import ics
import io
import typing
import asyncio
import logging


timeFormat = "%Y-%m-%d %H:%M"
icsFormat = "%Y-%m-%d %H:%M:%S"
eventCreatedMessage = "Event \"{}\" was created.\n At this moment there are {} that have accepted"



def getMessageUid(message):
    return str(message.channel.id) + str(message.id)

def get_key_from_value(d, val):
    keys = [k for k, v in d.items() if v == val]
    if keys:
        return keys[0]
    return None


class Attendee():
    userId: int
    status:str

    def setStatus(self, status):
        self.status = status
        return self

    def setId(self, id):
        self.userId = id
        return self

    def __repr__(self):
        items = ("%s = %r" % (k, v) for k, v in self.__dict__.items())
        return "<%s: {%s}>" % (self.__class__.__name__, ', '.join(items))
    
    def fromJsonSerializable(self, input: dict):
        for prop in input:
            self.__dict__[prop] = input[prop]
        return self



class Event():
    id: str
    name: str
    startDateTime: datetime
    endDateTime: datetime
    timezone: str
    organizer: Attendee
    attendees: [Attendee] = []

    def __init__(self):
        self.id = uuid.uuid4().hex

    def toJsonSerializable(self):
        result = dict(self.__dict__)
        result["startDateTime"] = self.startDateTime.strftime(timeFormat)
        result["endDateTime"] = self.endDateTime.strftime(timeFormat)
        result["organizer"] = self.organizer.__dict__
        result["attendees"] = [
            attendee.__dict__ for attendee in self.attendees]
        return result

    def fromJsonSerializable(self, input: dict):
        input["startDateTime"] = datetime.strptime(
            input["startDateTime"], timeFormat)
        input["endDateTime"] = datetime.strptime(
            input["endDateTime"], timeFormat)
        input["organizer"] = Attendee().fromJsonSerializable(input["organizer"])
        input["attendees"] = [Attendee().fromJsonSerializable(attendee) for attendee in input["attendees"]]
        for prop in input:
            self.__dict__[prop] = input[prop]
        return self

    def toICSEvent(self):
        event = ics.Event()
        event.name = self.name
        start_dt = self.startDateTime.replace(tzinfo=tz.gettz(self.timezone))
        start_dt = start_dt.astimezone(tz.tzutc())
        event.begin = start_dt.strftime(icsFormat)
        end_dt = self.endDateTime.replace(tzinfo=tz.gettz(self.timezone))
        end_dt = end_dt.astimezone(tz.tzutc())
        event.end = end_dt.strftime(icsFormat)
        return event




class Calender(commands.Cog):
    """Calender cog to make and manage events"""

    # caching stuff
    reactions = {}
    channels = {}
    userTimezones = {}



    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=176359585513209856)
        default_guild = {
            "events": {},
            "calenderMessages": {},
            "statusReactions" : {   "accepted": "???",
                                    "maybe":"????",
                                    "declined":"???"}
            
        }
        default_user = {
            "timezone": None,
            "events": {}
        }
        self.config.register_guild(**default_guild)
        self.config.register_user(**default_user)

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def resetDB(self, ctx):
        """[p]resetDB resets the database for your guild"""
        await self.config.clear_all_guilds()
        await ctx.send("guild db reset")

    @commands.group(pass_context=True)
    async def calendar(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('Invalid sub command passed...')

    @calendar.command()
    async def createEvent(self, ctx:discord.ext.commands.Context, name, time, date, duration: typing.Optional[int] = 1, channel: TextChannel = None):
        """[p]createEvent <eventName> <hh:mm> <yyyy-mm-dd> duration=[hours] channel=[#channel] \n Used to create a new event that will be added to the guild calendar. An invite will be returned so it can be added to your personal agenda."""
        if await self.getUserTimezone(ctx.author) == None:
            ctx.send("Please configure a timezone with {}calendar setPersonalTimezone before you create an event".format(ctx.clean_prefix()))
        event:Event = Event()
        event.name = name
        event.startDateTime = datetime.strptime(date+" "+time, timeFormat)
        event.endDateTime = event.startDateTime + timedelta(hours=duration)
        event.organizer = Attendee().setId(ctx.author.id)
        event.timezone = await self.getUserTimezone(ctx.author)
        async with self.config.user(ctx.author).events() as events:
            events[event.id] = event.toJsonSerializable()
        async with self.config.guild(ctx.guild).events() as events:
            events[event.id] = event.toJsonSerializable()
        reactions = await self.getReactionsFromGuild(ctx.guild.id) 
        file = io.StringIO(str(ics.Calendar(events=[event.toICSEvent()])))
        message:discord.Message
        embed = await self.createEventEmbed(ctx.guild ,ctx.channel, event)
        if channel == None:
            channel = ctx.channel
        message = await channel.send(embed=embed, file=File(fp=file, filename=event.name+".ics"))
        
        for status in reactions:
            asyncio.create_task(message.add_reaction(reactions[status]))
        
        async with self.config.guild(ctx.guild).calenderMessages() as messages:
            messages[getMessageUid(message)] = {"event": event.id}

    @calendar.command()
    async def deleteEvent(self, ctx):
        reference = await ctx.fetch_message(ctx.message.reference.message_id)
        async with self.config.guild(ctx.guild).calenderMessages() as messages:
            messageUID = getMessageUid(reference)
            eventId = messages[messageUID]["event"]
            del messages[messageUID]
        asyncio.create_task( reference.delete())
        asyncio.create_task( ctx.message.delete())
        async with self.config.guild(ctx.guild).events() as events:
           del events[eventId]
        

    @calendar.command()
    async def setPersonalTimezone(self, ctx, timezone):
        """Set your personal timezone"""
        if(tz.gettz(timezone) != None):
            await self.config.user(ctx.author).timezone.set(timezone)
            await ctx.send("The time zone of " + ctx.author.mention + " is now set to: " + timezone)
        else:
            await ctx.send("That time zone or time zone format is not supported")
    
    @calendar.command()
    async def removePersonalTimezone(self, ctx, timezone):
        """Set your personal timezone"""

        await self.config.user(ctx.author).timezone.set(timezone)
        await ctx.send("The time zone of " + ctx.author.mention + " is removed")


    @commands.Cog.listener(name="on_raw_reaction_add")
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        reactions = await self.getReactionsFromGuild(payload.guild_id)
        if not(str(payload.emoji) in reactions.values()):
            return
        if payload.member.id == self.bot.user.id:
            return
        channel: TextChannel = await self.getChannel(payload.channel_id)
        message: PartialMessage = channel.get_partial_message(
            payload.message_id)
        configMessage = (await self.config.guild_from_id(payload.guild_id).calenderMessages()).get(getMessageUid(message))
        if(configMessage == None):
            return
        event = Event().fromJsonSerializable(
            (await self.config.guild_from_id(payload.guild_id).events())[configMessage["event"]])
        reactions = await self.getReactionsFromGuild(payload.guild_id)
        foundAttendee = False
        for existingAttendee in event.attendees:
            if existingAttendee.userId == payload.user_id:
                if not(channel.permissions_for(channel.guild.get_member(self.bot.user.id)).manage_messages):
                    asyncio.create_task(channel.send("Cannot automatically remove old reaction without \"manage messages\" permission"))
                else:
                    for status in reactions:
                        if reactions[status] != str(payload.emoji):
                            asyncio.create_task(message.remove_reaction(reactions[status], payload.member) )
                    existingAttendee.setStatus(get_key_from_value(reactions, str(payload.emoji)))
                foundAttendee = True
        if not(foundAttendee):
            newAttendee = Attendee().setId(payload.user_id).setStatus(get_key_from_value(reactions, str(payload.emoji)))
            event.attendees.append(newAttendee)
        asyncio.create_task(message.edit(embed= await self.createEventEmbed(channel.guild, channel,  event)))
        async with self.config.guild_from_id(payload.guild_id).events() as events:
            events[event.id] = event.toJsonSerializable()
    
  
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        reactions = await self.getReactionsFromGuild(payload.guild_id)
        if not(str(payload.emoji) in reactions.values()):
            return
        
        channel: TextChannel = await self.getChannel(payload.channel_id)
        message: PartialMessage = channel.get_partial_message(
            payload.message_id)
        for reaction in (await message.fetch()).reactions:
            async for member in reaction.users():
                if member.id == payload.user_id:
                    return
                    
        configMessage = (await self.config.guild_from_id(payload.guild_id).calenderMessages()).get(getMessageUid(message))
        if(configMessage == None):
            return
        event = Event().fromJsonSerializable(
            (await self.config.guild_from_id(payload.guild_id).events())[configMessage["event"]])
        reactions = await self.getReactionsFromGuild(payload.guild_id)
        for existingAttendee in event.attendees:
            if existingAttendee.userId == payload.user_id:
                del event.attendees[event.attendees.index(existingAttendee)]
        asyncio.create_task(message.edit(embed= await self.createEventEmbed( channel.guild, channel,  event)))
        async with self.config.guild_from_id(payload.guild_id).events() as events:
            events[event.id] = event.toJsonSerializable()


    @calendar.command()
    async def getAllEvents(self, ctx):
        message = ""
        events = await self.config.guild(ctx.guild).events()
        for eventId in events:
            event = Event().fromJsonSerializable(events[eventId])
            print(events[eventId])
            message += "{}: {} until {} {}".format(event.name, str(event.startDateTime),str(event.endDateTime), event.timezone )+ "\n"
        if len(events) == 0:
            message = "no events in calender"
        await ctx.send(message)
    
    # @calendar.command()
    # async def getAllMessages(self, ctx):
    #     message = ""
    #     messages = await self.config.guild(ctx.guild).calenderMessages()
    #     for messageId in messages:
    #         calMessage = messages[messageId]
    #         message += messageId + " "+ str(calMessage) + "\n"
    #     if len(messages) == 0:
    #         message = "no messages saved"
    #     await ctx.send(message)

    

    async def getReactionsFromGuild(self, guildId):
        if self.reactions.get(guildId) == None:
            self.reactions[guildId] = await self.config.guild_from_id(guildId).statusReactions()
        return self.reactions[guildId]
    
    async def getChannel(self, channelId):
        if self.channels.get(channelId) == None:
            self.channels[channelId] = await self.bot.fetch_channel(channelId)
        return self.channels[channelId]

    async def getUserTimezone(self, user):
        if self.userTimezones.get(user.id) == None:
            self.userTimezones[user.id] = await self.config.user(user).timezone()
        return self.userTimezones.get(user.id)
    
    async def createEventEmbed(self,guild, channel, event:Event) -> discord.Embed:
        embed = discord.Embed()
        timezones =[]
        for member in channel.members:
            timezone = await self.getUserTimezone(member)
            if timezone != None:
                timezones.append(timezone)

        
        otherTimezoneString = ""
        for timezone in timezones:
            otherTimezoneString += "{}: {} until {} \n".format(timezone, event.startDateTime.astimezone(tz.gettz(timezone)).strftime("**%H:%M** %Y-%m-%d"), event.endDateTime.astimezone(tz.gettz(timezone)).strftime("**%H:%M** %Y-%m-%d"))
        embed.add_field(name="When?", value=otherTimezoneString, inline=False)

        
        users = {attendee.userId: await self.bot.fetch_user(attendee.userId) for attendee in event.attendees}
        seperator = "\n"
        statusses = await self.config.guild(guild).statusReactions()
        for status in statusses:
            usersWithStatus = [users[attendee.userId].mention for attendee in event.attendees if attendee.status == status]
            message = seperator.join(usersWithStatus)
            if message == "":
                message = 	u"\u200B"
            embed.add_field(name = " {} {} ({})".format(statusses[status],status, len(usersWithStatus)) , value = message, inline = True)
            

        embed.title = event.name
        footerText = "If your timezone is not visible above, please use _[p]calendar setPersonalTimezone_ to set your timezone and when a response is added or removed your timezone will appear"
        embed.set_footer(text=footerText)
        embed.set_author(name="Cogger")
        return embed