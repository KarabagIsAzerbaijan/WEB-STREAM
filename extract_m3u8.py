#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robust m3u8 extractor for pages like kepeztv.az players.
- Tries: direct URL, HTML regex, <script> configs, <iframe> recursion
- Sends proper headers (User-Agent, Referer, Origin)
- Validates that the found URL is a real HLS manifest (#EXTM3U)
- Optional yt-dlp fallback (if installed)
- Optional wrapper .m3u creator with UA/Referer hints for players
"""

import re
import sys
import json
import argparse
from urllib.parse import urljoin, urlparse
from typing import Optional, Tuple, List

try:
    import httpx
except ImportError:
    print("Please: pip install httpx", file=sys.stderr); raise

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

M3U8_RX = re.compile(r"""(?i)\bhttps?://[^\s'"]+\.m3u8(?:\?[^\s'"]*)?""")
SOURCE_KV_RX = re.compile(r"""(?i)(source|file|src)\s*[:=]\s*['"]([^'"]+\.m3u8[^'"]*)['"]""")
IFRAME_SRC_RX = re.compile(r"""(?i)<iframe[^>]+src=['"]([^'"]+)['"]""")

def build_headers(referer: Optional[str], origin: Optional[str], ua: str) -> dict:
    h = {
        "User-Agent": ua,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    if referer:
        h["Referer"] = referer
    if origin:
        h["Origin"] = origin
    return h

def is_manifest(client: httpx.Client, url: str, headers: dict) -> bool:
    try:
        r = client.get(url, headers=headers, timeout=15, follow_redirects=True)
        if r.status_code != 200:
            return False
        text = r.text.strip()
        return text.startswith("#EXTM3U")
    except Exception:
        return False

def fetch_text(client: httpx.Client, url: str, headers: dict) -> str:
    r = client.get(url, headers=headers, timeout=20, follow_redirects=True)
    r.raise_for_status()
    return r.text

def search_manifest_in_text(text: str, base_url: str) -> List[str]:
    urls = set()

    # 1) direct .m3u8 patterns
    for m in M3U8_RX.finditer(text):
        urls.add(m.group(0))

    # 2) key:value script configs: source/file/src: "url.m3u8"
    for m in SOURCE_KV_RX.finditer(text):
        urls.add(m.group(2))

    # Resolve relatives
    resolved = []
    for u in urls:
        resolved.append(urljoin(base_url, u))
    return list(dict.fromkeys(resolved))  # preserve order / de-dup

def find_iframes(text: str, base_url: str) -> List[str]:
    frames = []
    for m in IFRAME_SRC_RX.finditer(text):
        frames.append(urljoin(base_url, m.group(1)))
    return frames

def smart_origin(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"

def try_extract(client: httpx.Client, url: str, headers: dict, depth: int = 0, max_depth: int = 2) -> Optional[str]:
    """Recursive extractor: page -> m3u8 or iframe -> page -> m3u8"""
    if depth > max_depth:
        return None

    # If caller already gave .m3u8 directly
    if url.lower().endswith(".m3u8"):
        return url if is_manifest(client, url, headers) else None

    html = fetch_text(client, url, headers)

    # 1) scan current page
    candidates = search_manifest_in_text(html, url)
    for cand in candidates:
        # Use current page URL as referer by default
        local_headers = dict(headers)
        local_headers.setdefault("Referer", url)
        local_headers.setdefault("Origin", smart_origin(url))
        if is_manifest(client, cand, local_headers):
            return cand

    # 2) recurse into iframes
    for frame in find_iframes(html, url):
        # when entering iframe, set referer to parent URL
        frame_headers = dict(headers)
        frame_headers["Referer"] = url
        frame_headers["Origin"]  = smart_origin(url)
        got = try_extract(client, frame, frame_headers, depth + 1, max_depth)
        if got:
            return got

    return None

def yt_dlp_fallback(page_url: str) -> Optional[str]:
    """Try yt-dlp to resolve HLS url; returns manifest URL if any."""
    try:
        import subprocess, shutil, tempfile
        if not shutil.which("yt-dlp"):
            return None
        with tempfile.TemporaryDirectory() as td:
            cmd = ["yt-dlp", "-J", "--no-warnings", "--skip-download", page_url]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if proc.returncode != 0:
                return None
            data = json.loads(proc.stdout)
            # Try top-level 'url' for HLS, or from formats
            if isinstance(data, dict):
                url = data.get("url")
                if isinstance(url, str) and url.endswith(".m3u8"):
                    return url
                for f in data.get("formats", []) or []:
                    u = f.get("url")
                    if isinstance(u, str) and ".m3u8" in u:
                        return u
    except Exception:
        return None
    return None

def write_output(path: str, manifest_url: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write("#EXT-X-VERSION:3\n")
        f.write(f"{manifest_url}\n")

def write_wrapper_m3u(path: str, name: str, manifest_url: str, referer: Optional[str], ua: str):
    """Plain .m3u wrapper with VLC hints; many players also respect UA header mapping."""
    with open(path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f"#EXTINF:-1,{name}\n")
        if referer:
            f.write(f"#EXTVLCOPT:http-referrer={referer}\n")
        if ua:
            f.write(f"#EXTVLCOPT:http-user-agent={ua}\n")
        f.write(f"{manifest_url}\n")

def main():
    ap = argparse.ArgumentParser(description="Extract real .m3u8 from a webpage/player")
    ap.add_argument("url", help="Page URL (or .m3u8 directly)")
    ap.add_argument("-o", "--out", default="output.m3u8", help="Output file path (HLS manifest or wrapper)")
    ap.add_argument("--ua", default=DEFAULT_UA, help="Custom User-Agent")
    ap.add_argument("--referer", help="Force Referer header")
    ap.add_argument("--origin", help="Force Origin header")
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--max-depth", type=int, default=2)
    ap.add_argument("--write-wrapper", action="store_true", help="Write .m3u wrapper (with UA/Referer) instead of raw manifest")
    ap.add_argument("--name", default="Channel", help="Display name for wrapper")
    ap.add_argument("--allow-yt-dlp", action="store_true", help="Try yt-dlp if HTML parse fails")
    args = ap.parse_args()

    origin = args.origin or smart_origin(args.url)
    headers = build_headers(args.referer, origin, args.ua)

    limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
    transport = httpx.HTTPTransport(retries=2)
    with httpx.Client(http2=True, limits=limits, transport=transport, headers=headers) as client:
        found = try_extract(client, args.url, headers, depth=0, max_depth=args.max_depth)

        if not found and args.allow_yt_dlp:
            found = yt_dlp_fallback(args.url)

        if not found:
            print("No playable .m3u8 found.", file=sys.stderr)
            sys.exit(2)

        if args.write-wrapper:
            write_wrapper_m3u(args.out, args.name, found, args.referer or args.url, args.ua)
        else:
            # Validate once more with final headers (use found url as base for origin)
            h
