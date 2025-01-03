import os
import discord
import asyncio
import aiohttp
import logging
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FireControl")

# Load configuration from environment variables
QB_URL = os.getenv("QB_URL")
QB_USERNAME = os.getenv("QB_USERNAME")
QB_PASSWORD = os.getenv("QB_PASSWORD")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Pirate phrases for completed downloads
PIRATE_PHRASES = [
    "Yo-ho-ho!", "Arrr, me hearties!", "Shiver me timbers!", "A fine bounty indeed!",
    "Drink up, me hearties, yo-ho!", "By the powers!", "Aye, she be done!", "Well blow me down!",
    "We be rich, mates!", "To the depths with the rest!", "Treasure secured!", "A grand haul!",
    "Anchors aweigh!", "Plunder complete!", "Set sail for the next adventure!"
]

# Torrent Manager Class
class TorrentManager:
    def __init__(self, qb_url, qb_username, qb_password):
        self.qb_url = qb_url
        self.qb_username = qb_username
        self.qb_password = qb_password
        self.session = None  # Initialize the session as None
        self.authenticated = False

    async def get_session(self):
        """Ensure the aiohttp session is created."""
        if self.session is None:
            try:
                self.session = aiohttp.ClientSession()
            except Exception as e:
                logger.error(f"Failed to initialize aiohttp session: {e}")
                raise
        return self.session

    async def authenticate(self):
        """Authenticate with qBittorrent WebUI."""
        session = await self.get_session()
        login_url = f"{self.qb_url}/api/v2/auth/login"
        payload = {"username": self.qb_username, "password": self.qb_password}
        async with session.post(login_url, data=payload) as response:
            if response.status == 200:
                self.authenticated = True
                logger.info("Authenticated with qBittorrent.")
            else:
                logger.error("Failed to authenticate with qBittorrent.")
                self.authenticated = False

    async def get_torrent_states(self):
        """Fetch current torrent states."""
        if not self.authenticated:
            await self.authenticate()
        session = await self.get_session()
        torrents_url = f"{self.qb_url}/api/v2/torrents/info"
        async with session.get(torrents_url) as response:
            if response.status == 200:
                torrents = await response.json()
                return {t["hash"]: t for t in torrents}
            else:
                logger.error("Failed to retrieve torrent states.")
                return {}

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

# Initialize components
intents = discord.Intents.default()
intents.messages = True  # Ensure the bot can read messages
intents.guilds = True
intents.message_content = True  # Required for message content handling
client = discord.Client(intents=intents)

torrent_manager = TorrentManager(QB_URL, QB_USERNAME, QB_PASSWORD)

# Helper function for iterating through guilds and channels
def get_available_channel():
    """Retrieve the first channel the bot can send messages to."""
    for guild in client.guilds:
        for channel in guild.text_channels:
            logger.info(f"Bot has access to channel: {channel.name} in guild: {guild.name}")
            if channel.permissions_for(guild.me).send_messages:
                return channel
    return None

# Background task for monitoring torrents
async def monitor_torrents():
    previous_states = await torrent_manager.get_torrent_states()  # Initialize with current states
    while True:
        current_states = await torrent_manager.get_torrent_states()
        state_changes = {
            torrent_hash: torrent
            for torrent_hash, torrent in current_states.items()
            if torrent["state"] != previous_states.get(torrent_hash, {}).get("state")
        }

        for torrent_hash, torrent in state_changes.items():
            previous_state = previous_states.get(torrent_hash, {}).get("state")
            await handle_torrent_change(torrent, previous_state)

        previous_states = current_states  # Update previous states
        await asyncio.sleep(30)  # Poll every 30 seconds

# Handle torrent state changes
async def handle_torrent_change(torrent, previous_state):
    name = torrent["name"]
    state = torrent["state"]
    channel = get_available_channel()

    if channel:
        if state == "downloading":
            message = f"Avast! The download be startin' fer {name}! ⚓"
            await channel.send(message)
            await asyncio.sleep(90)  # Wait for stabilization
            stats_message = (
                f"Arrr, {name} be downloadin' at {torrent['dlspeed'] / 1_000_000:.2f} Mbps with {torrent['num_seeds']} mates connected! "
                f"ETA: {torrent['eta'] // 60} minutes."
            )
            await channel.send(stats_message)
        elif state == "stalledUP" and previous_state == "downloading":
            pirate_phrase = random.choice(PIRATE_PHRASES)
            message = f"{pirate_phrase} {name} be finished, ye scallywags! 🏴‍☠️"
            await channel.send(message)
        elif state == "queuedDL":
            message = f"Arrr, {name} be queued fer download. Rank in queue: {torrent['priority']}!"
            await channel.send(message)



@client.event
async def on_ready():
    logger.info(f"We have logged in as {client.user}")
    client.loop.create_task(monitor_torrents())

@client.event
async def on_message(message):
    logger.info(f"Received message: {message.content} in channel: {message.channel.name} from {message.author}")
    if message.author == client.user:
        return

    if message.content.lower() == "!status":
        stats = await torrent_manager.get_torrent_states()
        downloading = len([t for t in stats.values() if t["state"] == "downloading"])
        queued = len([t for t in stats.values() if t["state"] == "queuedDL"])
        seeding = len([t for t in stats.values() if t["state"] == "stalledUP"])
        message_text = (
            f"Arrr, here be the current state of yer downloads:\n"
            f"🚢 Downloading: {downloading} torrents\n"
            f"📜 Queued: {queued}\n"
            f"⚓ Seeding: {seeding}"
        )
        await message.channel.send(message_text)

    elif message.content.lower() == "!eta":
        stats = await torrent_manager.get_torrent_states()
        downloading_torrents = [
            t for t in stats.values() if t["state"] == "downloading"
        ]
        if downloading_torrents:
            count = len(downloading_torrents)
            message_lines = [
                f"{i+1}. {t['name']} (Speed: {t['dlspeed'] / 1_000_000:.2f} Mbps, ETA: {t['eta'] // 60} minutes)"
                for i, t in enumerate(downloading_torrents)
            ]
            message_text = (
                f"Arrr, there be {count} torrents currently downloadin':\n" + "\n".join(message_lines)
            )
            await message.channel.send(message_text)
        else:
            await message.channel.send("No downloads be active, ye landlubber!")

    elif message.content.lower() == "!queue":
        stats = await torrent_manager.get_torrent_states()
        queued_torrents = [
            t for t in stats.values() if t["state"] == "queuedDL"
        ]
        if queued_torrents:
            count = len(queued_torrents)
            message_lines = [
                f"{i+1}. {t['name']} (Priority: {t.get('priority', 'N/A')})"
                for i, t in enumerate(queued_torrents)
            ]
            message_text = (
                f"Arrr, there be {count} torrents queued fer download:\n" + "\n".join(message_lines)
            )
            await message.channel.send(message_text)
        else:
            await message.channel.send("No torrents be queued, ye scallywags!")

async def main():
    await torrent_manager.authenticate()
    await client.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
