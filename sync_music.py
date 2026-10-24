import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
DEFAULT_YT_EMBED = "https://www.youtube.com/embed/videoseries?list=UUvRDAEFiy8wnjavvDv5pzHg"
DEFAULT_SP_EMBED = "https://open.spotify.com/embed/artist/6pS4jqJo9ZW5aKZ2wunsQa?utm_source=generator&theme=0"
DEFAULT_AM_EMBED = "https://music.amazon.co.jp/embed/B0HH3V5D9Y/?id=B0HH3V5D9Y&marketplaceId=A1VC38T7YXB528&musicTerritory=JP"

NON_SONG_PATTERNS = re.compile(
    r"(?:^ufc\d|^mk\s*\d|serena\s*ver|serena\s*\d+\.\d+|アルファリリース|リリース記念\s*#)",
    re.I,
)


def is_non_song_video(title: str) -> bool:
    return bool(NON_SONG_PATTERNS.search(title or ""))


def norm_title(title: str) -> str:
    if not title:
        return ""
    base = re.sub(r"\s*[\(（][^\)）]*[\)）]", "", title)
    base = base.replace("継ぎ人", "つぎびと").replace("商人", "しょうにん")
    return re.sub(r"[\s『』「」\"'_\-\.,!！?？/／]", "", base).lower()


existing_tracks = {}
try:
    with open("tracks.json", "r", encoding="utf-8") as f:
        existing_tracks = json.load(f)
except Exception:
    existing_tracks = {}

by_norm = {}


def ensure_record(title: str, preferred_key: str) -> dict:
    nt = norm_title(title)
    if not nt:
        nt = preferred_key
    if nt not in by_norm:
        q = urllib.parse.quote(f"Shinji Sakiyama {title}")
        by_norm[nt] = {
            "key": preferred_key,
            "title": title,
            "ytEmbed": DEFAULT_YT_EMBED,
            "ytLink": f"https://music.youtube.com/search?q={q}",
            "spEmbed": DEFAULT_SP_EMBED,
            "spLink": f"https://open.spotify.com/search/{q}",
            "amEmbed": DEFAULT_AM_EMBED,
            "amLink": f"https://music.amazon.co.jp/search/{q}",
        }
    return by_norm[nt]


for k, v in existing_tracks.items():
    t = v.get("title", "")
    if not t or is_non_song_video(t):
        continue
    rec = ensure_record(t, k)
    if "/embed/" in v.get("ytEmbed", "") and "videoseries" not in v.get("ytEmbed", ""):
        rec["ytEmbed"] = v["ytEmbed"]
        rec["ytLink"] = v.get("ytLink", rec["ytLink"])
    if "/embed/track/" in v.get("spEmbed", ""):
        rec["spEmbed"] = v["spEmbed"]
        rec["spLink"] = v.get("spLink", rec["spLink"])
    if "/embed/" in v.get("amEmbed", "") and "B0HH3V5D9Y" not in v.get("amEmbed", ""):
        rec["amEmbed"] = v["amEmbed"]
        rec["amLink"] = v.get("amLink", rec["amLink"])

# 1. Fetch YouTube RSS feeds (Topic channel UCcGlNKi4PILBbgWYbpGTO2A + Official channel UCvRDAEFiy8wnjavvDv5pzHg)
channel_ids = [
    "UCcGlNKi4PILBbgWYbpGTO2A",
    "UCvRDAEFiy8wnjavvDv5pzHg",
]
ns = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
for cid in channel_ids:
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=12) as resp:
            root = ET.fromstring(resp.read())
        for entry in root.findall("atom:entry", ns):
            vid_el = entry.find("yt:videoId", ns)
            title_el = entry.find("atom:title", ns)
            if vid_el is not None and title_el is not None and vid_el.text and title_el.text:
                vid = vid_el.text.strip()
                title = title_el.text.strip()
                if cid == "UCvRDAEFiy8wnjavvDv5pzHg" and is_non_song_video(title):
                    continue
                rec = ensure_record(title, f"yt_{vid}")
                rec["ytEmbed"] = f"https://www.youtube.com/embed/{vid}"
                rec["ytLink"] = f"https://music.youtube.com/watch?v={vid}"
    except Exception as e:
        print("YouTube RSS note:", e)

