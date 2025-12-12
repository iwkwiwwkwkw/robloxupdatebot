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

# Game Place IDs
GAME_IDS = [
    3719762683,      # Bee Swarm Simulator
    137594107439804, # Buzz
    4079902982,      # Bee Swarm Test Realm
    17573622029      # Onett's Place (2024)
]

# Test Realm group ID
TEST_REALM_GROUP_ID = 5211428

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Store last detected update timestamps
last_updates = {}

# Store previous group members count
group_members_count = 0

# ------------------------------
# TIME CONVERSION (UTC → CT, PRETTY)
# ------------------------------
def convert_time_pretty(utc_time):
    if not utc_time:
        return "Unknown"

    utc_dt = datetime.fromisoformat(utc_time.replace("Z", "+00:00"))
    central = pytz.timezone("America/Chicago")
    ct_dt = utc_dt.astimezone(central)

    return ct_dt.strftime("%B %d, %Y – %I:%M %p CT")

# ------------------------------
# API FUNCTIONS
# ------------------------------
async def fetch_universe_id(session, place_id):
    url = f"https://apis.roblox.com/universes/v1/places/{place_id}/universe"
    async with session.get(url) as response:
        data = await response.json()
        return data.get("universeId")

async def fetch_game_info(session, universe_id):
    url = f"https://games.roblox.com/v1/games?universeIds={universe_id}"
    async with session.get(url) as response:
        data = await response.json()
        if "data" in data and len(data["data"]) > 0:
            return data["data"][0]
        return None

async def fetch_group_members(session, group_id):
    url = f"https://groups.roblox.com/v1/groups/{group_id}/users"
    async with session.get(url) as response:
        data = await response.json()
        if "data" in data:
            return data["data"]
        return []

# ------------------------------
# BACKGROUND CHECKER
# ------------------------------
async def check_updates():
    global group_members_count
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)

    async with aiohttp.ClientSession() as session:
        # Initialize group members count
        members = await fetch_group_members(session, TEST_REALM_GROUP_ID)
        group_members_count = len(members)

        while not client.is_closed():
            # ----- Game updates -----
            for place_id in GAME_IDS:
                try:
                    universe_id = await fetch_universe_id(session, place_id)
                    if not universe_id:
                        continue

                    info = await fetch_game_info(session, universe_id)
                    if not info:
                        continue

                    updated = info.get("updated")
                    pretty_time = convert_time_pretty(updated)
                    name = info.get("name")

                    if place_id not in last_updates:
                        last_updates[place_id] = updated
                    else:
                        if updated != last_updates[place_id]:
                            last_updates[place_id] = updated
                            await channel.send(f"{name} has been updated!\nLast updated: {pretty_time}")

                except Exception as e:
                    print("Error (game):", e)

            # ----- Test Realm group new member -----
            try:
                members = await fetch_group_members(session, TEST_REALM_GROUP_ID)
                if len(members) > group_members_count:
                    await channel.send("Onett has accepted a new member to the Test Realm group.")
                group_members_count = len(members)
            except Exception as e:
                print("Error (group):", e)

            await asyncio.sleep(60)  # Check every 60 seconds

# ------------------------------
# SLASH COMMAND: /checkupdates
# ------------------------------
@tree.command(name="checkupdates", description="Show last update time for all monitored Roblox games.")
async def checkupdates(interaction: discord.Interaction):
    results = []

    async with aiohttp.ClientSession() as session:
        for place_id in GAME_IDS:
            try:
                universe_id = await fetch_universe_id(session, place_id)
                info = await fetch_game_info(session, universe_id)
                if info:
                    updated = info.get("updated")
                    pretty_time = convert_time_pretty(updated)
                    name = info.get("name")
                    results.append(f"**{name}**\nLast Updated: {pretty_time}\n")
                else:
                    results.append(f"❌ `{place_id}`: Error fetching info\n")
            except Exception as e:
                results.append(f"⚠️ `{place_id}`: {e}\n")

    await interaction.response.send_message("\n".join(results))

# ------------------------------
# BOT READY
# ------------------------------
@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    await tree.sync()
    asyncio.create_task(check_updates())

# ------------------------------
# START KEEP ALIVE + BOT
# ------------------------------
keep_alive()
client.run(TOKEN)
