import requests
import discord
from discord.ext import tasks
import asyncio
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

# Keep track of already completed downloads, ETA notifications, and queued torrents
known_completed_torrents = set()
notified_torrents = set()
known_queued_torrents = set()


def authenticate_qbittorrent():
    """Authenticate with qBittorrent."""
    response = qb_session.post(
        f"{QB_URL}/api/v2/auth/login",
        data={"username": QB_USERNAME, "password": QB_PASSWORD},
    )
    if response.status_code == 200 and response.text == "Ok.":
        print("Arr, we've logged in to the qBittorrent treasure chest!")
    else:
        print("Blast it! Failed to log in to qBittorrent.")
        raise Exception("Authentication failed")


def get_active_downloads():
    """Fetch active torrents."""
    response = qb_session.get(f"{QB_URL}/api/v2/torrents/info?filter=downloading")
    if response.status_code == 200:
        torrents = response.json()
        print(f"Active Downloads: {len(torrents)} | Data: {torrents}")  # Debug log
        return torrents
    else:
        print("Curses! Couldn't fetch active downloads.")
        return []


def get_queued_torrents():
    """Fetch queued torrents."""
    response = qb_session.get(f"{QB_URL}/api/v2/torrents/info?filter=stalled")
    if response.status_code == 200:
        torrents = [torrent for torrent in response.json() if torrent.get("state") == "stalled"]
        print(f"Queued Torrents: {len(torrents)} | Data: {torrents}")  # Debug log
        return torrents
    else:
        print("Arr, the queue be hidden from us!")
        return []


def get_completed_downloads():
    """Fetch completed torrents."""
    response = qb_session.get(f"{QB_URL}/api/v2/torrents/info?filter=completed")
    if response.status_code == 200:
        torrents = response.json()
        print(f"Completed Torrents: {len(torrents)} | Data: {torrents}")  # Debug log
        return torrents
    else:
        print("Shiver me timbers! Can't find completed torrents.")
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
    print(f"Marking {len(known_completed_torrents)} treasures as already plundered.")


def initialize_known_queued():
    """Initialize the list of known queued downloads at startup."""
    global known_queued_torrents
    queued_torrents = get_queued_torrents()
    known_queued_torrents = {torrent["hash"] for torrent in queued_torrents}
    print(f"Spotted {len(known_queued_torrents)} torrents waiting in the brig.")


@tasks.loop(seconds=30)
async def monitor_qbittorrent():
    """Monitor qBittorrent for downloads and queue changes."""
    print("Scanning the horizon for queued torrents...")  # Debug log
    queued_torrents = get_queued_torrents()
    for torrent in queued_torrents:
        torrent_name = torrent["name"]
        torrent_hash = torrent["hash"]
        queue_position = torrent.get("priority", 0)  # Assuming priority is queue position

        if torrent_hash not in known_queued_torrents:
            known_queued_torrents.add(torrent_hash)  # Add first to prevent duplicate sends
            print(f"New torrent queued: {torrent_name} | Position: {queue_position}")  # Debug log
            for guild in client.guilds:
                for channel in guild.text_channels:
                    try:
                        await channel.send(
                            f"Torrent added to the brig: **{torrent_name}**\n"
                            f"Queue position: {queue_position}\n"
                            f"Total torrents in the brig: {len(queued_torrents)}"
                        )
                        break
                    except discord.errors.Forbidden:
                        continue

    active_hashes = {torrent["hash"] for torrent in get_active_downloads()}
    completed_hashes = {torrent["hash"] for torrent in get_completed_downloads()}
    print(f"Updating known brig prisoners, releasing {len(active_hashes | completed_hashes)}.")  # Debug log
    known_queued_torrents.difference_update(active_hashes | completed_hashes)

    active_downloads = get_active_downloads()
    print(f"Checking the fleet's active downloads: {len(active_downloads)}")  # Debug log
    for torrent in active_downloads:
        torrent_name = torrent["name"]
        torrent_hash = torrent["hash"]

        if torrent_hash not in notified_torrents:
            print(f"Torrent started downloading: {torrent_name}")  # Debug log
            await asyncio.sleep(90)

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
                                f"**{torrent_name}** be downloading!\n"
                                f"ETA: {eta}\n"
                                f"Speed: {avg_speed}\n"
                                f"Mateys connected: {num_peers}"
                            )
                            break
                        except discord.errors.Forbidden:
                            continue

            notified_torrents.add(torrent_hash)

    completed_downloads = get_completed_downloads()
    print(f"Scanning completed treasures: {len(completed_downloads)}")  # Debug log
    for torrent in completed_downloads:
        torrent_name = torrent["name"]
        torrent_hash = torrent["hash"]

        if torrent_hash not in known_completed_torrents:
            print(f"Torrent completed: {torrent_name}")  # Debug log
            for guild in client.guilds:
                for channel in guild.text_channels:
                    try:
                        await channel.send(
                            f"**{torrent_name}** be done! Treasure plundered successfully! 🏴‍☠️"
                        )
                        break
                    except discord.errors.Forbidden:
                        continue

            known_completed_torrents.add(torrent_hash)

    await asyncio.sleep(30)


@client.event
async def on_ready():
    print(f"Aye aye, captain! Logged in as {client.user}")
    authenticate_qbittorrent()
    initialize_known_completed()
    initialize_known_queued()
    monitor_qbittorrent.start()


if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
