"""
Live bounty tables for Cavia (Sanctum Anatomica), the Holdfasts (Zariman),
and the Hex (Hollvania / 1999) - Streamlit version.

Sources:
  1. oracle.browse.wf/bounty-cycle -> current node + bonus challenge (+ ally)
  2. WFCD solNodes.json            -> node id -> node name + mission type

Run locally:   streamlit run bounties_app.py
"""

import datetime as dt
import time

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Warframe Bounties", page_icon="🎯", layout="wide")

ORACLE = "https://oracle.browse.wf/bounty-cycle"
NODES_URLS = [
    "https://raw.githubusercontent.com/WFCD/warframe-worldstate-data"
    "/master/data/solNodes.json",
    # mirror: same file, different CDN, separate rate limit
    "https://cdn.jsdelivr.net/gh/WFCD/warframe-worldstate-data@master"
    "/data/solNodes.json",
]
CETUS = "https://api.warframestat.us/pc/cetusCycle"
DICT_URLS = ["https://oracle.browse.wf/dicts/en.json"]

# Display timezone (the server runs in UTC).
try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("Asia/Jerusalem")
except Exception:  # missing tzdata: fall back to fixed IDT offset
    LOCAL_TZ = dt.timezone(dt.timedelta(hours=3), "IDT")

NO_CACHE = {
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "User-Agent": "bounty-check/1.0",
}

# ---------------------------------------------------------------- tier data
CAVIA_TIERS = [
    {"levels_sp": "155-160", "reward": "1,500 standing"},
    {"levels_sp": "165-170", "reward": "3,000 standing"},
    {"levels_sp": "175-180", "reward": "4,500 standing"},
    {"levels_sp": "195-200", "reward": "6,000 standing"},
    {"levels_sp": "215-220", "reward": "7,500 standing"},
]

# Zariman pays Voidplume Pinions, NOT standing.
ZARIMAN_TIERS = [
    {"levels_sp": "150-155", "reward": "2 Pinions"},
    {"levels_sp": "160-165", "reward": "3 Pinions"},
    {"levels_sp": "170-175", "reward": "5 Pinions"},
    {"levels_sp": "190-195", "reward": "6 Pinions"},
    {"levels_sp": "210-215", "reward": "8 Pinions"},
]

# Tier 7 is the Antivirus bounty (no ally); it breaks the flat +1,500 step.
HEX_TIERS = [
    {"levels_sp": "165-170", "reward": "1,500 standing"},
    {"levels_sp": "175-180", "reward": "3,000 standing"},
    {"levels_sp": "185-190", "reward": "4,500 standing"},
    {"levels_sp": "195-200", "reward": "6,000 standing"},
    {"levels_sp": "205-210", "reward": "7,500 standing"},
    {"levels_sp": "215-220", "reward": "9,000 standing"},
    {"levels_sp": "225-230", "reward": "11,250 standing"},
]

# Hollvania nodes (not in WFCD data). From the wiki's Hollvania mission table.
HEX_NODES = {
    "SolNode850": ("Kobinn West", "Legacyte Harvest"),
    "SolNode851": ("Mischta Ramparts", "Hell-Scrub"),
    "SolNode852": ("Old Konderuk", "Hell-Scrub"),
    "SolNode853": ("Mausoleum East", "Exterminate"),
    "SolNode854": ("Rhu Manor", "Exterminate"),
    "SolNode855": ("Lower Vehrvod", "Faceoff"),
    "SolNode856": ("Victory Plaza", "Assassination"),
    "SolNode857": ("Vehrvod District", "Faceoff"),
    "SolNode858": ("Solstice Square", "Stage Defense"),
}

SYNDICATES = {
    "Cavia (Sanctum Anatomica)": {
        "key": "EntratiLabSyndicate",
        "tiers": CAVIA_TIERS,
        "extra_nodes": {},
    },
    "Holdfasts (Zariman)": {
        "key": "ZarimanSyndicate",
        "tiers": ZARIMAN_TIERS,
        "extra_nodes": {},
    },
    "Hex (Hollvania / 1999)": {
        "key": "HexSyndicate",
        "tiers": HEX_TIERS,
        "extra_nodes": HEX_NODES,
    },
}

