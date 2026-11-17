"""
Product Availability Tracker - Windows Version (100% Background / Headless)
Monitors MacBook Neo (4 colors) on Reliance Digital.
Sends WhatsApp alerts on stock availability and reports tracker status on first run.

Runs completely in the background without opening browser windows, stealing focus,
or simulating keypresses/mouse clicks. You can freely use your laptop while it runs!

PAUSE / RESUME:
  1. Press F9 (needs: pip install keyboard)
  2. Or create/delete "pause.flag" in the script folder

FIRST-TIME SETUP (if not done yet):
  1. Run:  chrome.exe --user-data-dir="C:\ChromeBotProfile"
  2. In that Chrome window, log in to WhatsApp Web.
  3. Close Chrome. From then on the script reuses that profile headlessly.
"""

import time
import logging
import os
import re
import sys
import io
import urllib.parse
from datetime import datetime
from typing import Dict, List, Tuple, Optional

import winsound

try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as SeleniumOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# ==================== CONFIGURATION ====================

BOT_CHROME_PROFILE_DIR = r"C:\ChromeBotProfile"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PAUSE_FLAG_FILE = os.path.join(SCRIPT_DIR, "pause.flag")

PRODUCTS = [
    {
        "name": "MacBook Neo 13\" Indigo",
        "group": "MacBook Neo 13\"",
        "url": "https://www.reliancedigital.in/product/apple-mhfg4hna-macbook-neo-apple-a18-pro-chip8-gb512-gb-ssdmacosliquid-retina-3302-cm-13-inch-indigo-mmdg1i-9971844",
        "site": "reliance",
        "expect": [], "conflict": []
    },
    {
        "name": "MacBook Neo 13\" Blush",
        "group": "MacBook Neo 13\"",
        "url": "https://www.reliancedigital.in/product/apple-mhfj4hna-macbook-neo-apple-a18-pro-chip8-gb512-gb-ssdmacosliquid-retina-3302-cm-13-inch-blush-mmdg1k-9971846",
        "site": "reliance",
        "expect": [], "conflict": []
    },
    {
        "name": "MacBook Neo 13\" Silver",
        "group": "MacBook Neo 13\"",
        "url": "https://www.reliancedigital.in/product/apple-mhfc4hna-macbook-neo-apple-a18-pro-chip8-gb512-gb-ssdmacosliquid-retina-3302-cm-13-inch-silver-mmdg1g-9971842",
        "site": "reliance",
        "expect": [], "conflict": []
    },
    {
        "name": "MacBook Neo 13\" Citrus",
        "group": "MacBook Neo 13\"",
        "url": "https://www.reliancedigital.in/product/apple-mhfe4hna-macbook-neo-apple-a18-pro-chip8-gb512-gb-ssdmacosliquid-retina-3302-cm-13-inch-citrus-mmdg1g-9971838",
        "site": "reliance",
        "expect": [], "conflict": []
    },
]

WHATSAPP_CONTACTS = [
    {"name": "Sandeep Saini", "number": "918899700262", "send_alert": True},
    {"name": "Gurmeet", "number": "918950158616", "send_alert": True},
    {"name": "Munil Giri", "number": "918802219480", "send_alert": True},
]

CHECK_INTERVAL = 120
HEARTBEAT_INTERVAL = 10800
RETRY_INTERVAL = 1200
PAGE_LOAD_WAIT = 5
ENABLE_SOUND = True

# --- WhatsApp templates ------------------------------------------------

INITIAL_STATUS_HEADER = """🚀 *MACBOOK TRACKER ONLINE*
━━━━━━━━━━━━━━━━━━━━━
⏰ *Started:* {timestamp}
📦 *Monitored Listings:* {total_count} on Reliance Digital
⏱️ *Check Frequency:* Every {interval}s
━━━━━━━━━━━━━━━━━━━━━
📋 *INITIAL STOCK STATUS:*
{status_lines}
━━━━━━━━━━━━━━━━━━━━━
{summary_note}"""

