"""
Product Availability Tracker - Final Version
Monitors Apple products across Amazon India, Reliance Digital, and JioMart.
Sends WhatsApp alerts (via WhatsApp Web) on ANY stock change:
  - Goes IN stock  → 🚨 hype alert with direct link
  - Goes OUT stock → 📉 quiet informational update

PAUSE / RESUME:
  1. Press F9 (needs: pip install keyboard)
  2. Or create/delete "pause.flag" in the script folder

FIRST-TIME SETUP:
  1. Set BOT_CHROME_PROFILE_DIR below to a new, empty folder.
  2. Run:  chrome.exe --user-data-dir="<that folder>"
  3. In that Chrome window, log in to Amazon, Reliance, JioMart, WhatsApp Web.
  4. Close Chrome. From then on the script reuses that profile.
"""

import time
import logging
import os
import re
import sys
import io
import subprocess
from datetime import datetime
from typing import Dict, List, Tuple, Optional

import pyautogui
import pyperclip
import winsound

try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False

# ==================== CONFIGURATION ====================

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BOT_CHROME_PROFILE_DIR = r"C:\ChromeBotProfile"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PAUSE_FLAG_FILE = os.path.join(SCRIPT_DIR, "pause.flag")

PRODUCTS = [
    # ---- Amazon: MacBook Air M5 ----
    {"name": "MacBook Air M5 512GB (ASIN B0GR1JFTPR)", "group": "MacBook Air M5 512GB",
     "url": "https://www.amazon.in/dp/B0GR1JFTPR", "site": "amazon",
     "expect": ["512"], "conflict": ["1 tb", "1tb", "256 gb", "256gb"]},
    {"name": "MacBook Air M5 512GB (ASIN B0GR1HPR1W)", "group": "MacBook Air M5 512GB",
     "url": "https://www.amazon.in/dp/B0GR1HPR1W", "site": "amazon",
     "expect": ["512"], "conflict": ["1 tb", "1tb", "256 gb", "256gb"]},
    {"name": "MacBook Air M5 512GB (ASIN B0GR1RQ144)", "group": "MacBook Air M5 512GB",
     "url": "https://www.amazon.in/dp/B0GR1RQ144", "site": "amazon",
     "expect": ["512"], "conflict": ["1 tb", "1tb", "256 gb", "256gb"]},

    
]

WHATSAPP_CONTACTS = [
    {"name": "Sandeep Saini", "number": "918899700262", "send_alert": True},
    {"name": "Sakshi Saini", "number": "918010488591", "send_alert": True},
    {"name": "Munil Giri", "number": "918802219480", "send_alert": True},
]

CHECK_INTERVAL = 60
HEARTBEAT_INTERVAL = 3600
RETRY_INTERVAL = 1200
PAGE_LOAD_WAIT = 6
CONTENT_STABLE_MAX_WAIT = 10
ENABLE_SOUND = True

# --- WhatsApp templates ------------------------------------------------

# Header for "something came IN stock" section
IN_STOCK_HEADER = """🚨🔥🚨 STOCK ALERT! 🚨🔥🚨

⚡⚡⚡ HURRY! BUY NOW! ⚡⚡⚡
"""

# Header for "something went OUT of stock" section
OUT_OF_STOCK_HEADER = """📉 STOCK GONE — Now Unavailable
"""

# One line per IN-stock item (with link — you want to buy it)
IN_STOCK_LINE = """🎯 {site_emoji} {site_name}
📦 {product_name}
💰 {price_str}
🔗 {url}
"""

# One line per OUT-of-stock item (link kept for reference)
OUT_OF_STOCK_LINE = """❌ {site_emoji} {site_name}
📦 {product_name}
🔗 {url}
"""

MESSAGE_FOOTER = """━━━━━━━━━━━━━━━━━━━━━
⏰ {timestamp}"""

HEARTBEAT_MESSAGE_TEMPLATE = """💓 HEARTBEAT — Tracker Alive
🕐 {timestamp}
⏱️ Uptime: {uptime}
🔍 Last check: {last_check_status}
⏭️ Next check in {next_check}s

✅ Everything running smoothly
"""

