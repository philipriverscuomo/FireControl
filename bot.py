import requests
import discord
from discord.ext import tasks
import time
import datetime
import os

# Environment Variables
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
QB_URL = os.getenv("QB_URL")
QB_USERNAME = os.getenv("QB_USERNAME")
QB_PASSWORD = os.getenv("QB_PASSWORD")

client = discord.Client(intents=discord.Intents.default())

# qBittorrent session
qb_session = requests.Session()


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


def calculate_eta(size_left, download_speed):
    """Calculate Estimated Time to Arrival (ETA)."""
    if download_speed > 0:
        seconds = size_left / download_speed
        return str(datetime.timedelta(seconds=int(seconds)))
    return "Unknown"


@tasks.loop(seconds=30)
async def monitor_qbittorrent():
    """Monitor qBittorrent for new downloads."""
    active_downloads = get_active_downloads()
    for torrent in active_downloads:
        if "eta_notified" not in torrent:  # Track ETA notifications
            torrent_name = torrent["name"]
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

            torrent["eta_notified"] = True  # Mark this torrent as notified


@client.event
async def on_ready():
    """Event triggered when the bot is ready."""
    print(f"Logged in as {client.user}")
    authenticate_qbittorrent()
    monitor_qbittorrent.start()


if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