IN_STOCK_HEADER = """🚨🔥🚨 STOCK ALERT! 🚨🔥🚨

⚡⚡⚡ HURRY! BUY NOW! ⚡⚡⚡
"""

OUT_OF_STOCK_HEADER = """📉 STOCK GONE — Now Unavailable
"""

IN_STOCK_LINE = """🎯 {site_emoji} {site_name}
📦 {product_name}
💰 {price_str}
🔗 {url}
"""

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

file_handler = logging.FileHandler("tracker.log", encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(file_formatter)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.WARNING)  # Only show log on console if there is an issue (WARNING / ERROR)
console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(console_formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.handlers.clear()
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# ==================== TEXT HELPERS ====================

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


STRONG_NEGATIVE_PHRASES = [
    "currently unavailable online",
    "currently unavailable",
    "out of stock",
    "sold out",
    "not in stock",
    "temporarily out of stock",
    "unavailable in your area",
    "notify me",
    "visit nearest store",
]

POSITIVE_STOCK_PHRASES = [
    "add to cart", "add to bag", "add to trolley", "buy now",
    "proceed to buy", "order now",
]

PREORDER_STOCK_PHRASES = [
    "pre-order", "preorder", "pre order", "reserve now", "book now",
]

SOFT_NEGATIVE_PHRASES = [
    "email when available", "coming soon", "not available",
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
        self.is_first_run = True

        self.paused = False
        self._setup_pause_control()

        for product in PRODUCTS:
            key = f"{product['name']}_{product['site']}"
            self.last_status[key] = False

        logger.info(f"✅ Tracker initialized with {len(PRODUCTS)} listings (Headless Background Mode)")

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

    # ---------- Drivers (Headless) ----------

    def _create_product_driver(self):
        """Headless driver for checking product availability (no profile needed)."""
        try:
            options = SeleniumOptions()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-gpu-compositing")
            options.add_argument("--log-level=3")
            options.add_argument("--silent")
            options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
            options.page_load_strategy = "eager"
            options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            service = ChromeService(log_output=os.devnull)
            return webdriver.Chrome(options=options, service=service)
        except Exception as e:
            logger.error(f"⚠️ Could not create product Selenium driver: {e}")
            return None

    def _create_whatsapp_driver(self):
        """Headless driver for WhatsApp Web using the logged-in profile."""
        try:
            options = SeleniumOptions()
            options.add_argument("--headless=new")
            options.add_argument(f"--user-data-dir={BOT_CHROME_PROFILE_DIR}")
            options.add_argument("--profile-directory=Default")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-gpu-compositing")
            options.add_argument("--log-level=3")
            options.add_argument("--silent")
            options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
            options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            service = ChromeService(log_output=os.devnull)
            return webdriver.Chrome(options=options, service=service)
        except Exception as e:
            logger.error(f"❌ Failed to create WhatsApp headless driver: {e}")
            return None

    # ---------- Page capture (100% Headless) ----------

    def read_url_headless(self, driver, url: str) -> Tuple[str, bool]:
        try:
            driver.get(url)
            time.sleep(3.5)
            last_len = 0
            stable_text = ""
            for _ in range(6):
                try:
                    text = driver.execute_script("return document.body.innerText;") or ""
                except Exception:
                    text = driver.find_element(By.TAG_NAME, "body").text

                if len(text) == last_len and len(text) > 300:
                    stable_text = text
                    break
                stable_text = text
                last_len = len(text)
                driver.execute_script("window.scrollBy(0, 400);")
                time.sleep(1)

            if stable_text and len(stable_text) > 200:
                return stable_text, True

            # Fallback scroll to bottom if needed
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            try:
                stable_text = driver.execute_script("return document.body.innerText;") or ""
            except Exception:
                stable_text = driver.find_element(By.TAG_NAME, "body").text

            if stable_text and len(stable_text) > 200:
                return stable_text, True

            return stable_text, False
        except Exception as e:
            logger.warning(f"⚠️ Headless fetch failed for {url}: {e}")
            return "", False

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
                logger.warning(f"⚠️ Conflicting variant declared: {declared_value}")
                return False
            if expect and any(good.replace(" ", "") in declared_value for good in expect):
                return True

        if expect and not any(good in full for good in expect):
            logger.warning(f"⚠️ Expected {expect} not found for {product['name']}")
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
            return False, self.extract_price(text)

        preorder = has_any(norm, PREORDER_STOCK_PHRASES)
        pos = has_any(norm, POSITIVE_STOCK_PHRASES)

        if preorder or pos:
            reason = preorder or pos
            logger.info(f"✅ {product['site'].upper()}: purchase option found - '{reason}'")
            if product["site"] != "jiomart" and not self.verify_variant(text, product):
                logger.info(f"❌ {product['site'].upper()}: OUT OF STOCK - variant mismatch")
                return False, 0.0
            return True, self.extract_price(text)

        soft_neg = has_any(norm, SOFT_NEGATIVE_PHRASES)
        if soft_neg:
            logger.info(f"❌ {product['site'].upper()}: OUT OF STOCK - '{soft_neg}'")
            return False, self.extract_price(text)

        logger.info(f"❌ {product['site'].upper()}: no positive stock signal found")
        return False, self.extract_price(text)

    def check_all_products(self):
        results = {}
        successful_checks = 0

        logger.info("=" * 50)
        logger.info("🔍 STARTING PRODUCT CHECK (Background)")
        logger.info("=" * 50)

        driver = self._create_product_driver()
        if not driver:
            logger.error("❌ Failed to launch headless Chrome driver for product check")
            return results, True

        try:
            for product in PRODUCTS:
                self.wait_if_paused()
                logger.info(f"--- Checking {product['name']} ---")

                page_text, success = self.read_url_headless(driver, product["url"])

                if not success or not page_text:
                    logger.warning(f"⚠️ Retrying headless check for {product['name']}...")
                    time.sleep(2)
                    page_text, success = self.read_url_headless(driver, product["url"])

                if success and page_text:
                    in_stock, price = self.check_stock(page_text, product)
                    successful_checks += 1
                else:
                    logger.error(f"❌ Failed to check {product['name']}")
                    in_stock, price = False, 0.0

                key = f"{product['name']}_{product['site']}"
                results[key] = (in_stock, price, product["url"], success, product["group"])
                time.sleep(1)

        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

        if successful_checks > 0:
            self.last_successful_check = time.time()

        network_error = successful_checks == 0
        logger.info(f"✅ CHECK COMPLETE - {successful_checks}/{len(PRODUCTS)} successful")
        return results, network_error

    # ---------- Messaging Templates ----------

    def format_initial_status_message(self, results: Dict) -> str:
        timestamp = datetime.now().strftime("%d-%b %I:%M %p")
        status_lines = []
        any_in_stock = False

        for key, (in_stock, price, url, success, group) in results.items():
            product_name, site = key.rsplit("_", 1)
            if not success:
                status_lines.append(f"⚠️ *{product_name}*: Check Failed (will retry)")
            elif in_stock:
                any_in_stock = True
                price_str = f"₹{price:,.0f}" if price > 0 else "Price on site"
                status_lines.append(f"🟢 *{product_name}*: IN STOCK ({price_str})\n   🔗 {url}")
            else:
                price_str = f" (₹{price:,.0f})" if price > 0 else ""
                status_lines.append(f"🔴 *{product_name}*: Out of Stock{price_str}")

        summary_note = (
            "🚨 *ACTION REQUIRED:* One or more items are currently IN STOCK! Check links above to purchase."
            if any_in_stock
            else "✅ Tracker is actively monitoring. You will be alerted immediately if any model becomes available!"
        )

        return INITIAL_STATUS_HEADER.format(
            timestamp=timestamp,
            total_count=len(PRODUCTS),
            interval=CHECK_INTERVAL,
            status_lines="\n".join(status_lines),
            summary_note=summary_note,
        )

    def format_change_message(self, results: Dict) -> str:
        timestamp = datetime.now().strftime("%d-%b %I:%M %p")
        went_in = []
        went_out = []

        for key, (in_stock, price, url, success, group) in results.items():
            if not success:
                continue
            product_name, site = key.rsplit("_", 1)
            prev = self.last_status.get(key, False)
            if prev == in_stock:
                continue
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
                parts.append("")
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
        return "\n".join(p for p in parts if p)

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

    # ---------- WhatsApp (100% Headless - No GUI, No Keypresses) ----------

    def _send_whatsapp_with_driver(self, driver, phone_number: str, message: str) -> bool:
        clean_phone = re.sub(r"\D", "", str(phone_number))
        encoded = urllib.parse.quote(message)
        url = f"https://web.whatsapp.com/send?phone={clean_phone}&text={encoded}"

        for attempt in (1, 2):
            try:
                logger.info(f"📱 Dispatching WhatsApp to {clean_phone} in background (attempt {attempt})...")
                driver.get(url)

                start = time.time()
                while time.time() - start < 30:
                    time.sleep(1)

                    # Check for send button
                    send_btns = driver.find_elements(
                        By.CSS_SELECTOR,
                        "button[aria-label='Send'], span[data-icon='send'], span[data-icon='send-light']"
                    )
                    if send_btns:
                        btn = send_btns[0]
                        if btn.tag_name == "span":
                            btn = btn.find_element(By.XPATH, "..")
                        try:
                            driver.execute_script("arguments[0].click();", btn)
                            logger.info(f"✅ WhatsApp sent to {phone_number}")
                            time.sleep(3)  # Wait for message to be sent over network
                            return True
                        except Exception as e:
                            logger.debug(f"Click attempt failed: {e}")

                    # Fallback: check if message loaded in textbox and press Enter via WebDriver
                    textboxes = driver.find_elements(
                        By.CSS_SELECTOR,
                        "div[contenteditable='true'][data-tab='10'], footer div[contenteditable='true']"
                    )
                    if textboxes:
                        tb = textboxes[0]
                        if tb.text.strip():
                            try:
                                tb.send_keys(Keys.ENTER)
                                logger.info(f"✅ WhatsApp sent to {phone_number} (via Enter)")
                                time.sleep(3)
                                return True
                            except Exception as e:
                                logger.debug(f"Enter key failed: {e}")

                    # Check for actual modal dialog error (only if a modal dialog is open)
                    dialogs = driver.find_elements(By.CSS_SELECTOR, "div[role='dialog'], div[data-animate-modal-popup='true']")
                    if dialogs:
                        dialog_text = dialogs[0].text.lower()
                        if "invalid" in dialog_text or "phone number" in dialog_text:
                            ok_btns = dialogs[0].find_elements(By.XPATH, ".//button")
                            if ok_btns:
                                try:
                                    ok_btns[0].click()
                                except Exception:
                                    pass
                            logger.error(f"❌ Phone number {phone_number} is invalid according to WhatsApp dialog")
                            return False

                logger.warning(f"⚠️ Timeout waiting to send WhatsApp to {phone_number}")
            except Exception as e:
                logger.error(f"❌ Error sending WhatsApp to {phone_number} (attempt {attempt}): {e}")

            if attempt == 1:
                time.sleep(2)

        return False

    def send_whatsapp(self, phone_number: str, message: str) -> bool:
        """Send a single WhatsApp message headlessly."""
        driver = self._create_whatsapp_driver()
        if not driver:
            return False
        try:
            return self._send_whatsapp_with_driver(driver, phone_number, message)
        finally:
            try:
                driver.quit()
            except Exception:
                pass

    def broadcast_whatsapp(self, message: str):
        """Broadcast message to all active contacts using a single headless session."""
        active_contacts = [c for c in WHATSAPP_CONTACTS if c.get("send_alert", True)]
        if not active_contacts:
            return

        driver = self._create_whatsapp_driver()
        if not driver:
            logger.error("❌ Could not start WhatsApp headless driver for broadcast")
            return

        try:
            for contact in active_contacts:
                logger.info(f"📤 Sending to {contact['name']} ({contact['number']})...")
                self._send_whatsapp_with_driver(driver, contact["number"], message)
                time.sleep(1.5)
        finally:
            try:
                driver.quit()
            except Exception:
                pass

    # ---------- Processing Results ----------

    def process_results(self, results: Dict, network_error: bool):
        current_time = time.time()

        # First-run status report
        if self.is_first_run:
            logger.info("\n" + "=" * 50)
            logger.info("📢 REPORTING INITIAL TRACKER STATUS ON WHATSAPP")
            logger.info("=" * 50)
            initial_status_msg = self.format_initial_status_message(results)
            logger.info(initial_status_msg)
            logger.info("=" * 50)

            if not network_error:
                self.broadcast_whatsapp(initial_status_msg)
                self.is_first_run = False

                any_in_stock = any(r[0] for r in results.values() if r[3])
                if any_in_stock and ENABLE_SOUND:
                    self.play_sound()

                for key, (in_stock, price, url, success, group) in results.items():
                    if success:
                        self.last_status[key] = in_stock
                return
            else:
                logger.warning("⚠️ Network error on first run, will retry initial status report next cycle.")
                return

        # Heartbeat
        if current_time - self.last_heartbeat >= HEARTBEAT_INTERVAL:
            heartbeat_msg = self.format_heartbeat_message()
            logger.info("💓 Sending periodic heartbeat to WhatsApp contacts...")
            self.broadcast_whatsapp(heartbeat_msg)
            self.last_heartbeat = current_time

        # Network error handling
        if network_error:
            self.pending_error_messages.append({
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "results": results.copy(),
            })
            return

        # Flush pending
        if self.pending_error_messages:
            for pending in self.pending_error_messages:
                msg = self.format_change_message(pending["results"])
                if msg:
                    self.broadcast_whatsapp(msg)
            self.pending_error_messages = []

        # Change alerts
        message = self.format_change_message(results)
        if not message:
            logger.info("📌 No status change - skipping alert")
        else:
            logger.info("\n" + "=" * 50)
            logger.info("📱 SENDING STOCK CHANGE ALERT")
            logger.info("=" * 50)
            logger.info(message)
            logger.info("=" * 50)
            self.broadcast_whatsapp(message)

            if ENABLE_SOUND:
                self.play_sound()

        for key, (in_stock, price, url, success, group) in results.items():
            if success:
                self.last_status[key] = in_stock

    def play_sound(self):
        pass
    def run(self):
        logger.info("🚀 PRODUCT TRACKER STARTED (100% Background Mode)")
        logger.info(f"⏸️  Pause: F9 (or create '{PAUSE_FLAG_FILE}')")
        time.sleep(2)

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


# ==================== MAIN ====================

if __name__ == "__main__":
    if not os.path.exists(BOT_CHROME_PROFILE_DIR):
        # print(f"⚠️  {BOT_CHROME_PROFILE_DIR} does not exist yet.")
        # print("    Run this once before starting the tracker:")
        # print(f'    chrome.exe --user-data-dir="{BOT_CHROME_PROFILE_DIR}"')
        # print("    Then log in to WhatsApp Web.")
        logger.error(f"❌ {BOT_CHROME_PROFILE_DIR} does not exist yet. Please create it first.")
        sys.exit(1)

    # print("🚀 PRODUCT AVAILABILITY TRACKER (Headless Background Mode)")
    # print(f"📦 Tracking {len(PRODUCTS)} listings on Reliance Digital")
    # print("💻 Runs completely in the background: your mouse and keyboard will NOT be touched!")
    # print()
    # print("⏸️  PAUSE / RESUME:")
    # if HAS_KEYBOARD:
    #     print("   • Press F9 to toggle pause/resume")
    # else:
    #     print("   • Install 'keyboard' for F9 hotkey: pip install keyboard")
    # print(f"   • Or create '{PAUSE_FLAG_FILE}' to pause, delete it to resume")
    # print()
    # print("    Press Ctrl+C to stop.\n")

    tracker = ProductTracker()
    tracker.run()
