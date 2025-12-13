import discord
from discord import app_commands
import asyncio
import aiohttp
import os
from keep_alive import keep_alive
from datetime import datetime, timedelta
import pytz

# ------------------------------
# CONFIG
# ------------------------------
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = 1447166033746989119

GAMES = {
    3719762683: "[Public Test Realm] Bee Swarm Simulator",
    137594107439804: "Bee Swarm Simulator",
    4079902982: "Bee Swarm Test Realm ⚠️ READ DESC ⚠️",
    17573622029: "buzz"
}

CHECK_INTERVAL = 60  # seconds

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Store last update times
last_updates = {}
daily_update_counts = {place_id: 0 for place_id in GAMES}

# Store current day for reset
central = pytz.timezone("America/Chicago")
current_day = datetime.now(central).date()

# ------------------------------
# TIME CONVERSION (UTC → Central, Pretty)
# ------------------------------
def convert_time_pretty(utc_time):
    if not utc_time:
        return "Unknown"
    utc_dt = datetime.fromisoformat(utc_time.replace("Z", "+00:00"))
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

# ------------------------------
# BACKGROUND CHECKER
# ------------------------------
async def check_updates():
    global current_day, daily_update_counts

    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)

    async with aiohttp.ClientSession() as session:
        while not client.is_closed():
            # Check if day has changed (reset counters)
            now = datetime.now(central).date()
            if now != current_day:
                current_day = now
                daily_update_counts = {place_id: 0 for place_id in GAMES}

            for place_id, game_name in GAMES.items():
                try:
                    universe_id = await fetch_universe_id(session, place_id)
                    if not universe_id:
                        continue

                    info = await fetch_game_info(session, universe_id)
                    if not info:
                        continue

                    updated = info.get("updated")
                    pretty_time = convert_time_pretty(updated)

                    if place_id not in last_updates:
                        last_updates[place_id] = updated
                    else:
                        if updated != last_updates[place_id]:
                            last_updates[place_id] = updated
                            daily_update_counts[place_id] += 1

                            embed = discord.Embed(
                                title=f"{game_name} has UPDATED!",
                                description=(
                                    f"Place ID: `{place_id}`\n"
                                    f"Last Updated: `{pretty_time}`\n"
                                    f"Updated today: {daily_update_counts[place_id]} time(s)"
                                )
                            )
                            await channel.send(embed=embed)

                except Exception as e:
                    print("Error:", e)

            await asyncio.sleep(CHECK_INTERVAL)

# ------------------------------
# SLASH COMMAND: /checkupdates
# ------------------------------
@tree.command(name="checkupdates", description="Show last update time for all monitored Roblox games.")
async def checkupdates(interaction: discord.Interaction):
    results = []

    async with aiohttp.ClientSession() as session:
        for place_id, game_name in GAMES.items():
            try:
                universe_id = await fetch_universe_id(session, place_id)
                if not universe_id:
                    results.append(f"❌ `{place_id}`: Universe not found\n")
                    continue

                info = await fetch_game_info(session, universe_id)
                if not info:
                    results.append(f"❌ `{place_id}`: Error fetching info\n")
                    continue

                updated = info.get("updated")
                pretty_time = convert_time_pretty(updated)

                results.append(
                    f"**{game_name}**\n"
                    f"Place ID: `{place_id}`\n"
                    f"Last Updated: `{pretty_time}`\n"
                )

            except Exception as e:
                results.append(f"⚠️ `{place_id}`: {e}\n")

    await interaction.response.send_message("\n".join(results))

# ------------------------------
# SLASH COMMAND: /dailysummary
# ------------------------------
@tree.command(name="dailysummary", description="Show how many times each game updated today.")
async def dailysummary(interaction: discord.Interaction):
    summary = []
    for place_id, game_name in GAMES.items():
        count = daily_update_counts.get(place_id, 0)
        summary.append(f"**{game_name}** → Updated today: {count} time(s)")

    await interaction.response.send_message("\n".join(summary))

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
