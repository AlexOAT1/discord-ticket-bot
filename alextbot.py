# alextbot.py

import discord
from discord import app_commands
from discord.ext import commands
import json
import os

# ------------- KONFIGURATION -------------
TOKEN = "YOUR_DISCORD_BOT_TOKEN"
OWNER_ID = "YOUR_ID"
DATAPATH = "data.json"
TICKET_CATEGORY_NAME = "tickets"

# ------------- SPEICHERN / LADEN -------------

def load_data():
    if not os.path.exists(DATAPATH):
        with open(DATAPATH, "w") as f:
            json.dump({"channels": {}, "allowed_roles": []}, f)
    with open(DATAPATH, "r") as f:
        return json.load(f)

def save_data():
    with open(DATAPATH, "w") as f:
        json.dump(data, f, indent=4)

# ------------- BOT SETUP -------------
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="/", intents=intents)
tree = bot.tree

data = load_data()

# ------------- PERMISSIONS TEST -------------
async def has_permission(interaction: discord.Interaction) -> bool:
    if interaction.user.guild_permissions.administrator:
        return True
    if str(interaction.user.id) == OWNER_ID:
        return True
    allowed_roles = data.get("allowed_roles", [])
    user_roles = [role.id for role in interaction.user.roles]
    return any(role_id in allowed_roles for role_id in user_roles)

# ------------- BUTTON VIEW CLASSES -------------

class TicketView(discord.ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=None)
        self.channel_id = channel_id
        reasons = data["channels"].get(str(channel_id), {}).get("reasons", ["standard"])
        for reason in reasons:
            self.add_item(TicketButton(reason, channel_id))

class TicketButton(discord.ui.Button):
    def __init__(self, reason, channel_id):
        super().__init__(label=reason, style=discord.ButtonStyle.primary, custom_id=f"ticket_{reason}_{channel_id}")
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
        if category is None:
            category = await guild.create_category(TICKET_CATEGORY_NAME)

        ticket_name = f"{self.label}-{interaction.user.name}".replace(' ', '-')
        ticket_channel = await guild.create_text_channel(ticket_name, category=category)

        # Set permissions
        await ticket_channel.set_permissions(guild.default_role, view_channel=False)
        await ticket_channel.set_permissions(interaction.user, view_channel=True, send_messages=True)
        for role_id in data.get("allowed_roles", []):
            role = guild.get_role(role_id)
            if role:
                await ticket_channel.set_permissions(role, view_channel=True, send_messages=True)

        info_text = data["channels"].get(str(self.channel_id), {}).get("info2", "Willkommen im Ticket!")
        delete_button_text = data["channels"].get(str(self.channel_id), {}).get("deleteticket", "Ticket löschen")

        view = CloseTicketView()
        view.children[0].label = delete_button_text

        await ticket_channel.send(info_text, view=view)
        await interaction.response.send_message(f"Ticket erstellt: {ticket_channel.mention}", ephemeral=True)

class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CloseTicketButton())

class CloseTicketButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Ticket schließen", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        await interaction.channel.delete()

# ------------- COMMANDS -------------

@tree.command(name="tb_channel_add", description="Füge einen Channel hinzu")
async def tb_channel_add(interaction: discord.Interaction, channel: discord.TextChannel):
    if not await has_permission(interaction):
        await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
        return
    data["channels"][str(channel.id)] = {"reasons": ["standard"], "info": "Ticket erstellen:", "info2": "Willkommen im Ticket!", "deleteticket": "Ticket löschen"}
    save_data()
    await update_ticket_message(channel)
    await interaction.response.send_message(f"Ticket Nachricht in {channel.mention} hinzugefügt.", ephemeral=True)

@tree.command(name="tb_channel_remove", description="Entferne einen Ticket Channel")
async def tb_channel_remove(interaction: discord.Interaction, channel: discord.TextChannel):
    if not await has_permission(interaction):
        await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
        return
    await clear_channel(channel)
    data["channels"].pop(str(channel.id), None)
    save_data()
    await interaction.response.send_message(f"Ticket Nachricht in {channel.mention} entfernt.", ephemeral=True)

