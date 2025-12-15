import discord
from discord import app_commands
import asyncio
import aiohttp
import os
from datetime import datetime, date
import pytz

TOKEN = os.getenv("TOKEN")
CHANNEL_ID = 1447166033746989119

GAME_IDS = {
    3719762683: "Public Test Realm – Bee Swarm Simulator",
    137594107439804: "Bee Swarm Simulator",
    4079902982: "Bee Swarm Test Realm ⚠️ READ DESC ⚠️",
    17573622029: "buzz"
}

CHECK_INTERVAL = 120  # seconds

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

central = pytz.timezone("America/Chicago")

last_update_time = {}
daily_update_count = {}
last_notification_date = {}

# ------------------------------
# TIME FORMAT
# ------------------------------
def pretty_time(utc_time):
    utc_dt = datetime.fromisoformat(utc_time.replace("Z", "+00:00"))
    ct_dt = utc_dt.astimezone(central)
    return ct_dt.strftime("%A, %B %d, %Y at %I:%M %p CT")

def today_ct():
    return datetime.now(central).date()

# ------------------------------
# ROBLOX API
# ------------------------------
async def fetch_universe_id(session, place_id):
    url = f"https://apis.roblox.com/universes/v1/places/{place_id}/universe"
    async with session.get(url) as r:
        data = await r.json()
        return data.get("universeId")

async def fetch_game_info(session, universe_id):
    url = f"https://games.roblox.com/v1/games?universeIds={universe_id}"
    async with session.get(url) as r:
        data = await r.json()
        if data.get("data"):
            return data["data"][0]
        return None

# ------------------------------
# BACKGROUND TASK
# ------------------------------
async def check_updates():
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)

    async with aiohttp.ClientSession() as session:
        while not client.is_closed():
            for place_id, display_name in GAME_IDS.items():
                try:
                    universe_id = await fetch_universe_id(session, place_id)
                    if not universe_id:
                        continue

                    info = await fetch_game_info(session, universe_id)
                    if not info:
                        continue

                    updated = info["updated"]
                    today = today_ct()

                    if place_id not in last_update_time:
                        last_update_time[place_id] = updated
                        daily_update_count[place_id] = 0
                        last_notification_date[place_id] = None
                        continue

                    if updated != last_update_time[place_id]:
                        last_update_time[place_id] = updated

                        # reset daily count if new day
                        if last_notification_date.get(place_id) != today:
                            daily_update_count[place_id] = 0
                            last_notification_date[place_id] = today

                        daily_update_count[place_id] += 1

                        # send ONLY first notification of the day
                        if daily_update_count[place_id] == 1:
                            message = (
                                f"{display_name} has updated!\n\n"
                                f"Last updated: {pretty_time(updated)}\n"
                                f"Updated {daily_update_count[place_id]} times today (since 12:00 AM CT)"
                            )
                            await channel.send(message)

                except Exception as e:
                    print("Error:", e)

            await asyncio.sleep(CHECK_INTERVAL)

# ------------------------------
# SLASH COMMAND
# ------------------------------
@tree.command(name="checkupdates", description="Show last update info for all monitored games.")
async def checkupdates(interaction: discord.Interaction):
    lines = []

    async with aiohttp.ClientSession() as session:
        for place_id, display_name in GAME_IDS.items():
            universe_id = await fetch_universe_id(session, place_id)
            if not universe_id:
                continue

            info = await fetch_game_info(session, universe_id)
            if not info:
                continue

            updated = info["updated"]
            count = daily_update_count.get(place_id, 0)

            lines.append(
                f"**{display_name}**\n"
                f"Last updated: {pretty_time(updated)}\n"
                f"Updates today: {count}\n"
            )

    await interaction.response.send_message("\n".join(lines))

# ------------------------------
# READY
# ------------------------------
@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    await tree.sync()
    asyncio.create_task(check_updates())

client.run(TOKEN)
