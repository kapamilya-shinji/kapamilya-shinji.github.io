import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

tracks = {}
channel_ids = [
    "UCcGlNKi4PILBbgWYbpGTO2A",
    "UCvRDAEFiy8wnjavvDv5pzHg",
]
ns = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
for cid in channel_ids:
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            root = ET.fromstring(resp.read())
        for entry in root.findall("atom:entry", ns):
            vid_el = entry.find("yt:videoId", ns)
            title_el = entry.find("atom:title", ns)
            if vid_el is not None and title_el is not None and vid_el.text and title_el.text:
                vid = vid_el.text.strip()
                title = title_el.text.strip()
                key = f"yt_{vid}"
                q = urllib.parse.quote(f"Shinji Sakiyama {title}")
                tracks[key] = {
                    "title": title,
                    "ytEmbed": f"https://www.youtube.com/embed/{vid}",
                    "ytLink": f"https://music.youtube.com/watch?v={vid}",
                    "spEmbed": "https://open.spotify.com/embed/artist/6pS4jqJo9ZW5aKZ2wunsQa?utm_source=generator&theme=0",
                    "spLink": f"https://open.spotify.com/search/{q}",
                    "amEmbed": "https://music.amazon.co.jp/embed/B0HH3V5D9Y/?id=B0HH3V5D9Y&marketplaceId=A1VC38T7YXB528&musicTerritory=JP",
                    "amLink": f"https://music.amazon.co.jp/search/{q}",
                }
    except Exception as e:
        print("YouTube RSS note:", e)

for country in ("JP", "US"):
    itunes_url = f"https://itunes.apple.com/lookup?id=6785027836&entity=song&country={country}&limit=200"
    try:
        req = urllib.request.Request(itunes_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for item in data.get("results", []):
            if item.get("wrapperType") == "track" and item.get("kind") == "song":
                tid = item.get("trackId")
                tname = item.get("trackName")
                if tid and tname:
                    key = f"itunes_{tid}"
                    if key not in tracks:
                        q = urllib.parse.quote(f"Shinji Sakiyama {tname}")
                        tracks[key] = {
                            "title": tname,
                            "ytEmbed": "https://www.youtube.com/embed/videoseries?list=UUvRDAEFiy8wnjavvDv5pzHg",
                            "ytLink": f"https://music.youtube.com/search?q={q}",
                            "spEmbed": "https://open.spotify.com/embed/artist/6pS4jqJo9ZW5aKZ2wunsQa?utm_source=generator&theme=0",
                            "spLink": f"https://open.spotify.com/search/{q}",
                            "amEmbed": "https://music.amazon.co.jp/embed/B0HH3V5D9Y/?id=B0HH3V5D9Y&marketplaceId=A1VC38T7YXB528&musicTerritory=JP",
                            "amLink": f"https://music.amazon.co.jp/search/{q}",
                        }
    except Exception as e:
        print("iTunes note:", e)

with open("tracks.json", "w", encoding="utf-8") as f:
    json.dump(tracks, f, ensure_ascii=False, indent=2)
print(f"Synced {len(tracks)} tracks into tracks.json")
