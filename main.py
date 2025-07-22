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

# Dictionary mapping permission names to discord.Permissions attributes
PERMISSION_MAPPING = {
    "create_instant_invite": "create_instant_invite",
    "kick_members": "kick_members",
    "ban_members": "ban_members",
    "administrator": "administrator",
    "manage_channels": "manage_channels",
    "manage_guild": "manage_guild",
    "add_reactions": "add_reactions",
    "view_audit_log": "view_audit_log",
    "priority_speaker": "priority_speaker",
    "stream": "stream",
    "view_channel": "view_channel",
    "send_messages": "send_messages",
    "send_tts_messages": "send_tts_messages",
    "manage_messages": "manage_messages",
    "embed_links": "embed_links",
    "attach_files": "attach_files",
    "read_message_history": "read_message_history",
    "mention_everyone": "mention_everyone",
    "use_external_emojis": "use_external_emojis",
    "view_guild_insights": "view_guild_insights",
    "connect": "connect",
    "speak": "speak",
    "mute_members": "mute_members",
    "deafen_members": "deafen_members",
    "move_members": "move_members",
    "use_vad": "use_vad",
    "change_nickname": "change_nickname",
    "manage_nicknames": "manage_nicknames",
    "manage_roles": "manage_roles",
    "manage_webhooks": "manage_webhooks",
    "manage_emojis_and_stickers": "manage_emojis_and_stickers",
    "use_application_commands": "use_application_commands",
    "request_to_speak": "request_to_speak",
    "manage_events": "manage_events",
    "manage_threads": "manage_threads",
    "create_public_threads": "create_public_threads",
    "create_private_threads": "create_private_threads",
    "use_external_stickers": "use_external_stickers",
    "send_messages_in_threads": "send_messages_in_threads",
    "use_embedded_activities": "use_embedded_activities",
    "moderate_members": "moderate_members"
}

# ----------- TASK LOOP ----------- #
@tasks.loop(seconds=30)
async def check_sheet():
    print("🔄 Checking Google Sheet for actions...")
    records = sheet.get_all_records()

    for i, row in enumerate(records, start=2):  # start=2 to match Sheet row numbers
        action = row.get("Action", "").strip().lower()
        role_name = row.get("Role", "").strip()
        permission_list = row.get("Permissions List", "").strip().split(",")  # Comma-separated permissions
        status = row.get("Status", "").strip().lower()

        if status != "pending":
            continue

        for guild in bot.guilds:
            try:
                role = discord.utils.get(guild.roles, name=role_name)
                if not role:
                    raise Exception(f"Role '{role_name}' not found in guild '{guild.name}'")

                if action == "assign":
                    permissions = discord.Permissions()
                    for perm in permission_list:
                        perm = perm.strip().lower()
                        if perm in PERMISSION_MAPPING:
                            setattr(permissions, PERMISSION_MAPPING[perm], True)
                        else:
                            print(f"⚠️ Unknown permission '{perm}' ignored for row {i}")
                    await role.edit(permissions=permissions)
                    print(f"✅ [{guild.name}] Assigned permissions {permission_list} to role '{role_name}'.")

                elif action == "deassign":
                    permissions = discord.Permissions()
                    for perm in permission_list:
                        perm = perm.strip().lower()
                        if perm in PERMISSION_MAPPING:
                            setattr(permissions, PERMISSION_MAPPING[perm], False)
                        else:
                            print(f"⚠️ Unknown permission '{perm}' ignored for row {i}")
                    # Create a new permission set to remove specified permissions
                    current_perms = role.permissions
                    new_perms = discord.Permissions(current_perms.value & ~permissions.value)
                    await role.edit(permissions=new_perms)
                    print(f"✅ [{guild.name}] Deassigned permissions {permission_list} from role '{role_name}'.")

                sheet.update_cell(i, 4, "done")  # Update Status column (now index 4 due to fewer columns)

            except Exception as e:
                print(f"❌ [{guild.name}] Error on row {i}: {e}")
                sheet.update_cell(i, 4, "error")  # Update Status column

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