# 2. Fetch Spotify Artist Embed page (__NEXT_DATA__) to resolve exact Spotify track IDs
try:
    sp_req = urllib.request.Request(
        "https://open.spotify.com/embed/artist/6pS4jqJo9ZW5aKZ2wunsQa",
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(sp_req, timeout=12) as resp:
        sp_html = resp.read().decode("utf-8", "ignore")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', sp_html, re.S)
    if m:
        sp_data = json.loads(m.group(1))
        entity = (
            sp_data.get("props", {})
            .get("pageProps", {})
            .get("state", {})
            .get("data", {})
            .get("entity", {})
        )
        for item in entity.get("trackList", []):
            tname = (item.get("title") or "").strip()
            uri = item.get("uri") or ""
            if tname and uri.startswith("spotify:track:"):
                sp_id = uri.split(":")[-1]
                rec = ensure_record(tname, f"sp_{sp_id}")
                rec["spEmbed"] = f"https://open.spotify.com/embed/track/{sp_id}?utm_source=generator&theme=0"
                rec["spLink"] = f"https://open.spotify.com/track/{sp_id}"
except Exception as e:
    print("Spotify artist embed note:", e)

# 3. Fetch Apple Music / iTunes Lookup API + resolve cross-platform Spotify / YouTube / Amazon ASIN via song.link
itunes_ids_by_norm = {}
for country in ("JP", "US"):
    itunes_url = f"https://itunes.apple.com/lookup?id=6785027836&entity=song&country={country}&limit=200"
    try:
        req = urllib.request.Request(itunes_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for item in data.get("results", []):
            if item.get("wrapperType") == "track" and item.get("kind") == "song":
                tid = item.get("trackId")
                tname = (item.get("trackName") or "").strip()
                if tid and tname:
                    rec = ensure_record(tname, f"itunes_{tid}")
                    itunes_ids_by_norm[norm_title(tname)] = tid
    except Exception as e:
        print("iTunes note:", e)


def enrich_from_songlink(lookup_path: str, rec: dict):
    try:
        sl_url = f"https://song.link/{lookup_path}"
        req = urllib.request.Request(sl_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", "ignore")
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if not m:
            return
        text = m.group(1)
        if "/embed/track/" not in rec["spEmbed"]:
            spm = re.search(r"https://open\.spotify\.com/track/([a-zA-Z0-9]+)", text)
            if spm:
                sp_id = spm.group(1)
                rec["spEmbed"] = f"https://open.spotify.com/embed/track/{sp_id}?utm_source=generator&theme=0"
                rec["spLink"] = f"https://open.spotify.com/track/{sp_id}"
        if "videoseries" in rec["ytEmbed"]:
            ytm = re.search(r"https://(?:www\.|music\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})", text)
            if ytm:
                vid = ytm.group(1)
                rec["ytEmbed"] = f"https://www.youtube.com/embed/{vid}"
                rec["ytLink"] = f"https://music.youtube.com/watch?v={vid}"
        if "B0HH3V5D9Y" in rec["amEmbed"]:
            amm = re.search(
                r"https://music\.amazon\.[a-z\.]+/albums/([A-Z0-9]+)\?trackAsin=([A-Z0-9]+)",
                text,
            )
            if amm:
                alb_asin, trk_asin = amm.group(1), amm.group(2)
                rec["amEmbed"] = (
                    f"https://music.amazon.co.jp/embed/{trk_asin}/?id={trk_asin}"
                    "&marketplaceId=A1VC38T7YXB528&musicTerritory=JP"
                )
                rec["amLink"] = f"https://music.amazon.co.jp/albums/{alb_asin}?trackAsin={trk_asin}"
            else:
                amm_alb = re.search(r"https://music\.amazon\.[a-z\.]+/albums/([A-Z0-9]+)", text)
                if amm_alb:
                    alb_asin = amm_alb.group(1)
                    rec["amEmbed"] = (
                        f"https://music.amazon.co.jp/embed/{alb_asin}/?id={alb_asin}"
                        "&marketplaceId=A1VC38T7YXB528&musicTerritory=JP"
                    )
                    rec["amLink"] = f"https://music.amazon.co.jp/albums/{alb_asin}"
    except Exception:
        pass


for nt, rec in by_norm.items():
    needs_enrich = (
        "videoseries" in rec["ytEmbed"]
        or "/embed/track/" not in rec["spEmbed"]
        or "B0HH3V5D9Y" in rec["amEmbed"]
    )
    if not needs_enrich:
        continue
    tid = itunes_ids_by_norm.get(nt)
    if tid:
        enrich_from_songlink(f"i/{tid}", rec)
    if ("/embed/track/" not in rec["spEmbed"] or "B0HH3V5D9Y" in rec["amEmbed"]) and "/embed/" in rec["ytEmbed"] and "videoseries" not in rec["ytEmbed"]:
        vid = rec["ytEmbed"].rsplit("/", 1)[-1]
        enrich_from_songlink(f"y/{vid}", rec)

output_tracks = {}
for nt, rec in by_norm.items():
    k = rec["key"]
    output_tracks[k] = {
        "title": rec["title"],
        "ytEmbed": rec["ytEmbed"],
        "ytLink": rec["ytLink"],
        "spEmbed": rec["spEmbed"],
        "spLink": rec["spLink"],
        "amEmbed": rec["amEmbed"],
        "amLink": rec["amLink"],
    }

with open("tracks.json", "w", encoding="utf-8") as f:
    json.dump(output_tracks, f, ensure_ascii=False, indent=2)
print(f"Synced {len(output_tracks)} unified tracks into tracks.json")
