import discord
import mysql.connector
import datetime
from discord.ext import commands
import utility.config_manager as config
from utility.db_manager import db_connection as db_conn


class Admin(commands.Cog):

    def __init__(self, dictator):
        self.dictator = dictator

    @commands.command(brief='Ban a user from the game.', help='Ban a user from the game. Any words after declaring the user will be the ban reason, if a reason is not specified it will default to "The ban hammer has spoken." The user, moderator and log channel will be notified. The user argument can be a Discord user tag, a Discord username with discriminator or a Discord user ID.', usage='<user> [reason]')
    @commands.has_role('Admin')
    async def ban(self, ctx, user, *, reason='The ban hammer has spoken.'):
        await ctx.message.delete()
        log_channel = await commands.TextChannelConverter().convert(ctx, config.read('log_channel_id'))
        
        # Ensure we're banning a valid user
        try:
            user = await commands.UserConverter().convert(ctx, user)

        except commands.CommandError as e:
            print(f'{ctx.author} tried to ban {user} but they\'re not a valid user.\n{e}')
            await ctx.author.send('You can only ban valid users.')
            return

        # Check if user is already banned
        with db_conn() as db:
            db.execute(f'SELECT banned FROM `users` WHERE discord_id = \'{user.id}\'')
            row = db.fetchone()

        if row[0] == 1:
            print(f'{ctx.author} tried to ban {user} but they\'re already banned.')
            await ctx.author.send(f'{user.mention} is already banned.')
            return

        # Ban the user
        with db_conn() as db:
            db.execute(f'UPDATE users SET banned = 1 WHERE discord_id = \'{user.id}\'')

        print(f'{ctx.author} banned {user} for: {reason}')
        await ctx.author.send(f'You have **banned** {user.mention} for: {reason}')
        await user.send(f'Your account to play 2HOL has been **banned** for: {reason}\nIf you believe this has been done in error, contact an Admin.')

        # Embed log
        embed = discord.Embed(title='User has been banned from the game', colour=discord.Colour.red())
        embed.add_field(name='User:', value=f'{user.mention}', inline=True)
        embed.add_field(name='Reason:', value=f'{reason}', inline=True)
        embed.add_field(name='Moderator:', value=f'{ctx.author.mention}', inline=True)
        await log_channel.send(embed=embed)

    @commands.command(brief='Unban a user from the game.', help='Unban a user from the game. Any words after declaring the user will be the unban reason, if a reason is not specified it will default to "It\'s your lucky day!" The user, moderator and log channel will be notified. The user argument can be a Discord user tag, a Discord username with discriminator or a Discord user ID.', usage='<user> [reason]')
    @commands.has_role('Admin')
    async def unban(self, ctx, user, *, reason='It\'s your lucky day!'):
        await ctx.message.delete()
        log_channel = await commands.TextChannelConverter().convert(ctx, config.read('log_channel_id'))
        
        # Ensure we're unbanning a valid user
        try:
            user = await commands.UserConverter().convert(ctx, user)

        except commands.CommandError as e:
            print(f'{ctx.author} tried to unban {user} but they\'re not a valid user.\n{e}')
            await ctx.author.send('You can only unban valid users.')
            return

        # Check that user is banned
        with db_conn() as db:
            db.execute(f'SELECT banned FROM `users` WHERE discord_id = \'{user.id}\'')
            row = db.fetchone()

        if row[0] == 0:
            print(f'{ctx.author} tried to unban {user} but they\'re not already banned.')
            await ctx.author.send(f'{user.mention} is not already banned.')
            return

        # Unban the user
        with db_conn() as db:
            db.execute(f'UPDATE users SET banned = 0 WHERE discord_id = \'{user.id}\'')

        print(f'{ctx.author} unbanned {user} for: {reason}')
        await ctx.author.send(f'You have **unbanned** {user.mention} for: {reason}')
        await user.send(f'Your account to play 2HOL has been **unbanned** for: {reason}')

        # Embed log
        embed = discord.Embed(title='User has been unbanned from the game', colour=discord.Colour.green())
        embed.add_field(name='User:', value=f'{user.mention}', inline=True)
        embed.add_field(name='Reason:', value=f'{reason}', inline=True)
        embed.add_field(name='Moderator:', value=f'{ctx.author.mention}', inline=True)
        await log_channel.send(embed=embed)

    @commands.command(aliases=['hois'], brief='Lookup who a player was in the game.', help='Lookup who a player was in the game. The player must have died. Only the last five results will be displayed. You will also be told how long ago each player died.')
    @commands.has_role('Admin')
    async def whois(self, ctx, *, character):
        
        # How many results to lookup.
        # Due to embed length limitations, the maxium is 8.
        history = 5

        with db_conn() as db:
            db.execute(f'SELECT discord_id, death_time, email FROM server_lives INNER JOIN users ON server_lives.user_id = users.id WHERE name = \'{character}\' ORDER BY death_time DESC LIMIT {history}')
            users = db.fetchall()

        if not users:
            embed = discord.Embed(title=f'No results for the character \'{character}\'.', colour=0xffbb35)
            await ctx.send(embed=embed)
            return

        current_time = datetime.datetime.now(tz=datetime.timezone.utc)
        current_time = current_time.replace(microsecond=0)
        embed = discord.Embed(title=f'Latest {history} results for the character \'{character}\':', colour=0xffbb35)

        for u in users:
            try:
                found_user = await self.dictator.fetch_user(u[0])

            except:
                raise commands.CommandError
            
            else:
                # Format death time as timezone aware
                death_time = datetime.datetime(year=u[1].year, month=u[1].month, day=u[1].day, hour=u[1].hour, minute=u[1].minute, second=u[1].second, tzinfo=datetime.timezone.utc)
                diff = current_time - death_time
                diff_split = str(diff).split(':')
                # diff_split[0] appears as '3 days, 4' where 3 = amount of days and 4 = amount of hours. I aplogise if you have to debug this.
                diff_formatted = f'{diff_split[0]} hours, {diff_split[1]} minutes ago'
                embed.add_field(name='Discord user:', value=f'{found_user}', inline=True)
                embed.add_field(name='Died:', value=f'{diff_formatted}', inline=True)
                embed.add_field(name='\u200b', value='\u200b')

        if len(users) < history:
            embed.add_field(name='\u200b', value='End of results')

        await ctx.send(embed=embed)

    @commands.command(brief='See info about a user.', help='Sends you a message containing relevant information about a user.', usage='<user>')
    @commands.has_role('Mod')
    async def info(self, ctx, user: discord.User):
        await ctx.message.delete()

        with db_conn() as db:
            db.execute(f'SELECT email, banned FROM users WHERE discord_id = \'{user.id}\'')
            user_info = db.fetchone()

        if not user_info:
            embed = discord.Embed(title=f'No results for the user \'{user.mention}\'.', colour=0xffbb35)
            await ctx.author.send(embed=embed)
            return

        embed = discord.Embed(title=f'Results for the user \'{user.name}#{user.discriminator}\':', colour=0xffbb35)
        embed.add_field(name='Username:', value=f'{user_info[0]}')
        embed.add_field(name='Banned:', value='Yes' if user_info[1] else 'No')
        await ctx.author.send(embed=embed)
        print(f'Supplied info of {user.name}#{user.discriminator} to {ctx.author.name}#{ctx.author.discriminator}')


def setup(dictator):
    dictator.add_cog(Admin(dictator))
