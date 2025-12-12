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

# Roblox game Place IDs
GAMES = {
    3719762683: "Bee Swarm Simulator",
    137594107439804: "Buzz",
    4079902982: "Bee Swarm Test Realm",
    17573622029: "Onett's Place (2024)"
}

# Roblox group IDs
GROUPS = {
    5211428: {"name": "Onett's Testing Group", "type": "member"},
    9760527: {"name": "Onett's Studio", "type": "developer"}
}

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

last_updates = {}
daily_update_counts = {game_id: 0 for game_id in GAMES}
last_day = datetime.now(pytz.timezone("America/Chicago")).day
last_group_members = {}

# Convert UTC → Central Time (CT)
def to_central(utc_str):
    if not utc_str:
        return "Unknown"
    utc = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
    central = utc.astimezone(pytz.timezone("America/Chicago"))
    return central.strftime("%A, %B %d, %Y at %I:%M %p CT")

# ---------- Roblox API ----------
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

async def fetch_group_members(session, group_id):
    url = f"https://groups.roblox.com/v1/groups/{group_id}/users"
    async with session.get(url) as resp:
        data = await resp.json()
        if "data" in data:
            return [member["user"]["username"] for member in data["data"]]
        return []

# ---------- Background Update Checker ----------
async def check_updates():
    global last_day
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)
    async with aiohttp.ClientSession() as session:
        while not client.is_closed():
            now = datetime.now(pytz.timezone("America/Chicago"))
            # Reset daily counts at midnight
            if now.day != last_day:
                last_day = now.day
                for game_id in daily_update_counts:
                    daily_update_counts[game_id] = 0

            # Check games
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

            # Check groups
            for group_id, info_dict in GROUPS.items():
                try:
                    members = await fetch_group_members(session, group_id)
                    if group_id not in last_group_members:
                        last_group_members[group_id] = members
                        continue
                    new_members = [m for m in members if m not in last_group_members[group_id]]
                    if new_members:
                        for m in new_members:
                            action_text = "accepted a new member" if info_dict["type"] == "member" else "added a new developer"
                            await channel.send(f"{info_dict['name']} has {action_text}: {m}")
                        last_group_members[group_id] = members
                except Exception as e:
                    print(f"Error fetching group {info_dict['name']}: {e}")

            await asyncio.sleep(60)

# ---------- Slash Commands ----------
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

@tree.command(name="groupmembers", description="Show current members of the monitored Roblox groups.")
async def groupmembers(interaction: discord.Interaction):
    reply = ""
    async with aiohttp.ClientSession() as session:
        for group_id, info_dict in GROUPS.items():
            members = await fetch_group_members(session, group_id)
            reply += f"{info_dict['name']} ({info_dict['type']}s):\n"
            reply += ", ".join(members) + "\n\n" if members else "No members found.\n\n"
    await interaction.response.send_message(reply)

# ---------- Bot Ready ----------
@client.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {client.user}")
    asyncio.create_task(check_updates())

# ---------- Start Keep Alive + Bot ----------
keep_alive()
client.run(TOKEN)
