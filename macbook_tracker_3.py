"""
Product Availability Tracker - FINAL
Sends WhatsApp ONLY when stock is available.
"""

import time
import logging
from datetime import datetime
import winsound
import pyautogui
import os
import re
import subprocess
from typing import Dict, List, Optional, Tuple

# ==================== CONFIGURATION ====================

PRODUCTS = [
    {
        "name": "MacBook Air M5 (Variant 1)",
        "url": "https://www.amazon.in/dp/B0GR1JFTPR",
        "site": "amazon"
    },
    {
        "name": "MacBook Air M5 (Variant 2)",
        "url": "https://www.amazon.in/dp/B0GR1HPR1W",
        "site": "amazon"
    },
    {
        "name": "MacBook Air M5 (Variant 3)",
        "url": "https://www.amazon.in/dp/B0GR1RQ144",
        "site": "amazon"
    },
    {
        "name": "MacBook Air M5 Sky Blue",
        "url": "https://www.reliancedigital.in/product/apple-mdh74hna-macbook-air-13-10-core-apple-m5-chip16-gb512-gb-ssdmac-osliquid-retina-3446-cm-136-inch-silver-mmc4sn-9969452?internal_source=search_results",
        "site": "reliance"
    },
    {
        "name": "MacBook Air M5 Midnight",
        "url": "https://www.reliancedigital.in/product/apple-mdhe4hna-macbook-air-13-10-core-apple-m5-chip16-gb512-gb-ssdmac-osliquid-retina-3446-cm-136-inch-midnight-mmc4t9-9969451?internal_source=search_results",
        "site": "reliance"
    },
    {
        "name": "MacBook Air M5 Silver",
        "url": "https://www.reliancedigital.in/product/apple-mdh74hna-macbook-air-13-10-core-apple-m5-chip16-gb512-gb-ssdmac-osliquid-retina-3446-cm-136-inch-silver-mmc4sn-9969452",
        "site": "reliance"
    }
]

WHATSAPP_CONTACTS = [
    {"name": "Sandeep Saini", "number": "918899700262", "send_alert": True},
    {"name": "Sakshi Saini", "number": "918010488591", "send_alert": True},
]

# ==================== EXCITING MESSAGE TEMPLATES ====================

STOCK_AVAILABLE_TEMPLATE = """🚨🔥🚨 STOCK AVAILABLE! 🚨🔥🚨

⚡⚡⚡ HURRY! BUY NOW! ⚡⚡⚡

{available_products}

⏰ Detected at: {timestamp}
🛒 GO GO GO! Click the link above and buy!

━━━━━━━━━━━━━━━━━━━━━━━━
💰 Don't wait — these sell out in MINUTES!
━━━━━━━━━━━━━━━━━━━━━━━━"""

PRODUCT_AVAILABLE_LINE = """🎯 {site}
📦 {product_name}
💰 Price: {price}
🔗 {url}
"""

CHECK_INTERVAL = 120
ENABLE_SOUND = True
SEND_ALERT_ONLY_ON_CHANGE = False  # Send EVERY time stock is available (not just on state change)

# ==================== SETUP LOGGING ====================

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tracker.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# ==================== TRACKER CLASS ====================

