import discord
from discord import app_commands
import asyncio
import aiohttp
import os
from keep_alive import keep_alive
from datetime import datetime
import pytz

TOKEN = os.getenv("TOKEN")
CHANNEL_ID = 1447166033746989119

# Roblox Game Place IDs
GAMES = {
    3719762683: "Bee Swarm Simulator",
    137594107439804: "Buzz",
    4079902982: "Bee Swarm Test Realm",
    17573622029: "Onett's Place (2024)"
}

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

last_updates = {}
daily_update_counts = {game_id: 0 for game_id in GAMES}
last_day = datetime.now(pytz.timezone("America/Chicago")).day

def to_central(utc_str):
    if not utc_str:
        return "Unknown"
    utc = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
    central = utc.astimezone(pytz.timezone("America/Chicago"))
    return central.strftime("%A, %B %d, %Y at %I:%M %p CT")

async def fetch_universe_id(session, place_id):
    url = f"https://apis.roblox.com/universes/v1/places/{place_id}/universe"
    async with session.get(url) as resp:
        data = await resp.json()
        return data.get("universeId")

async def fetch_game_info(session, universe_id):
    url = f"https://games.roblox.com/v1/games?universeIds={universe_id}"
    async with session.get(url) as resp:
        data = await resp.json()
        if "data" in data and len(data["data"]) > 0:
            return data["data"][0]
        return None

async def check_updates():
    global last_day
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)
    async with aiohttp.ClientSession() as session:
        while not client.is_closed():
            now = datetime.now(pytz.timezone("America/Chicago"))
            if now.day != last_day:
                last_day = now.day
                for game_id in daily_update_counts:
                    daily_update_counts[game_id] = 0

            # Check game updates
            for place_id, game_name in GAMES.items():
                try:
                    universe_id = await fetch_universe_id(session, place_id)
                    if not universe_id:
                        continue
                    info = await fetch_game_info(session, universe_id)
                    if not info:
                        continue
                    updated = info.get("updated")
                    if place_id not in last_updates:
                        last_updates[place_id] = updated
                    else:
                        if updated != last_updates[place_id]:
                            last_updates[place_id] = updated
                            daily_update_counts[place_id] += 1
                            await channel.send(
                                f"{game_name} has been updated!\n"
                                f"Last updated: {to_central(updated)}\n"
                                f"Updated {daily_update_counts[place_id]} times today."
                            )
                except Exception as e:
                    print(f"Error fetching game {game_name}: {e}")

# Slash command for checking game updates
@tree.command(name="checkupdates", description="Show last update time for all monitored Roblox games.")
async def checkupdates(interaction: discord.Interaction):
    reply = ""
    async with aiohttp.ClientSession() as session:
        for place_id, game_name in GAMES.items():
            universe_id = await fetch_universe_id(session, place_id)
            info = await fetch_game_info(session, universe_id)
            if info:
                reply += f"{game_name}\nLast updated: {to_central(info.get('updated'))}\n\n"
            else:
                reply += f"{game_name}\nLast updated: Unknown\n\n"
    await interaction.response.send_message(reply)

@client.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {client.user}")
    asyncio.create_task(check_updates())

keep_alive()
client.run(TOKEN)
