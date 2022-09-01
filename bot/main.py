import discord
import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

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

@client.event
async def on_ready():
    print("BOT ONLINE")

@client.event
async def on_message(message):
    if message.channel.id == 1014839638445277197:
        if "Upscaled" in message.content:
            if message.author.id == 936929561302675456:
                finished_images = client.get_channel(1014839203164598282)
                image = await message.attachments[0].to_file()
                await finished_images.send(file=image)

    # finished-images
    if message.channel.id == 1014839203164598282:
        await message.add_reaction("❤")

    # favorites
    if message.channel.id == 1014898112780836935:
        await message.add_reaction("❌")
        await message.add_reaction("⏲")

        connection = create_connection()
        cursor = connection.cursor()
        cursor.execute(f'insert into images (id, url, uploaded) values ({message.id}, "{message.attachments[0].url}", 0)')
        connection.commit()
        connection.close()

@client.event
async def on_raw_reaction_add(payload):
    if payload.user_id in [622098365806542868, 856627512146133054]:
        finished_images = client.get_channel(1014839203164598282)
        favorites = client.get_channel(1014898112780836935)

        # finished-images -> move image to favorites and add it to database
        if payload.channel_id == 1014839203164598282 and payload.emoji.name == "❤":
            message = await finished_images.fetch_message(payload.message_id)
            await message.delete()
            url = message.attachments[0]
            image = await url.to_file()
            await favorites.send(file=image)

        # favorites
        if payload.channel_id == 1014898112780836935:
            message = await favorites.fetch_message(payload.message_id)
            image = await message.attachments[0].to_file()

            # move image to finished-images and delete from database
            if payload.emoji.name == "❌":
                await message.delete()
                await finished_images.send(file=image)

                connection = create_connection()
                cursor = connection.cursor()
                cursor.execute(f'delete from images where id = {message.id}')
                connection.commit()
                connection.close()

            # update next to be uploaded
            if payload.emoji.name == "⏲":
                log = client.get_channel(1014925532346974329)
                await log.send(content="Priority upload updated", file=image)

                connection = create_connection()
                cursor = connection.cursor()
                cursor.execute(f'update latest set id = {message.id}')
                connection.commit()
                connection.close()

client.run(TOKEN)