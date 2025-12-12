import discord
from discord import app_commands
import asyncio
import aiohttp
import os
from keep_alive import keep_alive
from datetime import datetime, date
import pytz

TOKEN = os.getenv("TOKEN")
CHANNEL_ID = 1447166033746989119

# Roblox games to track
GAMES = {
    3719762683: "Public Test Realm - Bee Swarm Simulator",
    137594107439804: "Bee Swarm Simulator",
    4079902982: "Bee Swarm Test Realm ⚠️ READ DESC ⚠️",
    17573622029: "Buzz"
}

# Test Realm group
TEST_REALM_GROUP_ID = 5211428

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Store last detected updates
last_updates = {}
daily_update_count = {}
last_checked_date = date.today()
last_member_count = None

# ------------------------------
# Time conversion
# ------------------------------
def convert_time_pretty(utc_time):
    if not utc_time:
        return "Unknown"
    utc_dt = datetime.fromisoformat(utc_time.replace("Z", "+00:00"))
    central = pytz.timezone("America/Chicago")
    ct_dt = utc_dt.astimezone(central)
    return ct_dt.strftime("%B %d, %Y – %I:%M %p CT")

# ------------------------------
# Roblox API helpers
# ------------------------------
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

async def fetch_group_info(session, group_id):
    url = f"https://groups.roblox.com/v1/groups/{group_id}"
    async with session.get(url) as resp:
        data = await resp.json()
        return data

# ------------------------------
# Update checker loop
# ------------------------------
async def check_updates():
    global last_member_count, last_checked_date, daily_update_count
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)

    async with aiohttp.ClientSession() as session:
        while not client.is_closed():
            # Reset daily counters at midnight CT
            central_today = datetime.now(pytz.timezone("America/Chicago")).date()
            if central_today != last_checked_date:
                daily_update_count = {}
                last_checked_date = central_today

            # Game updates
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
                        daily_update_count[place_id] = 0
                    else:
                        if updated != last_updates[place_id]:
                            last_updates[place_id] = updated
                            daily_update_count[place_id] += 1

                            await channel.send(
                                f"**{game_name} has UPDATED!**\n"
                                f"Place ID: `{place_id}`\n"
                                f"Last Updated: `{pretty_time}`\n"
                                f"Updated {daily_update_count[place_id]} times today."
                            )
                except Exception as e:
                    print("Error:", e)

            # Test Realm group new member
            try:
                group_info = await fetch_group_info(session, TEST_REALM_GROUP_ID)
                current_member_count = group_info.get("memberCount")
                if last_member_count is None:
                    last_member_count = current_member_count
                elif current_member_count > last_member_count:
                    last_member_count = current_member_count
                    await channel.send("Onett has accepted a new member to the Test Realm group!")
            except Exception as e:
                print("Error fetching group info:", e)

            await asyncio.sleep(60)

# ------------------------------
# Slash command /checkupdates
# ------------------------------
@tree.command(name="checkupdates", description="Show last update time for all monitored Roblox games.")
async def checkupdates(interaction: discord.Interaction):
    results = []
    async with aiohttp.ClientSession() as session:
        for place_id, game_name in GAMES.items():
            try:
                universe_id = await fetch_universe_id(session, place_id)
                info = await fetch_game_info(session, universe_id)
                if info:
                    updated = info.get("updated")
                    pretty_time = convert_time_pretty(updated)
                    results.append(
                        f"**{game_name}**\nPlace ID: `{place_id}`\nLast Updated: `{pretty_time}`\n"
                    )
                else:
                    results.append(f"**{game_name}**\nPlace ID: `{place_id}`\nLast Updated: Unknown\n")
            except Exception as e:
                results.append(f"⚠️ `{place_id}`: {e}\n")

    await interaction.response.send_message("\n".join(results))

# ------------------------------
# Bot ready
# ------------------------------
@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    await tree.sync()
    asyncio.create_task(check_updates())

# ------------------------------
# Keep alive + run
# ------------------------------
keep_alive()
client.run(TOKEN)
