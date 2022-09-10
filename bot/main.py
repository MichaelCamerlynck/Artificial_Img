import asyncio
import datetime
import dateutil.tz
import discord
from discord.ext import tasks, commands
from discord import app_commands
import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import tweepy
import requests
from io import BytesIO
#import pytz

load_dotenv()

TOKEN = os.getenv("TOKEN")
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
client = discord.Client(intents=intents)

tree = app_commands.CommandTree(client)

host = os.getenv("HOST_NAME")
username = os.getenv("USER_NAME")
password = os.getenv("PASSWD")
db = os.getenv("DB_NAME")

consumer_key = os.getenv("CK")
consumer_secret = os.getenv("CS")
access_token = os.getenv("AT")
access_token_secret = os.getenv("ATS")

imagine_channel = 1014839638445277197
favorite_channel = 1014898112780836935
finished_channel = 1014839203164598282
prompt_channels = []

# temporary solution
tweet_time = ["08:45:00"]
timer = []
timezone = dateutil.tz.gettz("Asia/Singapore")
for time in tweet_time:
    hour, minute, second = [int(x) for x in time.split(":")]
    timer.append(datetime.time(hour=hour,minute=minute,second=second,tzinfo=timezone))


def create_connection():
    connection = None
    try:
        connection = mysql.connector.connect(
            host=host,
            user=username,
            passwd=password,
            database=db
        )
        print("Connection to MySQL DB successful")
    except Error as e:
        print(f"The error '{e}' occurred")

    return connection

async def send_tweet(message_id, connection):
    print("Tweeting Image")
    cursor = connection.cursor()
    log = client.get_channel(1014925532346974329)
    favorites = client.get_channel(favorite_channel)
    message = await favorites.fetch_message(message_id)
    text = message.content + " #midjourney #AIart"

    cursor.execute(f"select url from images where id = {message_id}")
    url = cursor.fetchone()[0]

    response = requests.get(url)
    print(url)
    img = BytesIO(response.content)

    auth = tweepy.OAuth1UserHandler(
        consumer_key, consumer_secret, access_token, access_token_secret
    )

    api = tweepy.API(auth)

    media = api.media_upload(
        filename="img.png",
        file=img
    )

    api.update_status(
        status=text,
        media_ids=[media.media_id]
    )

    cursor.execute(f"update images set uploaded = 1 where id = {message_id}")
    connection.commit()

    await message.add_reaction("👍")
    await log.send(content="Image tweeted", file=discord.File(fp=BytesIO(response.content), filename="img.png"))
    print("tweeted")

def update_prompt_channels():
    guild = client.get_guild(835215905180483594)
    category = discord.utils.get(guild.categories, id=1017594346582851634)
    channels = category.channels
    for channel in channels:
        prompt_channels.append(channel.id)

@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=835215905180483594))
    update_prompt_channels()
    send_automated_tweet.start()
    print("BOT ONLINE")

@tree.command(name="create", description="creates new channel", guild=discord.Object(id=835215905180483594))
async def self(interaction: discord.Interaction, name: str):
    guild = interaction.guild
    category = discord.utils.find(lambda c: c.id == 1017594346582851634, guild.channels)
    channel = await guild.create_text_channel(name, category=category)
    prompt_channels.append(channel.id)

    await interaction.response.send_message(f"Created channel **{name}**!")

@tree.command(name="delete", description="deletes channel", guild=discord.Object(id=835215905180483594))
async def self(interaction: discord.Interaction):
    if interaction.channel_id in prompt_channels:
        await interaction.channel.delete()

@tree.command(name="archive", description="moves channel to archived category", guild=discord.Object(id=835215905180483594))
async def self(interaction: discord.Interaction):
    if interaction.channel_id in prompt_channels:
        archived = discord.utils.get(interaction.guild.categories, id=1017748834610327616)
        await interaction.channel.move(category=archived, beginning=True)
        await client.get_channel(1014925532346974329).send(f"**{interaction.channel.name}** archived!")
        await interaction.response.send_message("Channel Archived")

