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

# List of swear words
SWEAR_WORDS = ["damn", "hell", "crap", "bloody", "freaking"]

# Keep track of already completed downloads and ETA notifications
known_completed_torrents = set()
notified_torrents = set()


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
        print("Failed to fetch active torrents")
        return []


def get_completed_downloads():
    """Fetch completed torrents."""
    response = qb_session.get(f"{QB_URL}/api/v2/torrents/info?filter=completed")
    if response.status_code == 200:
        return response.json()
    else:
        print("Failed to fetch completed torrents")
        return []


def calculate_eta(size_left, download_speed):
    """Calculate Estimated Time to Arrival (ETA)."""
    if download_speed > 0:
        seconds = size_left / download_speed
        return str(datetime.timedelta(seconds=int(seconds)))
    return "Unknown"


def initialize_known_completed():
    """Initialize the list of known completed downloads at startup."""
    global known_completed_torrents
    completed_torrents = get_completed_downloads()
    known_completed_torrents = {torrent["hash"] for torrent in completed_torrents}
    print(f"Ignoring {len(known_completed_torrents)} existing completed downloads")


@tasks.loop(seconds=30)
async def monitor_qbittorrent():
    """Monitor qBittorrent for downloads."""
    while True:
        # Check active downloads for ETA notifications
        active_downloads = get_active_downloads()
        for torrent in active_downloads:
            torrent_name = torrent["name"]
            torrent_hash = torrent["hash"]

            if torrent_hash not in notified_torrents:
                # Wait for stabilization (90 seconds)
                time.sleep(90)

                # Re-fetch torrent info for updated stats
                active_downloads = get_active_downloads()
                torrent_info = next(
                    (t for t in active_downloads if t["hash"] == torrent_hash), None
                )
                if torrent_info:
                    size_left = torrent_info["size"] - torrent_info["downloaded"]
                    download_speed = torrent_info["dlspeed"]
                    eta = calculate_eta(size_left, download_speed)
                    num_peers = torrent_info["num_complete"]
                    avg_speed = f"{download_speed / 1024 / 1024:.2f} MB/s"

                    for guild in client.guilds:
                        for channel in guild.text_channels:
                            try:
                                await channel.send(
                                    f"Download ETA for **{torrent_name}**: {eta}\n"
                                    f"Average Speed: {avg_speed}\n"
                                    f"Current Peers: {num_peers}"
                                )
                                break
                            except discord.errors.Forbidden:
                                continue

                notified_torrents.add(torrent_hash)  # Mark as notified

        # Check completed downloads for completion notifications
        completed_downloads = get_completed_downloads()
        for torrent in completed_downloads:
            torrent_name = torrent["name"]
            torrent_hash = torrent["hash"]

            if torrent_hash not in known_completed_torrents:
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

                # Mark this torrent as known
                known_completed_torrents.add(torrent_hash)

        # Pause before the next loop iteration
        time.sleep(30)


@client.event
async def on_ready():
    """Event triggered when the bot is ready."""
    print(f"Logged in as {client.user}")
    authenticate_qbittorrent()
    initialize_known_completed()  # Ignore existing completed downloads
    monitor_qbittorrent.start()


if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