@tree.command(name="tb_text_message_info", description="Setze Infotext")
async def tb_text_message_info(interaction: discord.Interaction, channel: discord.TextChannel, text: str):
    if not await has_permission(interaction):
        await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
        return
    data["channels"].setdefault(str(channel.id), {})["info"] = text
    save_data()
    await update_ticket_message(channel)
    await interaction.response.send_message(f"Infotext aktualisiert.", ephemeral=True)

@tree.command(name="tb_text_message_info2", description="Setze Info2 Text")
async def tb_text_message_info2(interaction: discord.Interaction, text: str):
    if not await has_permission(interaction):
        await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
        return
    for ch in data["channels"].values():
        ch["info2"] = text
    save_data()
    await interaction.response.send_message(f"Info2 Text aktualisiert.", ephemeral=True)

@tree.command(name="tb_text_button_deleteticket", description="Setze Button Text zum Ticket Löschen")
async def tb_text_button_deleteticket(interaction: discord.Interaction, text: str):
    if not await has_permission(interaction):
        await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
        return
    for ch in data["channels"].values():
        ch["deleteticket"] = text
    save_data()
    await interaction.response.send_message(f"Button Text aktualisiert.", ephemeral=True)

@tree.command(name="tb_ticketreason_add", description="Füge Grund hinzu")
async def tb_ticketreason_add(interaction: discord.Interaction, channel: discord.TextChannel, reason: str):
    if not await has_permission(interaction):
        await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
        return
    reasons = data["channels"].setdefault(str(channel.id), {}).setdefault("reasons", [])
    if reason not in reasons:
        reasons.append(reason)
    save_data()
    await update_ticket_message(channel)
    await interaction.response.send_message(f"Grund '{reason}' hinzugefügt.", ephemeral=True)

@tree.command(name="tb_ticketreason_remove", description="Entferne Grund")
async def tb_ticketreason_remove(interaction: discord.Interaction, channel: discord.TextChannel, reason: str):
    if not await has_permission(interaction):
        await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
        return
    reasons = data["channels"].get(str(channel.id), {}).get("reasons", [])
    if reason in reasons:
        reasons.remove(reason)
    save_data()
    await update_ticket_message(channel)
    await interaction.response.send_message(f"Grund '{reason}' entfernt.", ephemeral=True)

@tree.command(name="tb_reload", description="Lade alle Nachrichten neu")
async def tb_reload(interaction: discord.Interaction):
    if not await has_permission(interaction):
        await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
        return
    for channel_id in data["channels"]:
        channel = bot.get_channel(int(channel_id))
        await clear_channel(channel)
        await update_ticket_message(channel)
    await interaction.response.send_message("Alle Nachrichten neu geladen.", ephemeral=True)

@tree.command(name="tb_reset", description="Setzt alles zurück")
async def tb_reset(interaction: discord.Interaction):
    if not await has_permission(interaction):
        await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
        return
    for channel_id in data["channels"]:
        channel = bot.get_channel(int(channel_id))
        await clear_channel(channel)
    data["channels"] = {}
    save_data()
    await interaction.response.send_message("Bot zurückgesetzt.", ephemeral=True)

@tree.command(name="tb_roll_add", description="Füge eine Rolle hinzu")
async def tb_roll_add(interaction: discord.Interaction, role: discord.Role):
    if not await has_permission(interaction):
        await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
        return
    if role.id not in data["allowed_roles"]:
        data["allowed_roles"].append(role.id)
    save_data()
    await interaction.response.send_message(f"Rolle {role.name} hinzugefügt.", ephemeral=True)

@tree.command(name="tb_roll_remove", description="Entferne eine Rolle")
async def tb_roll_remove(interaction: discord.Interaction, role: discord.Role):
    if not await has_permission(interaction):
        await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
        return
    if role.id in data["allowed_roles"]:
        data["allowed_roles"].remove(role.id)
    save_data()
    await interaction.response.send_message(f"Rolle {role.name} entfernt.", ephemeral=True)

# ------------- HELP FEATURES -------------

async def update_ticket_message(channel):
    await clear_channel(channel)
    info_text = data["channels"].get(str(channel.id), {}).get("info", "Ticket erstellen:")
    await channel.send(info_text, view=TicketView(channel.id))

async def clear_channel(channel):
    async for message in channel.history(limit=50):
        await message.delete()

# ------------- BOT EVENTS -------------

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot {bot.user} ist online und Slash Commands sind synchronisiert!")

bot.run(TOKEN)