@tree.command(name="clear", description="clear the channel", guild=discord.Object(id=835215905180483594))
async def self(interaction: discord.Interaction):
    if interaction.channel_id in prompt_channels or interaction.channel_id == 1014839638445277197:
        await interaction.channel.purge()

@tree.command(name="timezone", description="changes timezone", guild=discord.Object(id=835215905180483594))
async def self(interaction: discord.Interaction, timezone: str):
    connection = create_connection()
    cursor = connection.cursor()

    cursor.execute(f"update latest set timezone = '{timezone}'")
    connection.commit()

    await interaction.response.send_message("Timezone updated")

@tree.command(name="timer", description="sets time to tweet", guild=discord.Object(id=835215905180483594))
async def self(interaction: discord.Interaction):
    await interaction.response.send_message(f"Next run: {send_automated_tweet.next_iteration}", ephemeral=True)

@client.event
async def on_message(message):
    # prompt channels
    if message.channel.id in prompt_channels:
        if message.author.id == 936929561302675456:
            if "Upscaled" in message.content:
                finished_images = client.get_channel(finished_channel)
                image = await message.attachments[0].to_file()
                await finished_images.send(file=image)

            if "%" not in message.content:
                await message.add_reaction("🔻")

    # finished-images
    if message.channel.id == finished_channel:
        await message.add_reaction("❤")
        await message.add_reaction("❌")

    # favorites
    if message.channel.id == favorite_channel:
        # rename an image
        if message.reference:
            text = message.content
            ori_msg = await client.get_channel(favorite_channel).fetch_message(message.reference.message_id)
            await ori_msg.edit(content=text)
            await message.delete()
        else:
            await message.add_reaction("❌")
            await message.add_reaction("⏲")
            await message.add_reaction("⬆")

            connection = create_connection()
            cursor = connection.cursor()
            cursor.execute(f'insert into images (id, url, uploaded) values ({message.id}, "{message.attachments[0].url}", 0)')
            connection.commit()
            connection.close()

@client.event
async def on_raw_reaction_add(payload):
    if payload.user_id in [622098365806542868, 856627512146133054]:
        finished_images = client.get_channel(finished_channel)
        favorites = client.get_channel(favorite_channel)
        log = client.get_channel(1014925532346974329)

        # finished-images
        if payload.channel_id == finished_channel:
            message = await finished_images.fetch_message(payload.message_id)

            # move image to favorites and add it to database
            if payload.emoji.name == "❤":
                await message.delete()
                url = message.attachments[0]
                image = await url.to_file()
                await favorites.send(file=image)

            # delete image
            if payload.emoji.name == "❌":
                await message.delete()

        # favorites
        if payload.channel_id == favorite_channel:
            message = await favorites.fetch_message(payload.message_id)
            image = await message.attachments[0].to_file()
            connection = create_connection()
            cursor = connection.cursor()

            # send tweet
            if payload.emoji.name == "⬆":
                await send_tweet(message.id, connection)

            # move image to finished-images and delete from database
            if payload.emoji.name == "❌":
                await message.delete()
                await finished_images.send(file=image)

                cursor.execute(f'delete from images where id = {message.id}')
                connection.commit()
                connection.close()

            # update next to be uploaded
            if payload.emoji.name == "⏲":
                await log.send(content="Priority upload updated", file=image)

                cursor.execute(f'update latest set id = {message.id}')
                connection.commit()
                connection.close()

        # imagine
        if payload.channel_id in prompt_channels:
            if payload.emoji.name == "🔻":
                message = await client.get_channel(payload.channel_id).fetch_message(payload.message_id)
                await message.delete()

@tasks.loop(time=timer)
async def send_automated_tweet():
    print("sending automated tweet")
    connection = create_connection()
    cursor = connection.cursor()

    cursor.execute(f"select uploaded, id from images where id = (select id from latest)")
    uploaded, message_id = cursor.fetchone()
    print(uploaded, message_id, "ids")

    if uploaded:
        print("latest, uploaded getting random")
        cursor.execute(f"select id from images where uploaded = 0 order by rand() limit 1")
        message_id = cursor.fetchone()[0]
        print(message_id, "new image to upload")

    await send_tweet(message_id, connection)
    connection.close()

client.run(TOKEN)
