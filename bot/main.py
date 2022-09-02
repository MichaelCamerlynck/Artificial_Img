import discord
from discord.ext import tasks
import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import tweepy
from PIL import Image
import requests
from io import BytesIO


load_dotenv()

TOKEN = os.getenv("TOKEN")
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
client = discord.Client(intents=intents)

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
    cursor = connection.cursor()
    log = client.get_channel(1014925532346974329)

    cursor.execute(f"select url from images where id = {message_id}")
    url = cursor.fetchone()[0]

    response = requests.get(url)
    img = BytesIO(response.content)

    # auth = tweepy.OAuth1UserHandler(
    #     consumer_key, consumer_secret, access_token, access_token_secret
    # )
    #
    # api = tweepy.API(auth)
    #
    # api.update_status_with_media(
    #     status="",
    #     filename="img",
    #     file=img
    # )

    cursor.execute(f"update images set uploaded = 1 where id = {message_id}")
    connection.commit()

    await log.send(content="Image tweeted", file=discord.File(fp=img, filename="img.png"))

    print("tweeted")

@client.event
async def on_ready():
    print("BOT ONLINE")
    send_automated_tweet.start()

@client.event
async def on_message(message):
    # imagine
    if message.channel.id == imagine_channel:
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

    # favorites
    if message.channel.id == favorite_channel:
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
        if payload.channel_id == finished_channel and payload.emoji.name == "❤":
            # move image to favorites and add it to database
            message = await finished_images.fetch_message(payload.message_id)
            await message.delete()
            url = message.attachments[0]
            image = await url.to_file()
            await favorites.send(file=image)

        # favorites
        if payload.channel_id == favorite_channel:
            message = await favorites.fetch_message(payload.message_id)
            image = await message.attachments[0].to_file()
            connection = create_connection()
            cursor = connection.cursor()

            # send tweet
            if payload.emoji.name == "⬆":
                await send_tweet(message.id, connection)
                await message.add_reaction("👍")

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
        if payload.channel_id == imagine_channel:
            if payload.emoji.name == "🔻":
                message = await client.get_channel(imagine_channel).fetch_message(payload.message_id)
                await message.delete()

@tasks.loop(hours=4)
async def send_automated_tweet():
    connection = create_connection()
    cursor = connection.cursor()

    cursor.execute(f"select uploaded, id from images where id = (select id from latest)")
    uploaded, message_id = cursor.fetchone()

    if uploaded:
        cursor.execute(f"select id from images order by rand() limit 1")
        message_id = cursor.fetchone()[0]
        print("random")

    await send_tweet(message_id, connection)
    connection.close()

client.run(TOKEN)