CHALLENGE_HINTS = {
    "entratilab": [
        ("destroydecoration", "Wrecking Crew: destroy 60 decorations"),
        ("killvoidrig", "Big Fish: eliminate 2 Rogue Voidrigs"),
        ("lootcrates", "Clean House: find 3 Murmur Sarcophages"),
        ("killmurmur", "Silence the Murmur: kill 100/150/200/250 Murmur"),
        ("lohksurge", "Tide of Lohk: activate 1/2/3 Lohk Surges"),
        ("rangedmechweakpoint", "Cull the Culverin: destroy 16/24/32/42 weak points"),
        ("alchemygrenadeelectric", "Shock Therapy: hit enemies with 6/12/18 Electric Amphors"),
        ("alchemygrenadefire", "Fire Storm: hit enemies with 6/12/18 Fire Amphors"),
        ("alchemygrenadecold", "Ice Death: hit enemies with 6/12/18 Cold Amphors"),
        ("alchemygrenadetoxin", "Poison Chalice: hit enemies with 6/12/18 Toxin Amphors"),
        ("summonnecramech", "A Loyal Necramech: summon a Necramech"),
        ("vitriol", "Chemistry Lesson: douse 30 enemies with Vitriol"),
        ("whisper", "Deadly Whispers: defeat the Mocking or Scathing Whisper"),
        ("flying", "Air Defence: kill 3 flying Murmur enemies"),
        ("demolisherlimb", "Dismantle Demolishers: destroy 3/5/8 Demolisher limbs"),
        ("conduit", "Anxious Activation: activate 2 Conduits in 30s"),
        ("murmureye", "Stare Down: collect 45 Murmur Eyes"),
        ("vosphene", "See No Evil: activate 1/2/3/4 defences"),
        ("docket", "Paranoia Protocol: Dockets vanish after 20s"),
    ],
    "vania": [
        ("destroyvehicles", "Demolition Derby: destroy 5 automobiles"),
        ("destroyspeakers", "Noise Pollution: destroy 10/20 speakers on Techrot Skuzzis"),
        ("safecracker", "Shell Cracker: find and open the Techrot cache"),
        ("destroyprops", "Break Cover: destroy 75 stationary items"),
        ("destroycontainers", "Hazardous Contents: destroy 2 Scaldra Efervon Containers"),
        ("killwithabilities", "Energy Overload: kill 40 enemies with abilities"),
        ("mercy", "Mercy kills: perform 8 Mercy kills"),
    ],
    "zariman": [
        ("accolade", "Boost Melica's Morale: take a Zarium Accolade to Melica"),
        ("melica", "Boost Melica's Morale: take a Zarium Accolade to Melica"),
        ("argozene", "Accumulate Argozene: collect 3/5/7/9 Argozene Canisters"),
        ("killasoperator", "Work without Warframes: kill 10/20/30/40 as Operator"),
        ("exodamper", "Protect Our Exodampers: kill 2/3 Angels, keep Exodampers intact"),
        ("vitoplastglobule", "Harvest Vitoplast Globules: collect 4/6/8/10 globules"),
        ("vitoplast", "Harvest Vitoplast Droplets: collect 75/100/200/300 Vitoplast"),
        ("sealrupture", "Repair the Ruptures: seal 6/9/12/15 Ruptures"),
        ("rupture", "Fight Void Flood Efficiently: close 3/6/9/12, meter below 70%"),
        ("armament", "Diversify Our Armaments: all Armament types active at once"),
        ("killgrineer", "Assault the Grineer: kill 100/150/200/250 Grineer"),
        ("killcorpus", "Repel the Corpus: kill 100/150/200/250 Corpus"),
        ("noability", "Weapons Only: complete without abilities"),
        ("shield", "Defend Console Shields: keep the target's shield intact"),
        ("lohk", "Steal New Strength: find and activate 1/2 Lohk surges"),
    ],
}


