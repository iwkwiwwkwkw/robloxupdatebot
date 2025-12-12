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

# Roblox Place IDs
GAME_IDS = [
    3719762683,      # Public Test Realm
    137594107439804, # Bee Swarm Simulator
    4079902982,      # Bee Swarm Test Realm
    17573622029      # buzz
]

# Roblox group IDs (Onett's Test Realm group)
GROUP_IDS = {
    5211428: "Test Realm Group"
}

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

last_updates = {}
group_last_counts = {}

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
# ROBLOX API FUNCTIONS
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

async def fetch_group_member_count(session, group_id):
    url = f"https://groups.roblox.com/v1/groups/{group_id}"
    async with session.get(url) as response:
        data = await response.json()
        return data.get("memberCount")

# ------------------------------
# BACKGROUND CHECKER
# ------------------------------
async def check_updates():
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)

    async with aiohttp.ClientSession() as session:
        while not client.is_closed():
            # Check game updates
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
                            embed = discord.Embed(
                                title=f"**{name} UPDATED!**",
                                description=f"Place ID: `{place_id}`\nLast Updated: `{pretty_time}`",
                                color=0xFFFFFF
                            )
                            await channel.send(embed=embed)
                except Exception as e:
                    print(f"Game update error: {e}")

            # Check group new members
            for group_id, group_name in GROUP_IDS.items():
                try:
                    count = await fetch_group_member_count(session, group_id)
                    if group_id not in group_last_counts:
                        group_last_counts[group_id] = count
                    else:
                        if count > group_last_counts[group_id]:
                            group_last_counts[group_id] = count
                            await channel.send(f"**Onett has accepted a new member to the {group_name}**")
                except Exception as e:
                    print(f"Group update error: {e}")

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
                if not info or not universe_id:
                    results.append(f"❌ `{place_id}`: Error fetching info\n")
                    continue

                name = info.get("name")
                updated = info.get("updated")
                pretty_time = convert_time_pretty(updated)
                results.append(
                    f"**{name}**\nPlace ID: `{place_id}`\nLast Updated: `{pretty_time}`\n"
                )
            except Exception as e:
                results.append(f"⚠️ `{place_id}`: {e}\n")
    await interaction.response.send_message("\n".join(results))

# ------------------------------
# BOT READY
# ------------------------------
@client.event
async def on_ready():
    await tree.sync()
    asyncio.create_task(check_updates())
    print(f"Logged in as {client.user}")

# ------------------------------
# START KEEP ALIVE + BOT
# ------------------------------
keep_alive()
client.run(TOKEN)
