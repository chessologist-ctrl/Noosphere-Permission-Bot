import discord
from discord.ext import tasks, commands
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
import os
import json

# ----------- LOAD .env ----------- #
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# ----------- CONFIG ----------- #
SHEET_NAME = "Permission Bot"  # Google Sheet name

# ----------- DISCORD SETUP ----------- #
intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
intents.message_content = True
intents.messages = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ----------- GOOGLE SHEETS SETUP ----------- #
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Load credentials from environment variable
creds_dict = json.loads(os.getenv("CREDS_JSON"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1  # Main instruction tab

# ----------- TASK LOOP ----------- #
@tasks.loop(seconds=30)
async def check_sheet():
    print("🔄 Checking Google Sheet for actions...")
    records = sheet.get_all_records()

    for i, row in enumerate(records, start=2):  # start=2 to match Sheet row numbers
        action = row.get("Action", "").strip().lower()
        category_name = row.get("Category", "").strip()
        channel_name = row.get("Channel Name", "").strip()
        channel_type = row.get("Type", "").strip().lower()
        role_name = row.get("Role", "").strip()
        permission = row.get("Permission", "").strip().lower()
        status = row.get("Status", "").strip().lower()

        if status != "pending":
            continue

        for guild in bot.guilds:
            try:
                category = discord.utils.get(guild.categories, name=category_name)
                role = discord.utils.get(guild.roles, name=role_name) if role_name else None

                if action == "create":
                    if not category:
                        category = await guild.create_category(category_name)

                    channel = None
                    if channel_type == "text":
                        channel = await guild.create_text_channel(channel_name, category=category)
                    elif channel_type == "voice":
                        channel = await guild.create_voice_channel(channel_name, category=category)
                    else:
                        raise Exception(f"Unknown channel type: '{channel_type}'")

                    print(f"✅ [{guild.name}] Created {channel_type} channel '{channel_name}' in '{category_name}'.")

                    # Apply permissions if specified
                    if role and permission:
                        permissions = {}
                        if permission == "allow":
                            permissions = {
                                role: discord.PermissionOverwrite(
                                    read_messages=True,
                                    send_messages=True,
                                    connect=True,
                                    speak=True
                                )
                            }
                        elif permission == "deny":
                            permissions = {
                                role: discord.PermissionOverwrite(
                                    read_messages=False,
                                    send_messages=False,
                                    connect=False,
                                    speak=False
                                )
                            }
                        else:
                            raise Exception(f"Unknown permission: '{permission}'")

                        await channel.edit(overwrites=permissions)
                        print(f"✅ [{guild.name}] Set {permission} permissions for role '{role_name}' on channel '{channel_name}'.")

                elif action == "delete":
                    if channel_name:
                        target_channel = discord.utils.get(guild.channels, name=channel_name)
                        if target_channel:
                            await target_channel.delete()
                            print(f"🗑 [{guild.name}] Deleted channel '{channel_name}'.")
                    else:
                        if category:
                            for channel in category.channels:
                                await channel.delete()
                                print(f"🗑 [{guild.name}] Deleted channel '{channel.name}' from category '{category.name}'.")
                            await category.delete()
                            print(f"🗑 [{guild.name}] Deleted category '{category_name}' and all its channels.")

                elif action == "assign":
                    if not role:
                        raise Exception(f"No role specified for assign action on row {i}")
                    target_channel = discord.utils.get(guild.channels, name=channel_name)
                    if target_channel:
                        permissions = {
                            role: discord.PermissionOverwrite(
                                read_messages=True,
                                send_messages=True,
                                connect=True,
                                speak=True
                            )
                        }
                        await target_channel.edit(overwrites=permissions)
                        print(f"✅ [{guild.name}] Assigned permissions for role '{role_name}' on channel '{channel_name}'.")

                elif action == "deassign":
                    if not role:
                        raise Exception(f"No role specified for deassign action on row {i}")
                    target_channel = discord.utils.get(guild.channels, name=channel_name)
                    if target_channel:
                        permissions = {
                            role: discord.PermissionOverwrite(
                                read_messages=False,
                                send_messages=False,
                                connect=False,
                                speak=False
                            )
                        }
                        await target_channel.edit(overwrites=permissions)
                        print(f"✅ [{guild.name}] Deassigned permissions for role '{role_name}' on channel '{channel_name}'.")

                sheet.update_cell(i, 8, "done")

            except Exception as e:
                print(f"❌ [{guild.name}] Error on row {i}: {e}")
                sheet.update_cell(i, 8, "error")

# ----------- BOT EVENTS ----------- #
@bot.event
async def on_ready():
    print(f"✅ {bot.user.name} is live and monitoring servers:")
    for g in bot.guilds:
        print(f" - {g.name} ({g.id})")
    check_sheet.start()

# ----------- RUN BOT ----------- #
from keep_alive import keep_alive
keep_alive()

bot.run(DISCORD_TOKEN)