import tkinter as tk
from tkinter import ttk, messagebox
import requests, threading, json, csv, os, time, math
from datetime import datetime
from collections import deque

# ═══════════════════════════════
#  DESIGN SYSTEM
# ═══════════════════════════════
BG          = "#07111C"
BG_SIDE     = "#0A1828"
BG_CARD     = "#0D1E30"
BG_C2       = "#112238"
BG_INPUT    = "#0A1828"
BG_DARK     = "#050E18"

BDR         = "#162840"
BDR_L       = "#1E3C5C"

GOLD        = "#F5C842"
GOLD_D      = "#C09818"
BLUE        = "#1E90FF"
BLUE_D      = "#1060CC"
TEAL        = "#00C8D4"
GREEN       = "#00D97E"
GREEN_D     = "#00A85E"
RED         = "#FF3348"
RED_D       = "#BB1130"
PURPLE      = "#8B6FE8"
ORANGE      = "#FF8A20"
AMBER       = "#FFB020"

TH          = "#EEF5FF"
TS          = "#7A96BC"
TM          = "#3A5470"
TD          = "#1A2E48"

# Coin display colors
COIN_COLORS = {
    "bitcoin":   GOLD,
    "ethereum":  PURPLE,
    "binancecoin": AMBER,
    "solana":    TEAL,
    "ripple":    BLUE,
    "cardano":   BLUE,
    "dogecoin":  AMBER,
    "polkadot":  PURPLE,
    "avalanche-2": RED,
    "chainlink": BLUE,
}

HISTORY_FILE   = "crypto_history.csv"
PORTFOLIO_FILE = "portfolio.json"
ALERTS_FILE    = "alerts.json"

DEFAULT_COINS = [
    "bitcoin","ethereum","binancecoin","solana","ripple",
    "cardano","dogecoin","polkadot","avalanche-2","chainlink",
]

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
HEADERS = {"User-Agent": "CryptoTracker/1.0", "Accept": "application/json"}


