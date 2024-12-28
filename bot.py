import requests
import discord
from discord.ext import tasks
import time
import datetime
import os
import random

# Environment Variables
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
QB_URL = os.getenv("QB_URL")
QB_USERNAME = os.getenv("QB_USERNAME")
QB_PASSWORD = os.getenv("QB_PASSWORD")

client = discord.Client(intents=discord.Intents.default())

# qBittorrent session
qb_session = requests.Session()

# List of swear words to randomly select from
SWEAR_WORDS = [
    "damn",
    "hell",
    "crap",
    "bloody",
    "freaking",
    "frickin'",
    "dang",
    "bullshit",
    "arse",
    "bugger",
    "shit",
    "bastard",
    "son of a gun",
    "motherlover",
    "screw it",
    "what the hell",
    "jerk",
    "git",
    "numpty",
    "turd",
    "wanker",
    "dipstick",
    "dumbass",
    "knobhead",
    "pillock",
    "prat",
    "twat",
    "nincompoop",
    "tosser",
    "tool",
    "clown",
    "bampot",
    "knucklehead"
]


def authenticate_qbittorrent():
    """Authenticate with qBittorrent."""
    response = qb_session.post(
        f"{QB_URL}/api/v2/auth/login",
        data={"username": QB_USERNAME, "password": QB_PASSWORD},
    )
    if response.status_code == 200 and response.text == "Ok.":
        print("Authenticated with qBittorrent")
    else:
        print("Failed to authenticate with qBittorrent")
        raise Exception("Authentication failed")


def get_active_downloads():
    """Fetch active torrents."""
    response = qb_session.get(f"{QB_URL}/api/v2/torrents/info?filter=downloading")
    if response.status_code == 200:
        return response.json()
    else:
        print("Failed to fetch torrents")
        return []


def get_completed_downloads():
    """Fetch completed torrents."""
    response = qb_session.get(f"{QB_URL}/api/v2/torrents/info?filter=completed")
    if response.status_code == 200:
        return response.json()
    else:
        print("Failed to fetch torrents")
        return []


def calculate_eta(size_left, download_speed):
    """Calculate Estimated Time to Arrival (ETA)."""
    if download_speed > 0:
        seconds = size_left / download_speed
        return str(datetime.timedelta(seconds=int(seconds)))
    return "Unknown"


@tasks.loop(seconds=30)
async def monitor_qbittorrent():
    """Monitor qBittorrent for downloads."""
    notified_torrents = set()  # Track notified torrents for ETA
    completed_torrents = set()  # Track torrents already marked as completed

    while True:
        # Check active downloads for ETA notifications
        active_downloads = get_active_downloads()
        for torrent in active_downloads:
            torrent_name = torrent["name"]
            if torrent_name not in notified_torrents:
                size_left = torrent["size"] - torrent["downloaded"]
                download_speed = torrent["dlspeed"]

                # Notify in the first available text channel
                for guild in client.guilds:
                    for channel in guild.text_channels:
                        try:
                            await channel.send(f"Started download: **{torrent_name}**")
                            break
                        except discord.errors.Forbidden:
                            continue  # Skip channels where the bot lacks permission

                # Wait for stabilization (90 seconds)
                time.sleep(90)

                # Re-fetch the download speed and calculate ETA
                download_speed = get_active_downloads()[0]["dlspeed"]
                eta = calculate_eta(size_left, download_speed)
                for guild in client.guilds:
                    for channel in guild.text_channels:
                        try:
                            await channel.send(
                                f"Download ETA for **{torrent_name}**: {eta}"
                            )
                            break
                        except discord.errors.Forbidden:
                            continue

                notified_torrents.add(torrent_name)  # Mark torrent as notified

        # Check completed downloads for completion notifications
        completed_downloads = get_completed_downloads()
        for torrent in completed_downloads:
            torrent_name = torrent["name"]
            if torrent_name not in completed_torrents:
                swear_word = random.choice(SWEAR_WORDS)
                for guild in client.guilds:
                    for channel in guild.text_channels:
                        try:
                            await channel.send(
                                f"Download complete: **{torrent_name}**. What a {swear_word} masterpiece!"
                            )
                            break
                        except discord.errors.Forbidden:
                            continue

                completed_torrents.add(torrent_name)  # Mark torrent as completed

        # Pause before the next loop iteration
        time.sleep(30)


@client.event
async def on_ready():
    """Event triggered when the bot is ready."""
    print(f"Logged in as {client.user}")
    authenticate_qbittorrent()
    monitor_qbittorrent.start()


if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