# ---------------------------------------------------------------- helpers
def prettify(path: str) -> str:
    """'/Lotus/.../EntratiLabKillMurmurEasyChallenge' -> 'Kill Murmur Easy'."""
    name = path.rsplit("/", 1)[-1]
    for prefix in ("EntratiLab", "LichVania", "Vania", "Zariman"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    for suffix in ("Challenge", "AllyAgent"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    out = []
    for ch in name:
        if ch.isupper() and out and not out[-1].isupper():
            out.append(" ")
        out.append(ch)
    return "".join(out).strip()


def fetch(url, **kwargs):
    r = requests.get(url, headers=NO_CACHE, timeout=30, **kwargs)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------- cached loaders
# st.cache_data replaces the solNodes.json disk cache: the result is kept in
# memory on the server, so page refreshes don't hit GitHub again.

@st.cache_data(ttl=24 * 3600, show_spinner=False)
def load_nodes():
    last_err = None
    for url in NODES_URLS:
        try:
            return fetch(url)
        except requests.RequestException as e:
            last_err = e
            continue  # rate limited / down: try the mirror
    raise RuntimeError(f"could not fetch node data from any source ({last_err})")


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def load_challenge_dict():
    for url in DICT_URLS:
        try:
            data = fetch(url)
        except Exception:
            continue
        if isinstance(data, dict) and data:
            return data
    return {}


@st.cache_data(ttl=60, show_spinner=False)
def load_feed():
    """Short TTL: refreshes at most once a minute, even if you spam F5."""
    feed = fetch(ORACLE, params={"_": int(time.time())})
    return feed, dt.datetime.now(dt.timezone.utc)


@st.cache_data(ttl=60, show_spinner=False)
def load_cetus():
    return fetch(CETUS)


def describe(path: str, cdict: dict) -> str:
    """Readable challenge text: dictionary desc if available, else hints, else prettify."""
    if cdict:
        base = path.rsplit("/", 1)[-1]
        for key in (path, path.lower(), base, base.lower()):
            entry = cdict.get(key)
            if entry is None:
                continue
            if isinstance(entry, str):
                return entry
            if isinstance(entry, dict):
                desc = entry.get("desc") or entry.get("description")
                name = entry.get("value") or entry.get("name")
                if desc and name:
                    return f"{name}: {desc}"
                if desc or name:
                    return desc or name
    low = path.lower()
    hints = []
    for prefix, entries in CHALLENGE_HINTS.items():
        if prefix in low:
            hints = entries
            break
    for needle, text in hints:
        if needle in low:
            text = text.split(": ", 1)[-1]
            for tag, suffix in (("veryhard", " [T4]"), ("hard", " [T3]"),
                                ("easy", " [T1]")):
                if tag in low:
                    return text + suffix
            return text
    return prettify(path)


def table(feed, nodes, spec, cdict):
    rows = []
    for i, b in enumerate(feed["bounties"][spec["key"]]):
        nid = b["node"]
        if nid in spec["extra_nodes"]:
            name, mtype = spec["extra_nodes"][nid]
        else:
            meta = nodes.get(nid, {})
            name = meta.get("value", nid).replace(" (Deimos)", "")
            mtype = meta.get("type", "?")

        tier = spec["tiers"][i] if i < len(spec["tiers"]) else {}
        row = {
            "tier": i + 1,
            "mission": mtype,
            "node": name,
            "bonus": describe(b["challenge"], cdict),
            "levels_sp": tier.get("levels_sp", "?"),
            "reward": tier.get("reward", "?"),
        }
        if "ally" in b:
            row["ally"] = prettify(b["ally"])
        rows.append(row)

    cols = ["tier", "mission", "node", "bonus", "levels_sp", "reward"]
    if any("ally" in r for r in rows):
        cols.append("ally")
        for r in rows:
            r.setdefault("ally", "")
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------- page
# Compact styling: less top padding, small tight tables that follow the
# light/dark theme (borders are semi-transparent grey).
st.markdown("""
<style>
.block-container {padding-top: 3rem; padding-bottom: 1rem;}
.bt-h {font-weight: 700; font-size: 0.95rem; margin: 0.3rem 0 0.15rem 0;}
.bt-status {font-size: 0.85rem; margin-bottom: 0.3rem;}
table.bt {width: 100%; border-collapse: collapse; font-size: 0.78rem;
          margin-bottom: 0.3rem; border: none;}
table.bt th, table.bt td {padding: 2px 6px; line-height: 1.25; text-align: left;
          vertical-align: top; white-space: nowrap; border: none;
          border-bottom: 1px solid rgba(128,128,128,0.25);}
table.bt th {font-weight: 600; opacity: 0.7;}
table.bt td:nth-child(4) {white-space: normal;}   /* bonus text may wrap */
table.bt td:nth-child(1), table.bt th:nth-child(1) {text-align: center;}
</style>
""", unsafe_allow_html=True)

COL_NAMES = {"tier": "T", "mission": "Mission", "node": "Node", "bonus": "Bonus",
             "levels_sp": "SP lvl", "reward": "Reward", "ally": "Ally"}

head, btn = st.columns([5, 1], vertical_alignment="center")
head.markdown("### 🎯 Warframe Bounties")
if btn.button("🔄 Refresh", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

now = dt.datetime.now(dt.timezone.utc)

# --- bounty feed
try:
    feed, fetched_at = load_feed()
except Exception as e:
    st.error(f"Could not load the bounty feed from oracle.browse.wf: {e}")
    st.stop()

expiry = dt.datetime.fromtimestamp(feed["expiry"] / 1000, dt.timezone.utc)
delta = expiry - now
parts = []
if delta.total_seconds() > 0:
    parts.append(f"🟢 <b>LIVE</b> {int(delta.total_seconds() // 60)} min left "
                 f"(rotates {expiry.astimezone(LOCAL_TZ):%H:%M})")
else:
    parts.append(f"🔴 <b>STALE</b> expired {int(-delta.total_seconds() // 60)} "
                 "min ago, press Refresh")

# --- Cetus
try:
    c = load_cetus()
    state = c.get("state") or ("day" if c.get("isDay") else "night")
    cexp = dt.datetime.fromisoformat(c["expiry"].replace("Z", "+00:00"))
    mins = int((cexp - now).total_seconds() // 60)
    nxt = "night" if state == "day" else "day"
    icon = "☀️" if state == "day" else "🌙"
    if mins >= 0:
        parts.append(f"{icon} Cetus <b>{state.upper()}</b> {mins} min to {nxt} "
                     f"({cexp.astimezone(LOCAL_TZ):%H:%M})")
    else:
        parts.append(f"{icon} Cetus outdated")
except Exception as e:
    parts.append(f"Cetus unavailable ({type(e).__name__})")

parts.append(f"<span style='opacity:.6'>rot {feed['rot']}/{feed['vaultRot']} · "
             f"fetched {fetched_at.astimezone(LOCAL_TZ):%H:%M}</span>")
st.markdown(f"<div class='bt-status'>{' &nbsp;·&nbsp; '.join(parts)}</div>",
            unsafe_allow_html=True)

# --- lookups
try:
    nodes = load_nodes()
except RuntimeError as e:
    st.warning(f"{e}. Node names and mission types will show as IDs.")
    nodes = {}
cdict = load_challenge_dict()
present = set(feed["bounties"].keys())


def render(label):
    spec = SYNDICATES[label]
    st.markdown(f"<div class='bt-h'>{label}</div>", unsafe_allow_html=True)
    if spec["key"] not in present:
        st.caption("(not present in this feed)")
        return
    df = table(feed, nodes, spec, cdict)
    if df.empty:
        st.caption("(no bounties in this feed)")
        return
    html = df.rename(columns=COL_NAMES).to_html(index=False, classes="bt", border=0)
    # strip newlines so markdown doesn't treat indented HTML as a code block
    st.markdown(html.replace("\n", ""), unsafe_allow_html=True)


# --- tables: Cavia + Zariman side by side (5 rows each), Hex full width.
# On a phone the two columns stack automatically.
left, right = st.columns(2)
with left:
    render("Cavia (Sanctum Anatomica)")
with right:
    render("Holdfasts (Zariman)")
render("Hex (Hollvania / 1999)")

# --- unmapped syndicates (new hub added to the feed?)
known = {s["key"] for s in SYNDICATES.values()}
unmapped = sorted(present - known)
if unmapped:
    with st.expander(f"⚠️ Feed has unmapped syndicate keys: {', '.join(unmapped)}"):
        for k in unmapped:
            st.write(f"**{k}**: {len(feed['bounties'][k])} entries")
            st.json(feed["bounties"][k][:2])