# ════════════════════════════════
#  API ENGINE
# ════════════════════════════════
class CoinGeckoAPI:


    TIMEOUT = 12

    # Cache coin list to avoid repeated requests
    _coin_list  = []
    _list_ts    = 0

    @classmethod
    def get_prices(cls, coin_ids: list) -> dict:

        ids = ",".join(coin_ids)
        url = (f"{COINGECKO_BASE}/simple/price"
               f"?ids={ids}"
               f"&vs_currencies=usd"
               f"&include_market_cap=true"
               f"&include_24hr_vol=true"
               f"&include_24hr_change=true"
               f"&include_last_updated_at=true")
        resp = requests.get(url, headers=HEADERS, timeout=cls.TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    @classmethod
    def get_coin_detail(cls, coin_id: str) -> dict:
        """Fetch detailed info for a single coin."""
        url = (f"{COINGECKO_BASE}/coins/{coin_id}"
               f"?localization=false&tickers=false"
               f"&market_data=true&community_data=false"
               f"&developer_data=false&sparkline=false")
        resp = requests.get(url, headers=HEADERS, timeout=cls.TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    @classmethod
    def search(cls, query: str) -> list:

        url = f"{COINGECKO_BASE}/search?query={query}"
        resp = requests.get(url, headers=HEADERS, timeout=cls.TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data.get("coins", [])[:15]

    @classmethod
    def get_markets(cls, coin_ids: list) -> list:

        ids = ",".join(coin_ids)
        url = (f"{COINGECKO_BASE}/coins/markets"
               f"?vs_currency=usd&ids={ids}"
               f"&order=market_cap_desc"
               f"&per_page=25&page=1"
               f"&sparkline=false"
               f"&price_change_percentage=24h")
        resp = requests.get(url, headers=HEADERS, timeout=cls.TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    @classmethod
    def get_history_chart(cls, coin_id: str, days: int = 7) -> dict:

        url = (f"{COINGECKO_BASE}/coins/{coin_id}/market_chart"
               f"?vs_currency=usd&days={days}&interval=daily")
        resp = requests.get(url, headers=HEADERS, timeout=cls.TIMEOUT)
        resp.raise_for_status()
        return resp.json()


# ═══════════════════════════════════════════════════════════════
#  DATA STORAGE
# ═══════════════════════════════════════════════════════════════
class DataStore:


    # ── History ──────────────────────────────────────────────
    @staticmethod
    def save_price(coin_id: str, name: str, price: float,
                   change_24h: float, market_cap: float):
        write_header = not os.path.exists(HISTORY_FILE)
        with open(HISTORY_FILE, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(["Timestamp","Coin ID","Name",
                             "Price (USD)","24h Change (%)","Market Cap"])
            w.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                coin_id, name, f"{price:.4f}",
                f"{change_24h:.2f}", f"{market_cap:.0f}",
            ])

    @staticmethod
    def load_history(coin_id: str = None) -> list:
        if not os.path.exists(HISTORY_FILE):
            return []
        try:
            with open(HISTORY_FILE, encoding="utf-8") as f:
                rows = list(csv.reader(f))
            if not rows: return []
            header = rows[0]; data = rows[1:]
            if coin_id:
                data = [r for r in data if len(r) > 1 and r[1] == coin_id]
            return data[-500:]  # last 500 entries
        except Exception:
            return []

    # ── Portfolio ─────────────────────────────────────────────
    @staticmethod
    def load_portfolio() -> dict:
        if not os.path.exists(PORTFOLIO_FILE):
            return {}
        try:
            with open(PORTFOLIO_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    @staticmethod
    def save_portfolio(data: dict):
        with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # ── Alerts ────────────────────────────────────────────────
    @staticmethod
    def load_alerts() -> list:
        if not os.path.exists(ALERTS_FILE):
            return []
        try:
            with open(ALERTS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    @staticmethod
    def save_alerts(data: list):
        with open(ALERTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════
def fmt_price(p):
    if p is None: return "—"
    if p >= 1000:  return f"${p:,.2f}"
    if p >= 1:     return f"${p:.4f}"
    return               f"${p:.8f}"

def fmt_large(n):
    if n is None: return "—"
    if n >= 1e12: return f"${n/1e12:.2f}T"
    if n >= 1e9:  return f"${n/1e9:.2f}B"
    if n >= 1e6:  return f"${n/1e6:.2f}M"
    return f"${n:,.0f}"

def change_color(v):
    if v is None: return TS
    return GREEN if v >= 0 else RED

def change_arrow(v):
    if v is None: return "—"
    arrow = "▲" if v >= 0 else "▼"
    return f"{arrow} {abs(v):.2f}%"

def lerp(c1, c2, t):
    t = max(0.0, min(1.0, t))
    r1,g1,b1 = int(c1[1:3],16),int(c1[3:5],16),int(c1[5:7],16)
    r2,g2,b2 = int(c2[1:3],16),int(c2[3:5],16),int(c2[5:7],16)
    return (f"#{int(r1+(r2-r1)*t):02x}"
            f"{int(g1+(g2-g1)*t):02x}"
            f"{int(b1+(b2-b1)*t):02x}")


# ═══════════════════════════════════════════════════════════════
#  WIDGETS
# ═══════════════════════════════════════════════════════════════
class SparkLine(tk.Canvas):

    def __init__(self, parent, color=GREEN, **kw):
        kw.setdefault("width", 120)
        kw.setdefault("height", 36)
        super().__init__(parent, bg=BG_CARD, highlightthickness=0, **kw)
        self._color = color
        self._data  = []

    def set_data(self, data: list, color=None):
        if color: self._color = color
        self._data = data
        self._draw()

    def _draw(self):
        self.delete("all")
        data = self._data
        if len(data) < 2: return
        W = self.winfo_width()  or int(self["width"])
        H = self.winfo_height() or int(self["height"])
        lo, hi = min(data), max(data)
        rng = (hi - lo) or 1
        pad = 4

        def _y(v): return H - pad - int((H - 2*pad) * (v-lo)/rng)
        def _x(i): return pad + int((W - 2*pad) * i / (len(data)-1))

        pts = []
        for i, v in enumerate(data):
            pts += [_x(i), _y(v)]

        # Fill
        fp = [_x(0), H] + pts + [_x(len(data)-1), H]
        self.create_polygon(*fp, fill=self._color, stipple="gray12", outline="")
        # Line
        if len(pts) >= 4:
            self.create_line(*pts, fill=self._color, width=1.8,
                             smooth=True, joinstyle="round")
        # End dot
        if pts:
            ex, ey = pts[-2], pts[-1]
            self.create_oval(ex-2, ey-2, ex+2, ey+2,
                             fill=self._color, outline=TH, width=1)


class MiniChart(tk.Canvas):
    PL, PR, PT, PB = 52, 16, 20, 28

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG_DARK, highlightthickness=0, **kw)
        self._prices = []
        self._labels = []
        self._coin   = ""
        self.bind("<Configure>", lambda e: self._draw())

    def set_data(self, prices: list, labels: list, coin: str):
        self._prices = prices
        self._labels = labels
        self._coin   = coin
        self._draw()

    def _draw(self):
        self.delete("all")
        W = self.winfo_width(); H = self.winfo_height()
        if W < 40 or H < 40 or len(self._prices) < 2: return
        pl,pr,pt,pb = self.PL,self.PR,self.PT,self.PB
        gw = W-pl-pr; gh = H-pt-pb
        prices = self._prices
        lo, hi = min(prices), max(prices)
        rng = (hi-lo) or 1

        def _y(v): return pt + gh - int(gh*(v-lo)/rng)
        def _x(i): return pl + int(gw*i/max(len(prices)-1,1))

        # Grid
        for p in range(0, 101, 25):
            v  = lo + rng*p/100
            y  = _y(v)
            self.create_line(pl, y, W-pr, y, fill=BDR, dash=(2,6))
            label = fmt_price(v).replace("$","")
            self.create_text(pl-4, y, text=label,
                             font=("Consolas",7), fill=TM, anchor="e")

        # Axes
        self.create_line(pl, pt-2, pl, pt+gh+1, fill=BDR_L)
        self.create_line(pl-1, pt+gh, W-pr, pt+gh, fill=BDR_L)

        # Area + line
        col = COIN_COLORS.get(self._coin, BLUE)
        pts = []
        for i,v in enumerate(prices):
            pts += [_x(i), _y(v)]

        fp = [_x(0), pt+gh] + pts + [_x(len(prices)-1), pt+gh]
        self.create_polygon(*fp, fill=col, stipple="gray12", outline="")
        self.create_line(*pts, fill=col, width=2.2,
                         smooth=True, joinstyle="round")

        # End dot
        ex, ey = pts[-2], pts[-1]
        self.create_oval(ex-4, ey-4, ex+4, ey+4, fill=col, outline=TH, width=1)

        # X labels
        n = len(self._labels)
        if n > 0:
            step = max(1, n//5)
            for i, lbl in enumerate(self._labels):
                if i % step == 0 or i == n-1:
                    self.create_text(_x(i), H-6, text=lbl,
                                     font=("Consolas",7), fill=TM)


def make_card(parent, accent=None, title=None, bg=BG_CARD):
    outer = tk.Frame(parent, bg=bg,
                     highlightbackground=BDR, highlightthickness=1)
    if accent:
        tk.Frame(outer, bg=accent, height=2).pack(fill="x")
    if title:
        hdr = tk.Frame(outer, bg=bg); hdr.pack(fill="x",padx=14,pady=(10,0))
        tk.Label(hdr, text=title, font=("Segoe UI",9,"bold"),
                 fg=TS, bg=bg).pack(side="left")
        tk.Frame(outer, bg=BDR, height=1).pack(fill="x",padx=14,pady=(6,0))
    inner = tk.Frame(outer, bg=bg); inner.pack(fill="both",expand=True)
    return outer, inner


def action_btn(parent, text, fg_color, bg_color, cmd, padx_=10):
    return tk.Button(parent, text=text, fg=fg_color, bg=bg_color,
                     font=("Segoe UI",9,"bold"), bd=0, pady=8,
                     padx=padx_, cursor="hand2", relief="flat",
                     activeforeground=TH, activebackground=bg_color,
                     command=cmd)


# ═══════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════
class App(tk.Tk):

    AUTO_REFRESH_SEC = 60   # default auto-refresh interval

    def __init__(self):
        super().__init__()
        self.title("Crypto Price Tracker")
        self.geometry("1220x760"); self.minsize(1050,650)
        self.configure(bg=BG)

        # State
        self._watchlist   = list(DEFAULT_COINS)
        self._prices      = {}           # coin_id -> market data dict
        self._portfolio   = DataStore.load_portfolio()
        self._alerts      = DataStore.load_alerts()
        self._price_hist  = {}           # coin_id -> deque of prices (for sparklines)
        self._run         = True
        self._refreshing  = False
        self._auto_on     = True
        self._page        = ""
        self._search_results = []

        # Load sparkline history from CSV
        for cid in self._watchlist:
            rows = DataStore.load_history(cid)
            prices = []
            for r in rows[-30:]:
                try: prices.append(float(r[3]))
                except: pass
            self._price_hist[cid] = deque(prices or [0.0], maxlen=50)

        self._build_topbar()
        self._build_body()

        self.protocol("WM_DELETE_WINDOW", self._quit)
        self._nav("prices")
        self._start_auto_refresh()
        self.after(200, self._refresh_prices)  # initial load

    # ── TOP BAR ────────────────────────────────────────────────
    def _build_topbar(self):
        bar = tk.Frame(self, bg=BG_SIDE, height=52)
        bar.pack(fill="x"); bar.pack_propagate(False)

        # Left: logo
        lf = tk.Frame(bar, bg=BG_SIDE); lf.pack(side="left", padx=(20,0))
        dot = tk.Canvas(lf, width=10, height=10, bg=BG_SIDE, highlightthickness=0)
        dot.pack(side="left", padx=(0,10))
        dot.create_oval(0,0,10,10, fill=GOLD, outline="")
        tk.Label(lf, text="Crypto Price Tracker",
                 font=("Consolas",13,"bold"), fg=TH, bg=BG_SIDE
                 ).pack(side="left")

        # Right: controls
        rf = tk.Frame(bar, bg=BG_SIDE); rf.pack(side="right", padx=20)

        # Status
        self._status_lbl = tk.Label(rf, text="",
                                    font=("Segoe UI",8), fg=TS, bg=BG_SIDE)
        self._status_lbl.pack(side="right", padx=(10,0))

        # Refresh btn
        action_btn(rf, " ⟳  Refresh", BG, BLUE,
                   self._manual_refresh, padx_=14
                   ).pack(side="right", padx=4)

        # Auto refresh toggle
        self._auto_btn = tk.Button(rf, text="Auto ON",
                                   font=("Segoe UI",8), fg=GREEN, bg=BG_SIDE,
                                   bd=0, cursor="hand2", relief="flat",
                                   activeforeground=TH, activebackground=BG_SIDE,
                                   command=self._toggle_auto)
        self._auto_btn.pack(side="right", padx=4)

        # Interval
        tk.Label(rf, text="Refresh:", font=("Segoe UI",8), fg=TM, bg=BG_SIDE
                 ).pack(side="right", padx=(10,2))
        self._interval_var = tk.StringVar(value="60")
        iv = ttk.Combobox(rf, textvariable=self._interval_var,
                          values=["30","60","120","300"],
                          width=4, font=("Consolas",9))
        iv.pack(side="right")
        iv.bind("<<ComboboxSelected>>", self._change_interval)

        # Clock
        self._clock = tk.StringVar()
        tk.Label(rf, textvariable=self._clock,
                 font=("Consolas",9), fg=TS, bg=BG_SIDE
                 ).pack(side="right", padx=(10,6))
        tk.Frame(rf, bg=BDR_L, width=1).pack(side="right", fill="y", pady=14, padx=6)

        tk.Frame(self, bg=BDR_L, height=1).pack(fill="x")
        self._tick_clock()

    def _tick_clock(self):
        self._clock.set(datetime.now().strftime("%a %d %b  %H:%M:%S"))
        self.after(1000, self._tick_clock)

    # ── BODY ───────────────────────────────────────────────────
    def _build_body(self):
        body = tk.Frame(self, bg=BG); body.pack(fill="both", expand=True)

        # Sidebar
        side = tk.Frame(body, bg=BG_SIDE, width=190)
        side.pack(side="left", fill="y"); side.pack_propagate(False)

        # Host
        self._host = tk.Frame(body, bg=BG)
        self._host.pack(side="left", fill="both", expand=True)

        self._build_sidebar(side)
        self._pages = {}
        self._pg_prices()
        self._pg_search()
        self._pg_portfolio()
        self._pg_alerts()
        self._pg_history()

    def _build_sidebar(self, side):
        tk.Frame(side, bg=BDR_L, height=1).pack(fill="x")
        tk.Label(side, text="MENU", font=("Segoe UI",7,"bold"),
                 fg=TD, bg=BG_SIDE).pack(anchor="w", padx=20, pady=(12,4))

        self._nav_btns = {}
        items = [
            ("prices",    "  Live Prices"),
            ("search",    "  Search Coin"),
            ("portfolio", "  Portfolio"),
            ("alerts",    "  Price Alerts"),
            ("history",   "  History"),
        ]
        for key, label in items:
            b = tk.Button(side, text=label, anchor="w",
                          font=("Segoe UI",10), fg=TS, bg=BG_SIDE,
                          activeforeground=GOLD, activebackground=BG_C2,
                          bd=0, pady=10, padx=20, cursor="hand2", relief="flat",
                          command=lambda k=key: self._nav(k))
            b.pack(fill="x"); self._nav_btns[key] = b

        tk.Frame(side, bg=BDR, height=1).pack(fill="x",padx=14,pady=10)
        tk.Label(side, text="WATCHLIST", font=("Segoe UI",7,"bold"),
                 fg=TD, bg=BG_SIDE).pack(anchor="w", padx=20, pady=(0,4))

        # Mini watchlist in sidebar
        self._side_prices_frame = tk.Frame(side, bg=BG_SIDE)
        self._side_prices_frame.pack(fill="x")
        self._side_labels = {}
        for cid in self._watchlist[:8]:
            row = tk.Frame(self._side_prices_frame, bg=BG_SIDE)
            row.pack(fill="x", padx=14, pady=2)
            col = COIN_COLORS.get(cid, BLUE)
            name_lbl = tk.Label(row, text=cid[:8].upper(),
                                font=("Consolas",7,"bold"), fg=col,
                                bg=BG_SIDE, width=8, anchor="w")
            name_lbl.pack(side="left")
            price_lbl = tk.Label(row, text="—",
                                 font=("Consolas",7), fg=TH,
                                 bg=BG_SIDE, anchor="e")
            price_lbl.pack(side="right")
            self._side_labels[cid] = price_lbl

        tk.Frame(side, bg=BG_SIDE).pack(fill="both", expand=True)
        tk.Frame(side, bg=BDR, height=1).pack(fill="x",padx=14)
        self._api_lbl = tk.Label(side, text="API: CoinGecko",
                                 font=("Segoe UI",7), fg=TD, bg=BG_SIDE)
        self._api_lbl.pack(pady=(4,10))

    # ── PAGE: LIVE PRICES ──────────────────────────────────────
    def _pg_prices(self):
        pg = tk.Frame(self._host, bg=BG)
        self._pages["prices"] = pg

        # Header
        hdr = tk.Frame(pg, bg=BG); hdr.pack(fill="x",padx=24,pady=(18,0))
        tk.Label(hdr, text="Live Prices",
                 font=("Consolas",16,"bold"), fg=TH, bg=BG).pack(side="left")
        self._price_ts = tk.Label(hdr, text="",
                                  font=("Segoe UI",8), fg=TM, bg=BG)
        self._price_ts.pack(side="right")

        # Loading label
        self._loading_lbl = tk.Label(pg, text="⟳  Fetching prices...",
                                     font=("Segoe UI",11), fg=TS, bg=BG)

        # ── Summary bar (top 3 stats)
        sum_row = tk.Frame(pg, bg=BG); sum_row.pack(fill="x",padx=24,pady=(10,4))
        self._sum_cards = {}
        for key,lbl,col in [
            ("btc_dom","BTC Dominance",GOLD),
            ("total_mc","Total Market Cap",BLUE),
            ("24h_vol","24h Volume",TEAL),
        ]:
            outer, inner = make_card(sum_row, accent=col)
            outer.pack(side="left", expand=True, fill="both", padx=4)
            vl = tk.Label(inner, text="—", font=("Consolas",14,"bold"),
                          fg=col, bg=BG_CARD)
            vl.pack(anchor="w", padx=12, pady=(8,0))
            tk.Label(inner, text=lbl, font=("Segoe UI",8),
                     fg=TS, bg=BG_CARD).pack(anchor="w",padx=12,pady=(0,8))
            self._sum_cards[key] = vl

        # ── Price table header
        th_row = tk.Frame(pg, bg=BG_C2)
        th_row.pack(fill="x", padx=24, pady=(8,0))
        cols = [
            ("#",      3),("Coin",     14),("Price",    12),
            ("24h %",  8),("Market Cap",12),("Volume",   12),("Trend",12),
        ]
        for lbl,w in cols:
            tk.Label(th_row, text=lbl, font=("Segoe UI",9,"bold"),
                     fg=TS, bg=BG_C2, width=w, anchor="w"
                     ).pack(side="left", padx=(8,0), pady=6)

        # ── Scrollable coin rows
        outer2, inner2 = make_card(pg, bg=BG_CARD)
        outer2.pack(fill="both", expand=True, padx=24, pady=(0,16))

        canv = tk.Canvas(inner2, bg=BG_CARD, highlightthickness=0)
        vsb  = ttk.Scrollbar(inner2, orient="vertical", command=canv.yview)
        canv.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canv.pack(side="left", fill="both", expand=True)

        self._price_frame = tk.Frame(canv, bg=BG_CARD)
        win = canv.create_window((0,0), window=self._price_frame, anchor="nw")
        canv.bind("<Configure>",
                  lambda e: canv.itemconfig(win, width=e.width))
        self._price_frame.bind("<Configure>",
                               lambda e: canv.configure(
                                   scrollregion=canv.bbox("all")))

        self._coin_rows = {}   # cid -> dict of label widgets

    def _build_coin_rows(self, market_data: list):

        # Clear existing
        for w in self._price_frame.winfo_children():
            w.destroy()
        self._coin_rows = {}

        style = ttk.Style(self)
        for i, coin in enumerate(market_data):
            cid  = coin.get("id","")
            col  = COIN_COLORS.get(cid, BLUE)
            bg   = BG_CARD if i%2==0 else BG_C2

            row = tk.Frame(self._price_frame, bg=bg, cursor="hand2")
            row.pack(fill="x")
            row.bind("<Button-1>", lambda e, c=cid: self._open_detail(c))

            price  = coin.get("current_price") or 0
            chg    = coin.get("price_change_percentage_24h")
            mcap   = coin.get("market_cap") or 0
            vol    = coin.get("total_volume") or 0
            symbol = coin.get("symbol","").upper()
            name   = coin.get("name","")

            # Rank
            tk.Label(row, text=f"#{i+1}", font=("Consolas",9),
                     fg=TM, bg=bg, width=3, anchor="w"
                     ).pack(side="left", padx=(10,0), pady=8)

            # Coin name + symbol
            nf = tk.Frame(row, bg=bg); nf.pack(side="left", padx=(6,0))
            tk.Label(nf, text=symbol, font=("Consolas",10,"bold"),
                     fg=col, bg=bg).pack(anchor="w")
            tk.Label(nf, text=name[:18], font=("Segoe UI",7),
                     fg=TM, bg=bg).pack(anchor="w")

            # Price
            pl = tk.Label(row, text=fmt_price(price),
                          font=("Consolas",11,"bold"), fg=TH, bg=bg, width=13, anchor="w")
            pl.pack(side="left", padx=(10,0))

            # 24h change
            cc = change_color(chg)
            cl = tk.Label(row, text=change_arrow(chg),
                          font=("Consolas",10,"bold"), fg=cc, bg=bg, width=9, anchor="w")
            cl.pack(side="left", padx=(6,0))

            # Market cap
            tk.Label(row, text=fmt_large(mcap),
                     font=("Consolas",9), fg=TS, bg=bg, width=13, anchor="w"
                     ).pack(side="left", padx=(6,0))

            # Volume
            tk.Label(row, text=fmt_large(vol),
                     font=("Consolas",9), fg=TS, bg=bg, width=13, anchor="w"
                     ).pack(side="left", padx=(6,0))

            # Sparkline
            sp = SparkLine(row, color=col, width=100, height=32)
            sp.pack(side="left", padx=(6,10), pady=4)
            hist = list(self._price_hist.get(cid, deque()))
            if hist: sp.set_data(hist, color=col)

            self._coin_rows[cid] = {
                "price_lbl": pl, "change_lbl": cl, "spark": sp, "bg": bg
            }

    def _update_coin_rows(self, market_data: list):
        for coin in market_data:
            cid   = coin.get("id","")
            if cid not in self._coin_rows: continue
            row   = self._coin_rows[cid]
            price = coin.get("current_price") or 0
            chg   = coin.get("price_change_percentage_24h")
            col   = COIN_COLORS.get(cid, BLUE)

            row["price_lbl"].config(text=fmt_price(price))
            row["change_lbl"].config(text=change_arrow(chg),
                                     fg=change_color(chg))
            hist = list(self._price_hist.get(cid, deque()))
            if hist: row["spark"].set_data(hist, color=col)

    # ── PAGE: SEARCH ────────────────────────────────────────────
    def _pg_search(self):
        pg = tk.Frame(self._host, bg=BG)
        self._pages["search"] = pg

        tk.Label(pg, text="Search Cryptocurrency",
                 font=("Consolas",15,"bold"), fg=TH, bg=BG
                 ).pack(anchor="w", padx=24, pady=(18,0))
        tk.Label(pg, text="Search by name or symbol (e.g. Bitcoin, ETH, SOL)",
                 font=("Segoe UI",9), fg=TS, bg=BG
                 ).pack(anchor="w", padx=24, pady=(2,12))

        # Search bar
        sb = tk.Frame(pg, bg=BG); sb.pack(fill="x", padx=24, pady=(0,14))
        self._search_var = tk.StringVar()
        ent = tk.Entry(sb, textvariable=self._search_var,
                       font=("Consolas",12), fg=TH, bg=BG_INPUT,
                       insertbackground=BLUE, relief="flat", bd=6)
        ent.pack(side="left", fill="x", expand=True, ipady=8)
        ent.bind("<Return>", lambda e: self._do_search())
        action_btn(sb, "  Search  ", BG, BLUE,
                   self._do_search, padx_=20).pack(side="left", padx=(8,0))
        action_btn(sb, "Clear", BG, BG_C2,
                   lambda: [self._search_var.set(""),
                            self._clear_search_results()],
                   padx_=10).pack(side="left", padx=(6,0))

        self._search_status = tk.Label(pg, text="",
                                       font=("Segoe UI",9), fg=TS, bg=BG)
        self._search_status.pack(anchor="w", padx=24)

        # Results
        outer, self._search_inner = make_card(pg, title="Search Results")
        outer.pack(fill="both", expand=True, padx=24, pady=(8,20))

        self._search_cols_hdr = tk.Frame(self._search_inner, bg=BG_C2)
        self._search_cols_hdr.pack(fill="x")
        for lbl,w in [("Rank",5),("Symbol",8),("Name",20),("Action",10)]:
            tk.Label(self._search_cols_hdr, text=lbl,
                     font=("Segoe UI",9,"bold"), fg=TS, bg=BG_C2,
                     width=w, anchor="w"
                     ).pack(side="left", padx=(10,0), pady=6)

        self._search_list = tk.Frame(self._search_inner, bg=BG_CARD)
        self._search_list.pack(fill="both", expand=True)

    def _do_search(self):
        q = self._search_var.get().strip()
        if not q:
            self._search_status.config(text="Please enter a search term.", fg=RED)
            return
        self._search_status.config(text="Searching...", fg=TS)
        threading.Thread(target=self._search_worker, args=(q,), daemon=True).start()

    def _search_worker(self, q):
        try:
            results = CoinGeckoAPI.search(q)
            self.after(0, lambda: self._show_search_results(results))
        except Exception as e:
            self.after(0, lambda: self._search_status.config(
                text=f"Error: {e}", fg=RED))

    def _show_search_results(self, results):
        self._clear_search_results()
        self._search_results = results
        if not results:
            self._search_status.config(text="No results found.", fg=AMBER)
            return
        self._search_status.config(text=f"Found {len(results)} results.", fg=GREEN)
        for i, coin in enumerate(results):
            bg = BG_CARD if i%2==0 else BG_C2
            row = tk.Frame(self._search_list, bg=bg)
            row.pack(fill="x")
            rank = coin.get("market_cap_rank") or "—"
            sym  = coin.get("symbol","").upper()
            name = coin.get("name","")
            cid  = coin.get("id","")

            tk.Label(row, text=f"#{rank}", font=("Consolas",9),
                     fg=TM, bg=bg, width=5, anchor="w"
                     ).pack(side="left", padx=(10,0), pady=8)
            tk.Label(row, text=sym, font=("Consolas",10,"bold"),
                     fg=GOLD, bg=bg, width=8, anchor="w"
                     ).pack(side="left", padx=(6,0))
            tk.Label(row, text=name, font=("Segoe UI",10),
                     fg=TH, bg=bg, width=24, anchor="w"
                     ).pack(side="left", padx=(6,0))

            already = cid in self._watchlist
            btn_txt = "✓ Watching" if already else "+ Add to Watchlist"
            btn_col = GREEN if already else BLUE
            action_btn(row, btn_txt, BG, btn_col,
                       lambda c=cid: self._add_to_watchlist(c)
                       ).pack(side="left", padx=8)

    def _clear_search_results(self):
        for w in self._search_list.winfo_children(): w.destroy()

    def _add_to_watchlist(self, coin_id: str):
        if coin_id not in self._watchlist:
            self._watchlist.append(coin_id)
            self._price_hist[coin_id] = deque(maxlen=50)
            messagebox.showinfo("Added",
                f"'{coin_id}' added to watchlist.\nIt will appear on next refresh.",
                parent=self)
            self._do_search()  # refresh search to show ✓

    # ── PAGE: PORTFOLIO ─────────────────────────────────────────
    def _pg_portfolio(self):
        pg = tk.Frame(self._host, bg=BG)
        self._pages["portfolio"] = pg

        tk.Label(pg, text="Portfolio Tracker",
                 font=("Consolas",15,"bold"), fg=TH, bg=BG
                 ).pack(anchor="w", padx=24, pady=(18,2))
        tk.Label(pg, text="Track your holdings and see current value.",
                 font=("Segoe UI",9), fg=TS, bg=BG
                 ).pack(anchor="w", padx=24, pady=(0,10))

        # Add holding form
        outer_f, form = make_card(pg, accent=GOLD, title="Add / Update Holding")
        outer_f.pack(fill="x", padx=24, pady=(0,10))

        fr1 = tk.Frame(form, bg=BG_CARD); fr1.pack(fill="x",padx=14,pady=(10,4))
        for lbl,var_name in [("Coin ID (e.g. bitcoin)","_pf_coin"),
                              ("Amount Held","_pf_amt"),
                              ("Buy Price (USD)","_pf_buy")]:
            col = tk.Frame(fr1, bg=BG_CARD); col.pack(side="left",expand=True,padx=6)
            tk.Label(col, text=lbl, font=("Segoe UI",8), fg=TS, bg=BG_CARD
                     ).pack(anchor="w")
            var = tk.StringVar(); setattr(self, var_name, var)
            e = tk.Entry(col, textvariable=var, font=("Consolas",10),
                         fg=TH, bg=BG_INPUT, insertbackground=BLUE,
                         relief="flat", bd=4)
            e.pack(fill="x", ipady=5)

        bf = tk.Frame(form, bg=BG_CARD); bf.pack(fill="x",padx=14,pady=(4,12))
        action_btn(bf," + Add / Update ",BG,GOLD,self._add_portfolio).pack(side="left",padx=(0,8))
        action_btn(bf," Remove Selected ",BG,RED,self._remove_portfolio).pack(side="left")

        # Portfolio table
        outer_t, inner_t = make_card(pg, title="Holdings")
        outer_t.pack(fill="both", expand=True, padx=24, pady=(0,16))

        th = tk.Frame(inner_t, bg=BG_C2); th.pack(fill="x")
        for lbl,w in [("Coin",14),("Amount",10),("Buy Price",12),
                      ("Current Price",13),("Value",12),("P/L",10),("P/L %",8)]:
            tk.Label(th, text=lbl, font=("Segoe UI",9,"bold"),
                     fg=TS, bg=BG_C2, width=w, anchor="w"
                     ).pack(side="left",padx=(10,0),pady=6)

        self._pf_list = tk.Frame(inner_t, bg=BG_CARD)
        self._pf_list.pack(fill="both", expand=True)

        self._pf_total_row = tk.Frame(inner_t, bg=BG_C2)
        self._pf_total_row.pack(fill="x")
        self._pf_total_lbl = tk.Label(self._pf_total_row, text="",
                                      font=("Consolas",11,"bold"), fg=GOLD,
                                      bg=BG_C2)
        self._pf_total_lbl.pack(side="right", padx=14, pady=8)

        self._selected_pf_coin = None
        self._refresh_portfolio_ui()

    def _add_portfolio(self):
        cid = self._pf_coin.get().strip().lower()
        amt = self._pf_amt.get().strip()
        buy = self._pf_buy.get().strip()
        if not cid or not amt:
            messagebox.showwarning("Input Error","Coin ID and Amount are required.",parent=self)
            return
        try:
            amt_f = float(amt)
            buy_f = float(buy) if buy else 0.0
        except ValueError:
            messagebox.showwarning("Input Error","Amount and Buy Price must be numbers.",parent=self)
            return
        self._portfolio[cid] = {"amount": amt_f, "buy_price": buy_f}
        DataStore.save_portfolio(self._portfolio)
        if cid not in self._watchlist:
            self._watchlist.append(cid)
            self._price_hist[cid] = deque(maxlen=50)
        self._pf_coin.set(""); self._pf_amt.set(""); self._pf_buy.set("")
        self._refresh_portfolio_ui()
        messagebox.showinfo("Saved", f"'{cid}' added to portfolio.", parent=self)

    def _remove_portfolio(self):
        if not self._selected_pf_coin:
            messagebox.showinfo("Select","Click a row first to select it.",parent=self)
            return
        cid = self._selected_pf_coin
        if messagebox.askyesno("Remove",f"Remove '{cid}' from portfolio?",parent=self):
            self._portfolio.pop(cid, None)
            DataStore.save_portfolio(self._portfolio)
            self._selected_pf_coin = None
            self._refresh_portfolio_ui()

    def _refresh_portfolio_ui(self):
        for w in self._pf_list.winfo_children(): w.destroy()
        total_val = 0.0
        for i, (cid, holding) in enumerate(self._portfolio.items()):
            bg = BG_CARD if i%2==0 else BG_C2
            amt     = holding.get("amount",0)
            buy_p   = holding.get("buy_price",0)
            cur_p   = (self._prices.get(cid,{}).get("usd") or 0)
            cur_val = amt * cur_p
            cost    = amt * buy_p
            pl      = cur_val - cost
            pl_pct  = (pl/cost*100) if cost else 0
            total_val += cur_val

            row = tk.Frame(self._pf_list, bg=bg, cursor="hand2")
            row.pack(fill="x")
            row.bind("<Button-1>", lambda e, c=cid: self._select_pf_row(c))

            col = COIN_COLORS.get(cid, BLUE)
            for text, width, fg in [
                (cid.upper()[:12], 14, col),
                (f"{amt:,.4f}",    10, TH),
                (fmt_price(buy_p), 12, TS),
                (fmt_price(cur_p), 13, TH),
                (fmt_large(cur_val),12, TH),
                (fmt_large(pl),    10, GREEN if pl>=0 else RED),
                (f"{pl_pct:+.1f}%", 8, GREEN if pl>=0 else RED),
            ]:
                tk.Label(row, text=text, font=("Consolas",9),
                         fg=fg, bg=bg, width=width, anchor="w"
                         ).pack(side="left",padx=(10,0),pady=7)

        self._pf_total_lbl.config(
            text=f"Total Portfolio Value:  {fmt_large(total_val)}")

    def _select_pf_row(self, cid):
        self._selected_pf_coin = cid
        self._pf_coin.set(cid)
        h = self._portfolio.get(cid,{})
        self._pf_amt.set(str(h.get("amount","")))
        self._pf_buy.set(str(h.get("buy_price","")))

    # ── PAGE: ALERTS ────────────────────────────────────────────
    def _pg_alerts(self):
        pg = tk.Frame(self._host, bg=BG)
        self._pages["alerts"] = pg

        tk.Label(pg, text="Price Alerts",
                 font=("Consolas",15,"bold"), fg=TH, bg=BG
                 ).pack(anchor="w", padx=24, pady=(18,2))
        tk.Label(pg, text="Get notified when a coin crosses your target price.",
                 font=("Segoe UI",9), fg=TS, bg=BG
                 ).pack(anchor="w", padx=24, pady=(0,10))

        # Add alert
        outer_a, form_a = make_card(pg, accent=AMBER, title="Set New Alert")
        outer_a.pack(fill="x", padx=24, pady=(0,10))

        fr = tk.Frame(form_a, bg=BG_CARD); fr.pack(fill="x",padx=14,pady=(10,4))
        fields = [("Coin ID","_al_coin"),("Target Price (USD)","_al_price")]
        for lbl,var_name in fields:
            col = tk.Frame(fr, bg=BG_CARD); col.pack(side="left",expand=True,padx=6)
            tk.Label(col, text=lbl, font=("Segoe UI",8), fg=TS, bg=BG_CARD
                     ).pack(anchor="w")
            var = tk.StringVar(); setattr(self, var_name, var)
            tk.Entry(col, textvariable=var, font=("Consolas",10),
                     fg=TH, bg=BG_INPUT, insertbackground=BLUE,
                     relief="flat", bd=4
                     ).pack(fill="x",ipady=5)

        # Direction
        dir_f = tk.Frame(fr, bg=BG_CARD); dir_f.pack(side="left",expand=True,padx=6)
        tk.Label(dir_f, text="Direction", font=("Segoe UI",8),
                 fg=TS, bg=BG_CARD).pack(anchor="w")
        self._al_dir = tk.StringVar(value="above")
        for val,txt in [("above","Price goes ABOVE ▲"),("below","Price goes BELOW ▼")]:
            tk.Radiobutton(dir_f, text=txt, variable=self._al_dir, value=val,
                           font=("Segoe UI",9), fg=TH, bg=BG_CARD,
                           selectcolor=BG_DARK, activebackground=BG_CARD,
                           activeforeground=TH).pack(anchor="w")

        bf_a = tk.Frame(form_a, bg=BG_CARD); bf_a.pack(fill="x",padx=14,pady=(4,12))
        action_btn(bf_a," + Add Alert ",BG,AMBER,self._add_alert).pack(side="left",padx=(0,8))
        action_btn(bf_a," Remove Selected ",BG,RED,self._remove_alert).pack(side="left")

        # Alert table
        outer_t, inner_t = make_card(pg, title="Active Alerts")
        outer_t.pack(fill="both", expand=True, padx=24, pady=(0,16))

        th = tk.Frame(inner_t, bg=BG_C2); th.pack(fill="x")
        for lbl,w in [("Coin",14),("Target Price",14),
                      ("Direction",10),("Status",10),("Current Price",14)]:
            tk.Label(th, text=lbl, font=("Segoe UI",9,"bold"),
                     fg=TS, bg=BG_C2, width=w, anchor="w"
                     ).pack(side="left",padx=(10,0),pady=6)

        self._alert_list = tk.Frame(inner_t, bg=BG_CARD)
        self._alert_list.pack(fill="both",expand=True)
        self._selected_alert_idx = None
        self._refresh_alerts_ui()

    def _add_alert(self):
        cid   = self._al_coin.get().strip().lower()
        price = self._al_price.get().strip()
        direc = self._al_dir.get()
        if not cid or not price:
            messagebox.showwarning("Input","Coin ID and Target Price required.",parent=self)
            return
        try: price_f = float(price)
        except ValueError:
            messagebox.showwarning("Input","Price must be a number.",parent=self)
            return
        self._alerts.append({
            "coin":      cid,
            "target":    price_f,
            "direction": direc,
            "triggered": False,
            "created":   datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        DataStore.save_alerts(self._alerts)
        self._al_coin.set(""); self._al_price.set("")
        self._refresh_alerts_ui()

    def _remove_alert(self):
        if self._selected_alert_idx is None:
            messagebox.showinfo("Select","Click a row first.",parent=self)
            return
        idx = self._selected_alert_idx
        if 0 <= idx < len(self._alerts):
            self._alerts.pop(idx)
            DataStore.save_alerts(self._alerts)
            self._selected_alert_idx = None
            self._refresh_alerts_ui()

    def _refresh_alerts_ui(self):
        for w in self._alert_list.winfo_children(): w.destroy()
        for i, alert in enumerate(self._alerts):
            bg    = BG_CARD if i%2==0 else BG_C2
            cid   = alert.get("coin","")
            tgt   = alert.get("target",0)
            direc = alert.get("direction","above")
            trig  = alert.get("triggered",False)
            cur   = self._prices.get(cid,{}).get("usd") or 0

            status_txt = "✓ Triggered" if trig else "Watching"
            status_col = GREEN if trig else AMBER

            row = tk.Frame(self._alert_list, bg=bg, cursor="hand2")
            row.pack(fill="x")
            row.bind("<Button-1>", lambda e, ix=i: setattr(self,"_selected_alert_idx",ix))

            col = COIN_COLORS.get(cid, BLUE)
            for text,width,fg in [
                (cid.upper()[:12], 14, col),
                (fmt_price(tgt),   14, GOLD),
                (("▲ Above" if direc=="above" else "▼ Below"), 10, TH),
                (status_txt,       10, status_col),
                (fmt_price(cur),   14, TH),
            ]:
                tk.Label(row, text=text, font=("Consolas",9),
                         fg=fg, bg=bg, width=width, anchor="w"
                         ).pack(side="left",padx=(10,0),pady=7)

    # ── PAGE: HISTORY ───────────────────────────────────────────
    def _pg_history(self):
        pg = tk.Frame(self._host, bg=BG)
        self._pages["history"] = pg

        hdr = tk.Frame(pg, bg=BG); hdr.pack(fill="x",padx=24,pady=(18,8))
        tk.Label(hdr, text="Price History",
                 font=("Consolas",15,"bold"), fg=TH, bg=BG).pack(side="left")

        # Filter
        ff = tk.Frame(hdr, bg=BG); ff.pack(side="right")
        tk.Label(ff, text="Filter coin:", font=("Segoe UI",9), fg=TS, bg=BG
                 ).pack(side="left", padx=(0,6))
        self._hist_filter = tk.StringVar(value="all")
        opts = ["all"] + self._watchlist[:12]
        cb = ttk.Combobox(ff, textvariable=self._hist_filter,
                          values=opts, width=16, font=("Consolas",9))
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_history_ui())
        action_btn(ff,"⟳ Refresh",BG,BLUE,self._refresh_history_ui
                   ).pack(side="left",padx=8)

        # 7-day chart
        outer_c, inner_c = make_card(pg, accent=BLUE, title="7-Day Price Chart")
        outer_c.pack(fill="x", padx=24, pady=(0,8))

        # Coin selector for chart
        csf = tk.Frame(inner_c, bg=BG_CARD); csf.pack(fill="x",padx=14,pady=(8,4))
        tk.Label(csf, text="Show chart for:", font=("Segoe UI",8), fg=TS, bg=BG_CARD
                 ).pack(side="left",padx=(0,8))
        self._chart_coin = tk.StringVar(value=self._watchlist[0])
        cc = ttk.Combobox(csf, textvariable=self._chart_coin,
                          values=self._watchlist, width=20, font=("Consolas",9))
        cc.pack(side="left")
        action_btn(csf," Load Chart ",BG,TEAL,self._load_chart
                   ).pack(side="left",padx=8)
        self._chart_status = tk.Label(csf, text="", font=("Segoe UI",8),
                                      fg=TS, bg=BG_CARD)
        self._chart_status.pack(side="left",padx=8)

        self._mini_chart = MiniChart(inner_c, height=200)
        self._mini_chart.pack(fill="x",padx=2,pady=(0,8))

        # Log table
        outer_t, inner_t = make_card(pg, title="Saved History Log")
        outer_t.pack(fill="both", expand=True, padx=24, pady=(0,16))

        th_row = tk.Frame(inner_t, bg=BG_C2); th_row.pack(fill="x")
        for lbl,w in [("Timestamp",20),("Coin",14),("Name",16),
                      ("Price (USD)",13),("24h Change",11),("Market Cap",14)]:
            tk.Label(th_row, text=lbl, font=("Segoe UI",9,"bold"),
                     fg=TS, bg=BG_C2, width=w, anchor="w"
                     ).pack(side="left",padx=(10,0),pady=6)

        canv = tk.Canvas(inner_t, bg=BG_CARD, highlightthickness=0)
        vsb  = ttk.Scrollbar(inner_t, orient="vertical", command=canv.yview)
        canv.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right",fill="y")
        canv.pack(side="left",fill="both",expand=True)
        self._hist_frame = tk.Frame(canv, bg=BG_CARD)
        win = canv.create_window((0,0),window=self._hist_frame,anchor="nw")
        canv.bind("<Configure>", lambda e: canv.itemconfig(win,width=e.width))
        self._hist_frame.bind("<Configure>",
                              lambda e: canv.configure(scrollregion=canv.bbox("all")))
        self._refresh_history_ui()

    def _refresh_history_ui(self):
        for w in self._hist_frame.winfo_children(): w.destroy()
        filt = self._hist_filter.get()
        rows = DataStore.load_history(None if filt=="all" else filt)
        if not rows:
            tk.Label(self._hist_frame, text="No history saved yet.",
                     font=("Segoe UI",10), fg=TM, bg=BG_CARD
                     ).pack(pady=20)
            return
        for i, row in enumerate(reversed(rows[-200:])):
            bg = BG_CARD if i%2==0 else BG_C2
            r  = tk.Frame(self._hist_frame, bg=bg); r.pack(fill="x")
            col = COIN_COLORS.get(row[1] if len(row)>1 else "", BLUE)
            vals = [row[0] if len(row)>0 else ""]
            vals += row[1:6] if len(row)>=6 else row[1:]
            widths = [20,14,16,13,11,14]
            for j,(v,w) in enumerate(zip(vals, widths)):
                fg = col if j==1 else (
                    GREEN if j==4 and v.startswith("-")==False and v not in ("","—")
                    else RED if j==4 else TH if j<2 else TS)
                tk.Label(r, text=v[:20], font=("Consolas",8),
                         fg=fg, bg=bg, width=w, anchor="w"
                         ).pack(side="left",padx=(10,0),pady=6)

    def _load_chart(self):
        cid = self._chart_coin.get().strip()
        if not cid: return
        self._chart_status.config(text="Loading...", fg=TS)
        threading.Thread(target=self._chart_worker, args=(cid,), daemon=True).start()

    def _chart_worker(self, cid):
        try:
            data  = CoinGeckoAPI.get_history_chart(cid, days=7)
            prices= [p[1] for p in data.get("prices",[])]
            times = [datetime.fromtimestamp(p[0]/1000).strftime("%m/%d")
                     for p in data.get("prices",[])]
            self.after(0, lambda: self._show_chart(prices, times, cid))
        except Exception as e:
            self.after(0, lambda: self._chart_status.config(
                text=f"Error: {e}", fg=RED))

    def _show_chart(self, prices, labels, cid):
        self._mini_chart.set_data(prices, labels, cid)
        self._chart_status.config(text=f"✓ {cid.title()} · 7 days", fg=GREEN)

    # ── DETAIL POPUP ────────────────────────────────────────────
    def _open_detail(self, coin_id: str):
        info = self._prices.get(coin_id,{})
        if not info: return
        w = tk.Toplevel(self)
        w.title(f"{coin_id.title()} — Detail")
        w.geometry("440x340"); w.configure(bg=BG); w.resizable(False,False)

        col = COIN_COLORS.get(coin_id, BLUE)
        tk.Frame(w, bg=col, height=3).pack(fill="x")
        tk.Label(w, text=coin_id.upper(),
                 font=("Consolas",18,"bold"), fg=col, bg=BG
                 ).pack(anchor="w",padx=24,pady=(14,0))

        price  = info.get("usd") or 0
        chg    = info.get("usd_24h_change")
        mcap   = info.get("usd_market_cap")
        vol    = info.get("usd_24h_vol")

        tk.Label(w, text=fmt_price(price),
                 font=("Consolas",28,"bold"), fg=TH, bg=BG
                 ).pack(anchor="w",padx=24)
        tk.Label(w, text=change_arrow(chg),
                 font=("Consolas",14,"bold"), fg=change_color(chg), bg=BG
                 ).pack(anchor="w",padx=24)

        grid = tk.Frame(w, bg=BG_CARD,highlightbackground=BDR,highlightthickness=1)
        grid.pack(fill="x",padx=24,pady=14)
        for lbl,val in [
            ("Market Cap",   fmt_large(mcap)),
            ("24h Volume",   fmt_large(vol)),
            ("Last Updated", datetime.now().strftime("%H:%M:%S")),
        ]:
            r=tk.Frame(grid,bg=BG_CARD); r.pack(fill="x",padx=14,pady=5)
            tk.Label(r,text=lbl,font=("Segoe UI",9),fg=TS,bg=BG_CARD,width=16,anchor="w").pack(side="left")
            tk.Label(r,text=val,font=("Consolas",10,"bold"),fg=TH,bg=BG_CARD).pack(side="left")

        action_btn(w,"  Close  ",BG,BDR_L,w.destroy).pack(pady=(0,16))

    # ── NAVIGATION ─────────────────────────────────────────────
    def _nav(self, key):
        for f in self._pages.values(): f.pack_forget()
        self._pages[key].pack(fill="both", expand=True)
        for n,b in self._nav_btns.items():
            b.config(fg=GOLD if n==key else TS,
                     bg=BG_C2 if n==key else BG_SIDE,
                     font=("Segoe UI",10,"bold" if n==key else "normal"))
        self._page = key
        if key == "portfolio":   self._refresh_portfolio_ui()
        elif key == "alerts":    self._refresh_alerts_ui()
        elif key == "history":   self._refresh_history_ui()

    # ── PRICE REFRESH ENGINE ───────────────────────────────────
    def _refresh_prices(self):
        if self._refreshing: return
        self._refreshing = True
        self._status_lbl.config(text="⟳ Fetching...", fg=AMBER)
        self._loading_lbl.pack(pady=20)
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self):
        try:
            market = CoinGeckoAPI.get_markets(self._watchlist)
            # Also get simple prices for alerts/portfolio lookup
            prices = CoinGeckoAPI.get_prices(self._watchlist)
            self.after(0, lambda: self._apply_prices(market, prices))
        except requests.exceptions.ConnectionError:
            self.after(0, lambda: self._fetch_error("No internet connection."))
        except requests.exceptions.Timeout:
            self.after(0, lambda: self._fetch_error("Request timed out."))
        except requests.exceptions.HTTPError as e:
            self.after(0, lambda: self._fetch_error(f"API error: {e}"))
        except Exception as e:
            self.after(0, lambda: self._fetch_error(str(e)))

    def _apply_prices(self, market: list, prices: dict):
        self._loading_lbl.pack_forget()
        self._refreshing = False
        ts = datetime.now().strftime("%H:%M:%S")
        self._prices = prices
        self._price_ts.config(text=f"Updated: {ts}")
        self._status_lbl.config(text=f"✓ Updated {ts}", fg=GREEN)

        # Update sparkline history
        for coin in market:
            cid = coin.get("id","")
            p   = coin.get("current_price") or 0
            if cid not in self._price_hist:
                self._price_hist[cid] = deque(maxlen=50)
            self._price_hist[cid].append(p)
            # Save to CSV history
            DataStore.save_price(
                cid,
                coin.get("name",""),
                p,
                coin.get("price_change_percentage_24h") or 0,
                coin.get("market_cap") or 0
            )

        # Rebuild or update price table
        if self._coin_rows:
            self._update_coin_rows(market)
        else:
            self._build_coin_rows(market)

        # Update sidebar mini prices
        for cid, lbl in self._side_labels.items():
            p = prices.get(cid,{}).get("usd")
            if p: lbl.config(text=fmt_price(p))

        # Summary stats (aggregate from market data)
        total_mc  = sum(c.get("market_cap",0) or 0 for c in market)
        total_vol = sum(c.get("total_volume",0) or 0 for c in market)
        btc_mc    = next((c.get("market_cap",0) or 0
                          for c in market if c.get("id")=="bitcoin"), 0)
        btc_dom   = (btc_mc/total_mc*100) if total_mc else 0
        self._sum_cards["btc_dom"].config(text=f"{btc_dom:.1f}%")
        self._sum_cards["total_mc"].config(text=fmt_large(total_mc))
        self._sum_cards["24h_vol"].config(text=fmt_large(total_vol))

        # Check alerts
        self._check_alerts()
        # Refresh portfolio UI if visible
        if self._page == "portfolio": self._refresh_portfolio_ui()
        if self._page == "alerts":    self._refresh_alerts_ui()

    def _fetch_error(self, msg: str):
        self._loading_lbl.pack_forget()
        self._refreshing = False
        self._status_lbl.config(text=f"✗ {msg}", fg=RED)

    def _check_alerts(self):
        fired = False
        for alert in self._alerts:
            if alert.get("triggered"): continue
            cid   = alert.get("coin","")
            tgt   = alert.get("target",0)
            direc = alert.get("direction","above")
            cur   = self._prices.get(cid,{}).get("usd") or 0
            if cur == 0: continue
            hit = (direc=="above" and cur >= tgt) or (direc=="below" and cur <= tgt)
            if hit:
                alert["triggered"] = True
                fired = True
                messagebox.showwarning(
                    "Price Alert!",
                    f" ALERT TRIGGERED!\n\n"
                    f"Coin:   {cid.upper()}\n"
                    f"Price:  {fmt_price(cur)}\n"
                    f"Target: {fmt_price(tgt)} ({direc})",
                    parent=self
                )
        if fired:
            DataStore.save_alerts(self._alerts)
            if self._page == "alerts": self._refresh_alerts_ui()

    # ── AUTO REFRESH ───────────────────────────────────────────
    def _start_auto_refresh(self):
        interval = int(self._interval_var.get()) * 1000
        if self._auto_on and self._run:
            self.after(interval, self._auto_tick)

    def _auto_tick(self):
        if not self._run: return
        if self._auto_on:
            self._refresh_prices()
        interval = int(self._interval_var.get()) * 1000
        self.after(interval, self._auto_tick)

    def _manual_refresh(self):
        self._refresh_prices()

    def _toggle_auto(self):
        self._auto_on = not self._auto_on
        self._auto_btn.config(
            text="Auto ON" if self._auto_on else "Auto OFF",
            fg=GREEN if self._auto_on else RED)

    def _change_interval(self, _=None):
        pass  # interval is read directly from combobox each tick

    def _quit(self):
        self._run = False
        self.after(80, self.destroy)


# ═══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # Style ttk
    root = App()
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TScrollbar",
                    background=BG_C2, troughcolor=BG_DARK,
                    arrowcolor=TS, relief="flat")
    style.configure("TCombobox",
                    fieldbackground=BG_INPUT, background=BG_CARD,
                    foreground=TH, selectbackground=BDR_L,
                    arrowcolor=TS)
    root.mainloop()