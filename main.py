 import discord
from discord import app_commands
import asyncio
import aiohttp
import os
from keep_alive import keep_alive
from datetime import datetime, timedelta
import pytz

TOKEN = os.getenv("TOKEN")
CHANNEL_ID = 1447166033746989119

# ------------------------------
# Games to monitor
# ------------------------------
GAMES = [
    3719762683,      # Bee Swarm Simulator
    137594107439804, # Buzz
    4079902982,      # Bee Swarm Test Realm
    17573622029      # Buzz 2024 (original name preserved)
]

# ------------------------------
# Roblox groups to monitor
# ------------------------------
GROUPS = {
    5211428: "Testing Group",        # Notifications for new members
    9760527: "Studio Developer Group" # Notifications for new developers
}

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# ------------------------------
# Store state
# ------------------------------
last_updates = {}
daily_update_count = {}
last_group_members = {}

# ------------------------------
# Utility: convert UTC → Central Time
# ------------------------------
def convert_to_central(utc_str):
    if not utc_str:
        return "Unknown"
    utc = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
    central = utc.astimezone(pytz.timezone("America/Chicago"))
    return central.strftime("%A, %B %d, %Y at %I:%M %p CT")

# ------------------------------
# Roblox API functions
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

async def fetch_group_members(session, group_id):
    url = f"https://groups.roblox.com/v1/groups/{group_id}/users?sortOrder=Asc&limit=100"
    async with session.get(url) as resp:
        data = await resp.json()
        if "data" in data:
            return [member["userId"] for member in data["data"]]
        return []

# ------------------------------
# Background checker
# ------------------------------
async def background_task():
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)

    # Daily reset tracking
    last_reset = datetime.now(pytz.timezone("America/Chicago")).date()

    async with aiohttp.ClientSession() as session:
        while not client.is_closed():
            now_ct = datetime.now(pytz.timezone("America/Chicago"))
            today = now_ct.date()

            # Reset daily counts at 12 AM CT
            if today != last_reset:
                daily_update_count.clear()
                last_reset = today

            # ---- Game Updates ----
            for place_id in GAMES:
                try:
                    universe_id = await fetch_universe_id(session, place_id)
                    if not universe_id:
                        continue
                    info = await fetch_game_info(session, universe_id)
                    if not info:
                        continue
                    updated = info.get("updated")
                    name = info.get("name")

                    if place_id not in last_updates:
                        last_updates[place_id] = updated
                        daily_update_count[place_id] = 0
                    else:
                        if updated != last_updates[place_id]:
                            last_updates[place_id] = updated
                            daily_update_count[place_id] += 1

                            msg = (
                                f"Onett has updated **{name}**\n"
                                f"Last updated: {convert_to_central(updated)}\n"
                                f"Updated {daily_update_count[place_id]} times today."
                            )
                            await channel.send(msg)
                except Exception as e:
                    print("Error fetching game:", e)

            # ---- Group Notifications ----
            for group_id, group_name in GROUPS.items():
                try:
                    members = await fetch_group_members(session, group_id)
                    last_members = last_group_members.get(group_id, set(members))
                    new_members = set(members) - last_members

                    # Store updated member list
                    last_group_members[group_id] = set(members)

                    if group_id == 5211428:  # Testing Group
                        for _ in new_members:
                            await channel.send(f"Onett has accepted a new member to **{group_name}**")
                    elif group_id == 9760527:  # Studio Developer Group
                        for _ in new_members:
                            await channel.send(f"Onett has added a new developer to **{group_name}**")

                except Exception as e:
                    print("Error fetching group members:", e)

            await asyncio.sleep(60)

# ------------------------------
# Slash command: /checkupdates
# ------------------------------
@tree.command(name="checkupdates", description="Shows last update time for all monitored Roblox games.")
async def checkupdates(interaction: discord.Interaction):
    async with aiohttp.ClientSession() as session:
        reply = ""
        for place_id in GAMES:
            try:
                universe_id = await fetch_universe_id(session, place_id)
                info = await fetch_game_info(session, universe_id)
                if info:
                    updated = info.get("updated")
                    name = info.get("name")
                    reply += f"{name}\nLast updated: {convert_to_central(updated)}\n\n"
                else:
                    reply += f"{place_id}: Unknown\n\n"
            except:
                reply += f"{place_id}: Error fetching info\n\n"
        await interaction.response.send_message(reply)

# ------------------------------
# Slash command: /checkgroups
# ------------------------------
@tree.command(name="checkgroups", description="Shows current member count for all monitored Roblox groups.")
async def checkgroups(interaction: discord.Interaction):
    async with aiohttp.ClientSession() as session:
        reply = ""
        for group_id, group_name in GROUPS.items():
            try:
                info = await fetch_group_info(session, group_id)
                member_count = info.get("memberCount", "Unknown")
                reply += f"{group_name}\nTotal Members: {member_count}\n\n"
            except:
                reply += f"{group_name}: Error fetching info\n\n"
        await interaction.response.send_message(reply)

# ------------------------------
# Bot ready
# ------------------------------
@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    await tree.sync()
    asyncio.create_task(background_task())

# ------------------------------
# Start keep-alive + bot
# ------------------------------
keep_alive()
client.run(TOKEN)
