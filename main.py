Funnel
scanner — checks
lnd1..lndN
on
competitor
sites.
Usage:
python
scan_lnd_funnels.py
python
scan_lnd_funnels.py - -sites
sofiadate.com
anothersite.com - -max
300 - -concurrency
30

Output: lnd_funnels_YYYY - MM - DD.csv
"""

import asyncio
import csv
import argparse
from datetime import date
import aiohttp

# ── defaults ──────────────────────────────────────────────────────────────────
DEFAULT_SITES = ["sofiadate.com"]
DEFAULT_MAX   = 500
CONCURRENCY   = 20          # parallel requests
TIMEOUT_SEC   = 10

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# pages that exist but aren't real funnels (redirect to home, etc.)
IGNORE_CODES = {301, 302, 303, 307, 308, 404, 410, 403}


async def check_url(session: aiohttp.ClientSession, url: str, sem: asyncio.Semaphore):
    async with sem:
        try:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC),
                allow_redirects=False,   # catch redirects explicitly
            ) as resp:
                status = resp.status
                location = resp.headers.get("Location", "")

                # follow one redirect to detect redirect-to-homepage pattern
                if status in (301, 302, 303, 307, 308) and location:
                    # if it redirects back to root ("/", "/en/", etc.) → not a funnel
                    from urllib.parse import urlparse
                    parsed = urlparse(location)
                    path = parsed.path.rstrip("/")
                    if path in ("", "/en", "/uk", "/ru"):
                        return url, "redirect_to_home", location

                return url, status, location
        except asyncio.TimeoutError:
            return url, "timeout", ""
        except Exception as e:
            return url, f"error: {e}", ""


async def scan_site(site: str, max_n: int, concurrency: int):
    sem = asyncio.Semaphore(concurrency)
    urls = [f"https://www.{site}/lnd{n}" for n in range(1, max_n + 1)]

    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(headers=HEADERS, connector=connector) as session:
        tasks = [check_url(session, url, sem) for url in urls]
        results = []
        total = len(tasks)
        done = 0

        for coro in asyncio.as_completed(tasks):
            result = await coro
            done += 1
            if done % 50 == 0 or done == total:
                print(f"  {site}: {done}/{total} checked …", end="\r")
            results.append(result)

        print()
        return results


def is_live(status):
    """
Return
True if the
page is a
real, accessible
funnel.
