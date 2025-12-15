import discord
from discord import app_commands
import asyncio
import aiohttp
import os
from keep_alive import keep_alive
from datetime import datetime
import pytz

# ------------------------------
# CONFIG
# ------------------------------
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = 1447166033746989119

GAME_IDS = [
    3719762683,      # Public Test Realm Bee Swarm
    137594107439804, # Bee Swarm Simulator
    4079902982,      # Bee Swarm Test Realm
    17573622029      # buzz
]

CHECK_INTERVAL = 120  # seconds

# ------------------------------
# DISCORD SETUP
# ------------------------------
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# ------------------------------
# STATE
# ------------------------------
last_updates = {}
daily_update_counts = {}
last_reset_date = None

# ------------------------------
# TIME HELPERS
# ------------------------------
def convert_time_pretty(utc_time):
    if not utc_time:
        return "Unknown"

    utc_dt = datetime.fromisoformat(utc_time.replace("Z", "+00:00"))
    central = pytz.timezone("America/Chicago")
    ct_dt = utc_dt.astimezone(central)

    return ct_dt.strftime("%B %d, %Y – %I:%M %p CT")

def get_ct_date():
    central = pytz.timezone("America/Chicago")
    return datetime.now(central).date()

# ------------------------------
# ROBLOX API
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

# ------------------------------
# BACKGROUND UPDATE CHECKER
# ------------------------------
async def check_updates():
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)

    global last_reset_date

    async with aiohttp.ClientSession() as session:
        while not client.is_closed():

            # Reset daily counts at 12:00 AM CT
            today = get_ct_date()
            if last_reset_date != today:
                daily_update_counts.clear()
                last_reset_date = today

            for place_id in GAME_IDS:
                try:
                    universe_id = await fetch_universe_id(session, place_id)
                    if not universe_id:
                        continue

                    info = await fetch_game_info(session, universe_id)
                    if not info:
                        continue

                    updated = info.get("updated")
                    name = info.get("name")
                    pretty_time = convert_time_pretty(updated)

                    if place_id not in last_updates:
                        last_updates[place_id] = updated
                    else:
                        if updated != last_updates[place_id]:
                            last_updates[place_id] = updated
                            daily_update_counts[place_id] = daily_update_counts.get(place_id, 0) + 1

                            await channel.send(
                                f"**{name} has updated!**\n"
                                f"Place ID: `{place_id}`\n"
                                f"Last Updated: `{pretty_time}`\n"
                                f"Updated Today: `{daily_update_counts[place_id]}`"
                            )

                except Exception as e:
                    print("Error:", e)

            await asyncio.sleep(CHECK_INTERVAL)

# ------------------------------
# SLASH COMMAND
# ------------------------------
@tree.command(
    name="checkupdates",
    description="Show last update time and how many times each game updated today."
)
async def checkupdates(interaction: discord.Interaction):

    results = []

    async with aiohttp.ClientSession() as session:
        for place_id in GAME_IDS:
            universe_id = await fetch_universe_id(session, place_id)
            info = await fetch_game_info(session, universe_id) if universe_id else None

            if not info:
                results.append(f"`{place_id}`: Unable to fetch data\n")
                continue

            name = info.get("name")
            updated = info.get("updated")
            pretty_time = convert_time_pretty(updated)
            count = daily_update_counts.get(place_id, 0)
            times_text = "time" if count == 1 else "times"

            results.append(
                f"**{name}**\n"
                f"Place ID: `{place_id}`\n"
                f"Last Updated: `{pretty_time}`\n"
                f"Updated Today: `{count} {times_text}`\n"
            )

    await interaction.response.send_message("\n".join(results))

# ------------------------------
# READY
# ------------------------------
@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    await tree.sync()
    asyncio.create_task(check_updates())

# ------------------------------
# START
# ------------------------------
keep_alive()
client.run(TOKEN)
