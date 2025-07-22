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
if not DISCORD_TOKEN:
    print("❌ DISCORD_TOKEN not found in environment variables!")
    exit(1)

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
if not creds_dict:
    print("❌ CREDS_JSON not found or invalid in environment variables!")
    exit(1)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
try:
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1  # Main instruction tab
    print(f"✅ Connected to Google Sheet: {SHEET_NAME}")
except Exception as e:
    print(f"❌ Failed to connect to Google Sheet: {str(e)}")
    exit(1)

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
    headers = sheet.row_values(1)  # Get sheet headers to verify structure
    print(f"Sheet headers: {headers}")

    status_index = headers.index("Status") + 1 if "Status" in headers else 4  # Dynamic status column index
    print(f"Using Status column index: {status_index}")

    for i, row in enumerate(records, start=2):  # start=2 to match Sheet row numbers
        action = row.get("Action", "").strip().lower()
        role_name = row.get("Role", "").strip()
        permission_list = row.get("Permissions List", "").strip().split(",")  # Comma-separated permissions
        status = row.get("Status", "").strip().lower()

        if status != "pending":
            continue

        for guild in bot.guilds:
            try:
                print(f"Processing row {i} in guild {guild.name}: Action={action}, Role={role_name}, Permissions={permission_list}")
                role = discord.utils.get(guild.roles, name=role_name)
                if not role:
                    raise Exception(f"Role '{role_name}' not found in guild '{guild.name}'")

                current_perms = role.permissions

                if action == "assign":
                    permissions = discord.Permissions()
                    for perm in permission_list:
                        perm = perm.strip().lower()
                        if perm in PERMISSION_MAPPING:
                            if not getattr(current_perms, PERMISSION_MAPPING[perm]):  # Skip if already assigned
                                setattr(permissions, PERMISSION_MAPPING[perm], True)
                                print(f"🔧 Assigning {perm} to role '{role_name}'")
                            else:
                                print(f"⏭️ Skipping {perm} for role '{role_name}' as it’s already assigned")
                        else:
                            print(f"⚠️ Unknown permission '{perm}' ignored for row {i}")
                    if permissions.value != 0:  # Only edit if there are changes
                        await role.edit(permissions=discord.Permissions(current_perms.value | permissions.value))
                        print(f"✅ [{guild.name}] Assigned new permissions {permission_list} to role '{role_name}'.")
                    else:
                        print(f"ℹ️ No new permissions to assign for role '{role_name}'.")

                elif action == "deassign":
                    permissions = discord.Permissions()
                    for perm in permission_list:
                        perm = perm.strip().lower()
                        if perm in PERMISSION_MAPPING:
                            setattr(permissions, PERMISSION_MAPPING[perm], False)
                        else:
                            print(f"⚠️ Unknown permission '{perm}' ignored for row {i}")
                    new_perms = discord.Permissions(current_perms.value & ~permissions.value)
                    await role.edit(permissions=new_perms)
                    print(f"✅ [{guild.name}] Deassigned permissions {permission_list} from role '{role_name}'.")

                sheet.update_cell(i, status_index, "done")

            except Exception as e:
                print(f"❌ [{guild.name}] Error on row {i}: {str(e)}")  # Ensure exception details are logged
                sheet.update_cell(i, status_index, "error")

# ----------- BOT EVENTS ----------- #
@bot.event
async def on_ready():
    print(f"✅ Initializing bot connection...")
    try:
        print(f"✅ {bot.user.name} is live and monitoring servers:")
        for g in bot.guilds:
            print(f" - {g.name} ({g.id})")
        check_sheet.start()
        print(f"✅ check_sheet task started.")
    except Exception as e:
        print(f"❌ Error in on_ready: {str(e)}")

# ----------- RUN BOT ----------- #
from keep_alive import keep_alive
print(f"✅ Starting keep_alive...")
keep_alive()
print(f"✅ Running bot with token...")
bot.run(DISCORD_TOKEN)