# ==================== LOGGING ====================

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("tracker.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ==================== TEXT HELPERS ====================

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


STRONG_NEGATIVE_PHRASES = [
    "currently unavailable",
    "out of stock",
    "sold out",
    "not in stock",
    "temporarily out of stock",
    "unavailable in your area",
]

POSITIVE_STOCK_PHRASES = [
    "add to cart", "add to bag", "add to trolley", "buy now",
    "proceed to buy", "order now",
]

PREORDER_STOCK_PHRASES = [
    "pre-order", "preorder", "pre order", "reserve now", "book now",
]

SOFT_NEGATIVE_PHRASES = [
    "notify me", "email when available", "coming soon", "not available",
]

SITE_DISPLAY = {
    "amazon":   {"emoji": "🛒", "name": "Amazon"},
    "reliance": {"emoji": "🏬", "name": "Reliance Digital"},
    "jiomart":  {"emoji": "🛍️", "name": "JioMart"},
}


def has_any(norm_text: str, phrases: List[str]) -> Optional[str]:
    for p in phrases:
        if p in norm_text:
            return p
    return None


# ==================== TRACKER ====================

class ProductTracker:
    def __init__(self):
        self.last_status: Dict[str, bool] = {}
        self.last_heartbeat = time.time()
        self.start_time = time.time()
        self.pending_error_messages = []
        self.last_successful_check = None

        self.paused = False
        self._setup_pause_control()

        for product in PRODUCTS:
            key = f"{product['name']}_{product['site']}"
            self.last_status[key] = False

        logger.info(f"✅ Tracker initialized with {len(PRODUCTS)} listings")

    # ---------- Pause control ----------

    def _setup_pause_control(self):
        if HAS_KEYBOARD:
            try:
                keyboard.add_hotkey("f9", self._toggle_pause)
                logger.info("⌨️  F9 = pause / resume toggle")
            except Exception as e:
                logger.warning(f"Could not register F9 hotkey: {e}")
        else:
            logger.info("💡 Install 'keyboard' (pip install keyboard) for F9 pause hotkey")
        logger.info(f"📁 Or create/delete '{PAUSE_FLAG_FILE}' to pause/resume")

    def _toggle_pause(self):
        self.paused = not self.paused
        if self.paused:
            logger.info("⏸️  PAUSED — press F9 to resume")
        else:
            logger.info("▶️  RESUMED")

    def is_paused(self) -> bool:
        if self.paused:
            return True
        if os.path.exists(PAUSE_FLAG_FILE):
            return True
        return False

    def wait_if_paused(self):
        if not self.is_paused():
            return
        logger.info("⏸️  Paused. Press F9 or delete pause.flag to resume...")
        while self.is_paused():
            time.sleep(2)
        logger.info("▶️  Resumed")

    def interruptible_sleep(self, seconds: int):
        for _ in range(seconds):
            if self.is_paused():
                self.wait_if_paused()
            time.sleep(1)

    # ---------- Browser / capture ----------

    def open_url_and_read(self, url: str, product_name: str, product_site: str) -> Tuple[str, bool]:
        try:
            logger.info(f"📂 Opening: {product_name}")
            subprocess.Popen([
                CHROME_PATH,
                f"--user-data-dir={BOT_CHROME_PROFILE_DIR}",
                "--profile-directory=Default",
                "--new-window",
                "--start-maximized",
                url,
            ])
            time.sleep(PAGE_LOAD_WAIT)

            page_text = self._capture_stable_text(site=product_site)

            pyautogui.hotkey("alt", "f4")
            time.sleep(1)

            if page_text and len(page_text) > 200:
                return page_text, True
            logger.warning(f"⚠️ Captured only {len(page_text)} chars for {product_name}")
            return page_text, False

        except Exception as e:
            logger.error(f"❌ Error reading {product_name}: {e}")
            try:
                pyautogui.hotkey("alt", "f4")
            except Exception:
                pass
            return "", False

    def _capture_stable_text(self, site: str) -> str:
        text = self._copy_clipboard()

        if site != "jiomart" and len(text) > 1500:
            return text

        last_len = len(text)
        stable_text = text
        waited = 0.0
        step = 1.5

        while waited <= CONTENT_STABLE_MAX_WAIT:
            pyautogui.press("end")
            time.sleep(0.6)
            pyautogui.press("home")
            time.sleep(step)
            waited += step + 0.6

            text = self._copy_clipboard()
            if len(text) == last_len and len(text) > 200:
                stable_text = text
                break
            stable_text = text
            last_len = len(text)

        return stable_text

    def _copy_clipboard(self) -> str:
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.4)
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.4)
        return pyperclip.paste() or ""

    # ---------- Variant verification ----------

    def verify_variant(self, text: str, product: dict) -> bool:
        expect = product.get("expect", [])
        conflict = product.get("conflict", [])
        if not expect and not conflict:
            return True

        full = normalize(text)

        declared = re.search(
            r"(?:size|storage(?:\s*capacity)?|capacity)\s*:\s*([0-9]+\s?(?:gb|tb))",
            full,
        )
        if declared:
            declared_value = declared.group(1).replace(" ", "")
            if conflict and any(bad.replace(" ", "") in declared_value for bad in conflict):
                logger.warning(
                    f"⚠️ Page declares Size/Storage: {declared_value} for "
                    f"{product['name']} - conflicting variant."
                )
                return False
            if expect and any(good.replace(" ", "") in declared_value for good in expect):
                return True

        if expect and not any(good in full for good in expect):
            logger.warning(
                f"⚠️ Could not find expected variant keyword {expect} for "
                f"{product['name']} - likely wrong product/redirect."
            )
            return False

        return True

    # ---------- Price extraction ----------

    def extract_price(self, text: str) -> float:
        patterns = [
            r"₹\s*([\d,]+\.?\d*)\s*incl\.?\s*gst",
            r"deal\s*price[^₹\d]*₹\s*([\d,]+\.?\d*)",
            r"offer\s*price[^₹\d]*₹\s*([\d,]+\.?\d*)",
            r"₹\s*([\d,]+\.?\d*)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    price = float(match.group(1).replace(",", "").strip())
                    if 100 < price < 500000:
                        return price
                except ValueError:
                    continue
        return 0.0

    # ---------- Stock check ----------

    def check_stock(self, text: str, product: dict) -> Tuple[bool, float]:
        norm = normalize(text)

        neg_hit = has_any(norm, STRONG_NEGATIVE_PHRASES)
        if neg_hit:
            logger.info(f"❌ {product['site'].upper()}: OUT OF STOCK - '{neg_hit}'")
            return False, 0.0

        preorder = has_any(norm, PREORDER_STOCK_PHRASES)
        pos = has_any(norm, POSITIVE_STOCK_PHRASES)

        if preorder or pos:
            reason = preorder or pos
            logger.info(f"✅ {product['site'].upper()}: purchase option found - '{reason}'")
            if product["site"] != "jiomart" and not self.verify_variant(text, product):
                logger.info(f"❌ {product['site'].upper()}: OUT OF STOCK - variant mismatch")
                return False, 0.0
            price = self.extract_price(text)
            return True, price

        soft_neg = has_any(norm, SOFT_NEGATIVE_PHRASES)
        if soft_neg:
            logger.info(f"❌ {product['site'].upper()}: OUT OF STOCK - '{soft_neg}'")
            return False, 0.0

        logger.info(f"❌ {product['site'].upper()}: no positive stock signal found")
        return False, 0.0

    def check_product(self, product: dict) -> Tuple[bool, float, bool]:
        try:
            page_text, success = self.open_url_and_read(
                product["url"], product["name"], product["site"]
            )
            if not success or not page_text:
                return False, 0.0, False
            in_stock, price = self.check_stock(page_text, product)
            return in_stock, price, True
        except Exception as e:
            logger.error(f"❌ Error checking {product['name']}: {e}")
            return False, 0.0, False

    def check_all_products(self):
        results = {}
        successful_checks = 0

        logger.info("=" * 50)
        logger.info("🔍 STARTING PRODUCT CHECK")
        logger.info("=" * 50)

        for product in PRODUCTS:
            self.wait_if_paused()
            logger.info(f"--- Checking {product['name']} ---")
            in_stock, price, success = self.check_product(product)
            key = f"{product['name']}_{product['site']}"
            results[key] = (in_stock, price, product["url"], success, product["group"])

            if success:
                successful_checks += 1
            else:
                logger.error(f"❌ Failed to check {product['name']}")

            time.sleep(2)

        if successful_checks > 0:
            self.last_successful_check = time.time()

        network_error = successful_checks == 0
        logger.info(f"✅ CHECK COMPLETE - {successful_checks}/{len(PRODUCTS)} successful")
        return results, network_error

    # ---------- Messaging ----------

    def format_change_message(self, results: Dict) -> str:
        """Build a message showing ONLY products whose status changed since
        the last check. Covers BOTH directions:
          - went IN stock  → 🚨 hype alert with link
          - went OUT stock → 📉 quiet notice with link
        Returns empty string if nothing changed."""
        timestamp = datetime.now().strftime("%d-%b %I:%M %p")

        went_in = []   # (site, product_name, price, url)
        went_out = []  # (site, product_name, price, url)

        for key, (in_stock, price, url, success, group) in results.items():
            if not success:
                continue
            product_name, site = key.rsplit("_", 1)
            prev = self.last_status.get(key, False)  # default False on first run
            if prev == in_stock:
                continue  # no change
            if in_stock:
                went_in.append((site, product_name, price, url))
            else:
                went_out.append((site, product_name, price, url))

        if not went_in and not went_out:
            return ""

        parts = []

        if went_in:
            parts.append(IN_STOCK_HEADER)
            for site, product_name, price, url in went_in:
                meta = SITE_DISPLAY.get(site, {"emoji": "🔗", "name": site.title()})
                price_str = f"₹{price:,.0f}" if price > 0 else "check link for price"
                parts.append(IN_STOCK_LINE.format(
                    site_emoji=meta["emoji"],
                    site_name=meta["name"],
                    product_name=product_name,
                    price_str=price_str,
                    url=url,
                ))

        if went_out:
            if went_in:
                parts.append("")  # spacer between sections
            parts.append(OUT_OF_STOCK_HEADER)
            for site, product_name, price, url in went_out:
                meta = SITE_DISPLAY.get(site, {"emoji": "🔗", "name": site.title()})
                parts.append(OUT_OF_STOCK_LINE.format(
                    site_emoji=meta["emoji"],
                    site_name=meta["name"],
                    product_name=product_name,
                    url=url,
                ))

        parts.append(MESSAGE_FOOTER.format(timestamp=timestamp))
        return "\n".join(parts)

    def format_heartbeat_message(self) -> str:
        timestamp = datetime.now().strftime("%d-%b %I:%M %p")
        uptime_seconds = int(time.time() - self.start_time)
        uptime_str = f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m"
        last_check_str = (
            "Never" if self.last_successful_check is None
            else datetime.fromtimestamp(self.last_successful_check).strftime("%H:%M:%S")
        )
        return HEARTBEAT_MESSAGE_TEMPLATE.format(
            timestamp=timestamp,
            uptime=uptime_str,
            last_check_status=last_check_str,
            next_check=CHECK_INTERVAL,
        )

    def send_whatsapp(self, phone_number: str, message: str) -> bool:
        import urllib.parse
        url = f"https://web.whatsapp.com/send?phone={phone_number}&text={urllib.parse.quote(message)}"

        for attempt in (1, 2):
            try:
                subprocess.Popen([
                    CHROME_PATH,
                    f"--user-data-dir={BOT_CHROME_PROFILE_DIR}",
                    "--profile-directory=Default",
                    "--new-window",
                    url,
                ])
                time.sleep(12)

                for _ in range(3):
                    pyautogui.press("enter")
                    time.sleep(1.5)

                time.sleep(2)
                pyautogui.hotkey("alt", "f4")
                time.sleep(2)

                logger.info(f"✅ WhatsApp sent to {phone_number} (attempt {attempt})")
                return True

            except Exception as e:
                logger.error(f"❌ WhatsApp attempt {attempt} failed for {phone_number}: {e}")
                try:
                    pyautogui.hotkey("alt", "f4")
                except Exception:
                    pass
                if attempt == 1:
                    time.sleep(5)

        logger.error(f"❌ Giving up on WhatsApp send to {phone_number}")
        return False

    def process_results(self, results: Dict, network_error: bool):
        current_time = time.time()

        # Heartbeat
        if current_time - self.last_heartbeat >= HEARTBEAT_INTERVAL:
            heartbeat_msg = self.format_heartbeat_message()
            for contact in (c for c in WHATSAPP_CONTACTS if c["send_alert"]):
                self.send_whatsapp(contact["number"], heartbeat_msg)
                time.sleep(3)
            self.last_heartbeat = current_time

        # Network error handling
        if network_error:
            self.pending_error_messages.append({
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "results": results.copy(),
            })
            return

        # Send any queued pending messages now that we're back online
        if self.pending_error_messages:
            for pending in self.pending_error_messages:
                msg = self.format_change_message(pending["results"])
                if msg:
                    for contact in (c for c in WHATSAPP_CONTACTS if c["send_alert"]):
                        self.send_whatsapp(contact["number"], msg)
                        time.sleep(3)
            self.pending_error_messages = []

        # Build message from THIS cycle's transitions
        message = self.format_change_message(results)

        if not message:
            logger.info("📌 No status change - skipping alert")
        else:
            logger.info("\n" + "=" * 50)
            logger.info("📱 SENDING STOCK CHANGE ALERT")
            logger.info("=" * 50)
            logger.info(message)
            logger.info("=" * 50)

            for contact in (c for c in WHATSAPP_CONTACTS if c["send_alert"]):
                self.send_whatsapp(contact["number"], message)
                time.sleep(3)

            if ENABLE_SOUND:
                self.play_sound()

        # Update stored status for every successful check
        for key, (in_stock, price, url, success, group) in results.items():
            if success:
                self.last_status[key] = in_stock

    def play_sound(self):
        try:
            for freq in [1000, 1200, 1400, 1600, 1000, 1600, 2000]:
                winsound.Beep(freq, 400)
        except Exception as e:
            logger.error(f"❌ Sound failed: {e}")

    def run(self):
        logger.info("🚀 PRODUCT TRACKER STARTED")
        logger.info(f"⏸️  Pause: F9 (or create '{PAUSE_FLAG_FILE}')")
        time.sleep(3)

        try:
            while True:
                try:
                    self.wait_if_paused()
                    logger.info(f"📅 Checking at {datetime.now().strftime('%H:%M:%S')}")
                    results, network_error = self.check_all_products()
                    self.process_results(results, network_error)

                    wait = RETRY_INTERVAL if network_error else CHECK_INTERVAL
                    logger.info(f"⏰ Next check in {wait} seconds...")
                    self.interruptible_sleep(wait)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logger.error(f"❌ Error in main loop: {e}")
                    self.interruptible_sleep(60)
        except KeyboardInterrupt:
            logger.info("🛑 Tracker stopped by user")


if __name__ == "__main__":
    if not os.path.exists(BOT_CHROME_PROFILE_DIR):
        print(f"⚠️  {BOT_CHROME_PROFILE_DIR} does not exist yet.")
        print("    Run this once before starting the tracker:")
        print(f'    "{CHROME_PATH}" --user-data-dir="{BOT_CHROME_PROFILE_DIR}"')
        print("    Then log in to Amazon, Reliance, JioMart, and WhatsApp Web.")
        sys.exit(1)

    print("🚀 PRODUCT AVAILABILITY TRACKER")
    print(f"📦 Tracking {len(PRODUCTS)} listings across "
          f"{len(set(p['group'] for p in PRODUCTS))} product groups")
    print()
    print("⏸️  PAUSE / RESUME:")
    if HAS_KEYBOARD:
        print("   • Press F9 to toggle pause/resume")
    else:
        print("   • Install 'keyboard' for F9 hotkey: pip install keyboard")
    print(f"   • Or create '{PAUSE_FLAG_FILE}' to pause, delete it to resume")
    print()
    print("⚠️  Do not use the bot Chrome profile for anything else while this runs.")
    print("    Press Ctrl+C to stop.\n")

    tracker = ProductTracker()
    tracker.run()