class ProductTracker:
    def __init__(self):
        for product in PRODUCTS:
            key = f"{product['name']}_{product['site']}"
            # Not used for state, but kept for compatibility
        logger.info(f"✅ Tracker initialized with {len(PRODUCTS)} products")

    def open_url_and_read(self, url: str, product_name: str) -> str:
        """Open URL in Chrome and read page content"""
        try:
            chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

            logger.info(f"📂 Opening: {product_name}")
            subprocess.Popen([chrome_path, "--new-window", url])
            time.sleep(6)

            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.5)
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.5)

            import pyperclip
            page_text = pyperclip.paste()

            pyautogui.hotkey('alt', 'f4')
            time.sleep(1)

            return page_text

        except Exception as e:
            logger.error(f"❌ Error reading {product_name}: {e}")
            try:
                pyautogui.hotkey('alt', 'f4')
            except:
                pass
            return ""

    def extract_reliance_price(self, text: str) -> float:
        patterns = [
            r'class="product-price"[^>]*>.*?₹([\d,]+\.?\d*)',
            r'deal-price-text[^>]*>Deal\s*Price</span>\s*₹([\d,]+\.?\d*)',
            r'Deal\s*Price[^>]*>[\s\n]*₹([\d,]+\.?\d*)',
            r'Offer\s*Price[^>]*>[\s\n]*₹([\d,]+\.?\d*)',
            r'₹([\d,]+\.?\d*)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                try:
                    price = float(match.group(1).replace(',', '').strip())
                    if 100 < price < 500000:
                        return price
                except:
                    continue
        return 0.0

    def extract_amazon_price(self, text: str) -> float:
        patterns = [
            r'₹([\d,]+\.?\d*)\s*incl\.\s*GST',
            r'priceblock_ourprice[^>]*>₹([\d,]+\.?\d*)',
            r'priceblock_dealprice[^>]*>₹([\d,]+\.?\d*)',
            r'price_inside_buybox[^>]*>₹([\d,]+\.?\d*)',
            r'"price":"?([\d,]+\.?\d*)"?',
            r'₹([\d,]+\.?\d*)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    price = float(match.group(1).replace(',', '').strip())
                    if 100 < price < 500000:
                        return price
                except:
                    continue
        return 0.0

    def check_reliance(self, text: str) -> Tuple[bool, float]:
        out_of_stock_keywords = [
            'out of stock', 'sold out', 'not available', 'out-of-stock',
            'currently unavailable', 'not in stock', 'temporarily out of stock',
        ]
        for keyword in out_of_stock_keywords:
            if keyword in text.lower():
                logger.info(f"❌ Reliance: OUT OF STOCK - '{keyword}'")
                return False, 0.0

        has_add_to_cart = bool(re.search(r'add-to-cart|add to cart', text, re.IGNORECASE))

        if has_add_to_cart:
            price = self.extract_reliance_price(text)
            logger.info(f"✅ Reliance: IN STOCK - Rs.{price}")
            return True, price

        return False, 0.0

    def check_amazon(self, text: str) -> Tuple[bool, float]:
        out_of_stock = ['out of stock', 'currently unavailable', 'not available', 'sold out']
        for indicator in out_of_stock:
            if indicator in text.lower():
                logger.info(f"❌ Amazon: OUT OF STOCK - '{indicator}'")
                return False, 0.0

        has_add_to_cart = 'add to cart' in text.lower() or 'add-to-cart' in text.lower()
        has_buy_now = 'buy now' in text.lower() or 'buy-now' in text.lower()
        has_in_stock = 'in stock' in text.lower()

        if has_add_to_cart or has_buy_now or has_in_stock:
            price = self.extract_amazon_price(text)
            logger.info(f"✅ Amazon: IN STOCK - Price: Rs.{price}")
            return True, price

        return False, 0.0

    def check_product(self, product: dict) -> Tuple[bool, float]:
        try:
            page_text = self.open_url_and_read(product['url'], product['name'])
            if not page_text:
                logger.error(f"❌ Failed to read {product['name']}")
                return False, 0.0
            if product['site'] == 'reliance':
                return self.check_reliance(page_text)
            return self.check_amazon(page_text)
        except Exception as e:
            logger.error(f"❌ Error checking {product['name']}: {e}")
            return False, 0.0

    def check_all_products(self):
        results = {}
        logger.info("\n" + "=" * 50)
        logger.info("🔍 STARTING PRODUCT CHECK")
        logger.info("=" * 50)

        pyautogui.click(100, 100)
        time.sleep(1)

        for product in PRODUCTS:
            logger.info(f"\n--- Checking {product['name']} ---")
            in_stock, price = self.check_product(product)
            key = f"{product['name']}_{product['site']}"
            results[key] = (in_stock, price, product['url'])

            status = "✅ IN STOCK" if in_stock else "❌ OUT OF STOCK"
            logger.info(f"📊 RESULT: {product['name']} - {status} - Rs.{price}")
            time.sleep(2)

        logger.info("=" * 50)
        logger.info("✅ PRODUCT CHECK COMPLETE")
        logger.info("=" * 50)
        return results

    def format_stock_message(self, available: List[Tuple[str, float, str]]) -> str:
        """Format the exciting stock-available message"""
        timestamp = datetime.now().strftime("%d-%b-%Y %I:%M:%S %p")

        product_blocks = []
        for name, price, url in available:
            site = "AMAZON 🛍️" if "amazon" in name.lower() or "amazon" in url.lower() else "RELIANCE DIGITAL 🏬"
            price_str = f"₹{price:,.2f}" if price > 0 else "Check link"
            product_blocks.append(
                PRODUCT_AVAILABLE_LINE.format(
                    site=site,
                    product_name=name,
                    price=price_str,
                    url=url,
                )
            )

        return STOCK_AVAILABLE_TEMPLATE.format(
            available_products="\n".join(product_blocks),
            timestamp=timestamp,
        )

    def send_whatsapp(self, phone_number: str, message: str):
        try:
            import requests
            url = f"https://web.whatsapp.com/send?phone={phone_number}&text={requests.utils.quote(message)}"

            chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            if os.path.exists(chrome_path):
                subprocess.Popen([chrome_path, "--new-window", url])
                time.sleep(5)
            else:
                import webbrowser
                webbrowser.open(url)
                time.sleep(5)

            for _ in range(3):
                pyautogui.press('enter')
                time.sleep(0.5)

            pyautogui.hotkey('alt', 'f4')
            time.sleep(1)

            logger.info(f"✅ WhatsApp sent to {phone_number}")
            return True
        except Exception as e:
            logger.error(f"❌ WhatsApp failed: {e}")
            return False

    def process_results(self, results: Dict):
        """ONLY send WhatsApp if at least one product is in stock"""
        available = [
            (key.rsplit('_', 1)[0], price, url)
            for key, (in_stock, price, url) in results.items()
            if in_stock
        ]

        if not available:
            logger.info("😴 No stock available. No alert sent.")
            return

        logger.info(f"🎉 {len(available)} product(s) IN STOCK — sending alert!")

        message = self.format_stock_message(available)
        logger.info("\n" + "=" * 50)
        logger.info("📱 SENDING STOCK ALERT")
        logger.info("=" * 50)
        logger.info(message)
        logger.info("=" * 50)

        active_contacts = [c for c in WHATSAPP_CONTACTS if c['send_alert']]
        for contact in active_contacts:
            logger.info(f"📤 Sending to {contact['name']} ({contact['number']})")
            self.send_whatsapp(contact['number'], message)
            time.sleep(3)

        if ENABLE_SOUND:
            self.play_sound()

    def play_sound(self):
        try:
            frequencies = [1000, 1200, 1400, 1600, 1000, 1600, 2000]
            for freq in frequencies:
                winsound.Beep(freq, 300)
        except Exception as e:
            logger.error(f"❌ Sound failed: {e}")

    def run(self):
        logger.info("=" * 60)
        logger.info("🚀 PRODUCT TRACKER STARTED")
        logger.info("=" * 60)
        logger.info(f"📦 Products: {len(PRODUCTS)}")
        logger.info(f"⏱️  Check Interval: {CHECK_INTERVAL} seconds")
        logger.info(f"👤 Contacts: {len([c for c in WHATSAPP_CONTACTS if c['send_alert']])}")
        logger.info("=" * 60)
        logger.info("🔔 Alerts sent ONLY when stock is AVAILABLE")
        logger.info("=" * 60)
        logger.info("\n🔄 Starting in 3 seconds...")
        time.sleep(3)

        try:
            while True:
                logger.info(f"\n📅 Checking at {datetime.now().strftime('%H:%M:%S')}")
                results = self.check_all_products()

                logger.info("\n" + "=" * 50)
                logger.info("📊 CURRENT STATUS:")
                for key, (in_stock, price, url) in results.items():
                    status = "✅ IN STOCK" if in_stock else "❌ OUT OF STOCK"
                    logger.info(f"  {key}: {status} - Rs.{price}")
                logger.info("=" * 50)

                self.process_results(results)

                logger.info(f"⏰ Next check in {CHECK_INTERVAL} seconds...")
                time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            logger.info("\n🛑 Tracker stopped by user")
        except Exception as e:
            logger.error(f"❌ Error in main loop: {e}")


# ==================== MAIN ====================

if __name__ == "__main__":
    try:
        import pyperclip
    except ImportError:
        print("📦 Installing pyperclip...")
        os.system("pip install pyperclip")
        import pyperclip

    print("\n" + "=" * 60)
    print("🚀 PRODUCT AVAILABILITY TRACKER - HYPE MODE")
    print("=" * 60)
    print("\n📌 FEATURES:")
    print("  🔥 Sends WhatsApp ONLY when stock is AVAILABLE")
    print("  📊 Checks all products every 2 minutes")
    print("  ⚡ Exciting alerts with prices and direct links")
    print("\n⚠️  IMPORTANT:")
    print("  - Keep WhatsApp Web logged in")
    print("  - Do not use Chrome while script runs")
    print("  - Press Ctrl+C to stop\n")

    tracker = ProductTracker()
    tracker.run()