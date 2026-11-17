"""
Product Availability Tracker - Final Version
With Heartbeat Messages & Network Error Handling
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

# UPDATE THIS SECTION WITH YOUR PRODUCTS
PRODUCTS = [
    # Amazon Products
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
    
    # Reliance Digital Products
    {
           "name": "MacBook Air M5 Sky Blue",
           "url": "https://www.reliancedigital.in/product/apple-mdh74hna-macbook-air-13-10-core-apple-m5-chip16-gb512-gb-ssdmac-osliquid-retina-3446-cm-136-inch-silver-mmc4sn-9969452?internal_source=search_results",
           "site": "reliance"
       },
    {
        "name": "MacBook Air M5 Midnight",
        "url": "https://www.reliancedigital.in/product/apple-mdhe4hna-macbook-air-13-10-core-apple-m5-chip16-gb512-gb-ssdmac-osliquid-retina-3446-cm-136-inch-midnight-mmc4t9-9969451",
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
    {"name": "Munil Giri", "number": "918802219480", "send_alert": True},
]

CONSOLIDATED_MESSAGE_TEMPLATE = """[📊 STOCK STATUS UPDATE]
Time: {timestamp}

{product_status}

---
Total Products: {total}
✅ In Stock: {in_stock_count}
❌ Out of Stock: {out_of_stock_count}
"""

HEARTBEAT_MESSAGE_TEMPLATE = """[💓 HEARTBEAT - Tracker Running]
Time: {timestamp}
Uptime: {uptime}
Products Monitored: {total}
Last Check: {last_check_status}

✅ Program is running normally
Next check in {next_check} seconds
"""

ERROR_MESSAGE_TEMPLATE = """[⚠️ NETWORK ERROR]
Time: {timestamp}
Product: {product_name}
Error: {error}


Retrying in {retry_interval} minutes...
"""

CHECK_INTERVAL = 120  # Seconds between checks
HEARTBEAT_INTERVAL = 3600  # 1 hour (3600 seconds)
RETRY_INTERVAL = 1200  # 20 minutes (1200 seconds)
MAX_RETRIES = 3
ENABLE_SOUND = True
SEND_ALERT_ONLY_ON_CHANGE = True

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
        self.last_status = {}
        self.last_alert_status = None
        self.last_heartbeat = time.time()
        self.start_time = time.time()
        self.pending_error_messages = []  # Store messages to send when back online
        self.network_error_count = 0
        self.last_successful_check = None
        
        for product in PRODUCTS:
            key = f"{product['name']}_{product['site']}"
            self.last_status[key] = False
        
        logger.info(f"✅ Tracker initialized with {len(PRODUCTS)} products")
        logger.info(f"💓 Heartbeat every {HEARTBEAT_INTERVAL//60} minutes")
        logger.info(f"⚠️ Network retry after {RETRY_INTERVAL//60} minutes")

    def open_url_and_read(self, url: str, product_name: str) -> Tuple[str, bool]:
        """Open URL in Chrome and read page content with error handling"""
        try:
            chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            
            logger.info(f"📂 Opening: {product_name}")
            subprocess.Popen([chrome_path, "--new-window", url])
            time.sleep(6)  # Wait for page to load
            
            # Select all and copy
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.5)
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.5)
            
            import pyperclip
            page_text = pyperclip.paste()
            
            # Close Chrome
            pyautogui.hotkey('alt', 'f4')
            time.sleep(1)
            
            if page_text and len(page_text) > 100:
                return page_text, True
            else:
                return "", False
            
        except Exception as e:
            logger.error(f"❌ Error reading {product_name}: {e}")
            try:
                pyautogui.hotkey('alt', 'f4')
            except:
                pass
            return "", False

    def extract_reliance_price(self, text: str) -> float:
        """Extract price from Reliance page"""
        patterns = [
            r'class="product-price"[^>]*>.*?₹([\d,]+\.?\d*)',
            r'class="product-price"[^>]*>.*?([\d,]+\.?\d*)',
            r'deal-price-text[^>]*>Deal\s*Price</span>\s*₹([\d,]+\.?\d*)',
            r'deal-price-text[^>]*>Deal\s*Price</span>\s*([\d,]+\.?\d*)',
            r'Deal\s*Price[^>]*>[\s\n]*₹([\d,]+\.?\d*)',
            r'Offer\s*Price[^>]*>[\s\n]*₹([\d,]+\.?\d*)',
            r'₹([\d,]+\.?\d*)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                try:
                    price_str = match.group(1).replace(',', '').strip()
                    price = float(price_str)
                    if 100 < price < 500000:
                        return price
                except:
                    continue
        return 0.0

    def extract_amazon_price(self, text: str) -> float:
        """Extract price from Amazon page"""
        patterns = [
            r'₹([\d,]+\.?\d*)\s*incl\.\s*GST',
            r'₹([\d,]+\.?\d*)\s*Incl\.\s*GST',
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
                    price_str = match.group(1).replace(',', '').strip()
                    price = float(price_str)
                    if 100 < price < 500000:
                        return price
                except:
                    continue
        return 0.0

    def check_reliance(self, text: str) -> Tuple[bool, float]:
        """Check Reliance product"""
        # Out of stock indicators
        out_of_stock_keywords = [
            'out of stock', 'sold out', 'not available', 'out-of-stock',
            'currently unavailable', 'not in stock', 'temporarily out of stock'
        ]
        
        for keyword in out_of_stock_keywords:
            if keyword in text.lower():
                logger.info(f"❌ Reliance: OUT OF STOCK - found '{keyword}'")
                return False, 0.0
        
        # Check for Add to Cart button
        add_to_cart_patterns = [
            r'add-to-cart[^>]*>',
            r'id="add-to-cart"',
            r'addtocart',
            r'add to cart',
        ]
        
        has_add_to_cart = False
        for pattern in add_to_cart_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                has_add_to_cart = True
                break
        
        has_deal_price = 'deal price' in text.lower() or 'deal-price' in text.lower()
        has_product_price = 'product-price' in text
        
        if has_add_to_cart:
            price = self.extract_reliance_price(text)
            logger.info(f"✅ Reliance: IN STOCK - Add to Cart found! Price: Rs.{price}")
            return True, price
        
        if has_deal_price or has_product_price:
            logger.info(f"❌ Reliance: OUT OF STOCK - Price shown but no Add to Cart")
            return False, 0.0
        
        return False, 0.0

    def check_amazon(self, text: str) -> Tuple[bool, float]:
        """Check Amazon product"""
        out_of_stock = ['out of stock', 'currently unavailable', 'not available', 'sold out']
        for indicator in out_of_stock:
            if indicator in text.lower():
                logger.info(f"❌ Amazon: OUT OF STOCK - found '{indicator}'")
                return False, 0.0
        
        has_add_to_cart = 'add to cart' in text.lower() or 'add-to-cart' in text.lower()
        has_buy_now = 'buy now' in text.lower() or 'buy-now' in text.lower()
        has_in_stock = 'in stock' in text.lower()
        
        if has_add_to_cart or has_buy_now or has_in_stock:
            price = self.extract_amazon_price(text)
            logger.info(f"✅ Amazon: IN STOCK - Price: Rs.{price}")
            return True, price
        
        return False, 0.0

    def check_product(self, product: dict) -> Tuple[bool, float, bool]:
        """Check a single product with network error detection"""
        try:
            page_text, success = self.open_url_and_read(product['url'], product['name'])
            
            if not success or not page_text:
                logger.error(f"❌ Network error or empty response for {product['name']}")
                return False, 0.0, False
            
            if product['site'] == 'reliance':
                in_stock, price = self.check_reliance(page_text)
            else:
                in_stock, price = self.check_amazon(page_text)
            
            return in_stock, price, True
                
        except Exception as e:
            logger.error(f"❌ Error checking {product['name']}: {e}")
            return False, 0.0, False

    def check_all_products(self):
        """Check all products with network error handling"""
        results = {}
        network_error = False
        successful_checks = 0
        
        logger.info("\n" + "="*50)
        logger.info("🔍 STARTING PRODUCT CHECK")
        logger.info("="*50)
        
        pyautogui.click(100, 100)
        time.sleep(3)
        
        for product in PRODUCTS:
            logger.info(f"\n--- Checking {product['name']} ---")
            in_stock, price, success = self.check_product(product)
            key = f"{product['name']}_{product['site']}"
            results[key] = (in_stock, price, product['url'], success)
            
            if success:
                successful_checks += 1
                status = "✅ IN STOCK" if in_stock else "❌ OUT OF STOCK"
                logger.info(f"📊 RESULT: {product['name']} - {status} - Rs.{price}")
            else:
                network_error = True
                logger.error(f"❌ NETWORK ERROR: Failed to check {product['name']}")
            
            time.sleep(2)
        
        # Update last successful check time
        if successful_checks > 0:
            self.last_successful_check = time.time()
            self.network_error_count = 0
        else:
            self.network_error_count += 1
        
        logger.info("="*50)
        logger.info(f"✅ PRODUCT CHECK COMPLETE - {successful_checks}/{len(PRODUCTS)} successful")
        logger.info("="*50)
        
        return results, network_error

    def format_consolidated_message(self, results: Dict) -> str:
        """Format consolidated message with all products"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        product_lines = []
        in_stock_count = 0
        out_of_stock_count = 0
        error_count = 0
        
        for key, (in_stock, price, url, success) in results.items():
            product_name, site = key.rsplit('_', 1)
            
            if not success:
                error_count += 1
                product_lines.append(f"{site.upper()}: {product_name}")
                product_lines.append(f"  Status: ⚠️ CHECK FAILED - Network Error")
                product_lines.append("")
                continue
            
            status = "✅ IN STOCK" if in_stock else "❌ OUT OF STOCK"
            
            if in_stock:
                in_stock_count += 1
            else:
                out_of_stock_count += 1
            
            price_str = f"Rs.{price:,.2f}" if price > 0 else "Price N/A"
            product_lines.append(f"{site.upper()}: {product_name}")
            product_lines.append(f"  Status: {status}")
            product_lines.append(f"  Price: {price_str}")
            product_lines.append(f"  URL: {url}")
            product_lines.append("")
        
        message = CONSOLIDATED_MESSAGE_TEMPLATE.format(
            timestamp=timestamp,
            product_status="\n".join(product_lines),
            total=len(PRODUCTS),
            in_stock_count=in_stock_count,
            out_of_stock_count=out_of_stock_count
        )
        
        if error_count > 0:
            message += f"\n⚠️ {error_count} product(s) had network errors"
        
        return message

    def format_heartbeat_message(self) -> str:
        """Format heartbeat message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        uptime_seconds = int(time.time() - self.start_time)
        uptime_hours = uptime_seconds // 3600
        uptime_minutes = (uptime_seconds % 3600) // 60
        
        uptime_str = f"{uptime_hours}h {uptime_minutes}m"
        
        # Build status summary
        in_stock_count = sum(1 for status in self.last_status.values() if status)
        total_products = len(PRODUCTS)
        
        last_check_str = "Never" if self.last_successful_check is None else datetime.fromtimestamp(self.last_successful_check).strftime("%H:%M:%S")
        
        return HEARTBEAT_MESSAGE_TEMPLATE.format(
            timestamp=timestamp,
            uptime=uptime_str,
            total=total_products,
            last_check_status=f"✅ Last successful: {last_check_str} | In Stock: {in_stock_count}/{total_products}",
            next_check=CHECK_INTERVAL
        )

    def format_error_message(self, product_name: str, error: str) -> str:
        """Format error message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        return ERROR_MESSAGE_TEMPLATE.format(
            timestamp=timestamp,
            product_name=product_name,
            error=error,
            retry_interval=RETRY_INTERVAL//60
        )

    def send_whatsapp(self, phone_number: str, message: str):
        """Send WhatsApp message"""
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
                time.sleep(10)
            
            for _ in range(3):
                pyautogui.press('enter')
                time.sleep(0.5)
            
            pyautogui.hotkey('alt', 'f4')
            time.sleep(2)
            
            logger.info(f"✅ WhatsApp sent to {phone_number}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send WhatsApp: {e}")
            return False

    def process_results(self, results: Dict, network_error: bool):
        """Process results and send alerts"""
        current_time = time.time()
        
        # Check if we should send heartbeat
        if current_time - self.last_heartbeat >= HEARTBEAT_INTERVAL:
            logger.info("💓 Sending heartbeat message...")
            heartbeat_msg = self.format_heartbeat_message()
            
            active_contacts = [c for c in WHATSAPP_CONTACTS if c['send_alert']]
            for contact in active_contacts:
                self.send_whatsapp(contact['number'], heartbeat_msg)
                time.sleep(3)
            
            self.last_heartbeat = current_time
        
        # If network error, store messages for later
        if network_error:
            logger.warning("⚠️ Network error detected - will retry later")
            self.pending_error_messages.append({
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "results": results.copy()
            })
            return
        
        # If we were offline and now back online, send pending messages
        if self.pending_error_messages and not network_error:
            logger.info(f"📤 Online again! Sending {len(self.pending_error_messages)} pending messages...")
            for pending in self.pending_error_messages:
                message = f"[📨 PENDING UPDATE FROM {pending['timestamp']}]\n\n"
                message += self.format_consolidated_message(pending['results'])
                
                active_contacts = [c for c in WHATSAPP_CONTACTS if c['send_alert']]
                for contact in active_contacts:
                    self.send_whatsapp(contact['number'], message)
                    time.sleep(3)
            
            self.pending_error_messages = []
        
        # Normal processing - only send if status changed
        current_status = tuple((key, in_stock, price) for key, (in_stock, price, url, success) in results.items())
        
        if SEND_ALERT_ONLY_ON_CHANGE and self.last_alert_status == current_status:
            logger.info("📌 No status change - skipping WhatsApp alert")
            return
        
        message = self.format_consolidated_message(results)
        
        logger.info("\n" + "="*50)
        logger.info("📱 SENDING CONSOLIDATED ALERT")
        logger.info("="*50)
        logger.info(message)
        logger.info("="*50)
        
        active_contacts = [c for c in WHATSAPP_CONTACTS if c['send_alert']]
        for contact in active_contacts:
            logger.info(f"📤 Sending to {contact['name']} ({contact['number']})")
            self.send_whatsapp(contact['number'], message)
            time.sleep(3)
        
        self.last_alert_status = current_status
        
        # Update statuses
        for key, (in_stock, price, url, success) in results.items():
            if success:
                self.last_status[key] = in_stock
        
        if ENABLE_SOUND and not network_error:
            self.play_sound()

    def play_sound(self):
        """Play sound alert"""
        try:
            frequencies = [1000, 1200, 1400, 1600, 1000]
            for freq in frequencies:
                winsound.Beep(freq, 500)
        except Exception as e:
            logger.error(f"❌ Sound failed: {e}")

    def run(self):
        """Main loop with error handling"""
        logger.info("=" * 60)
        logger.info("🚀 PRODUCT TRACKER STARTED")
        logger.info("=" * 60)
        logger.info(f"📦 Products: {len(PRODUCTS)}")
        logger.info(f"⏱️  Check Interval: {CHECK_INTERVAL} seconds")
        logger.info(f"💓 Heartbeat: Every {HEARTBEAT_INTERVAL//60} minutes")
        logger.info(f"⚠️ Network Retry: {RETRY_INTERVAL//60} minutes")
        logger.info(f"👤 Contacts: {len([c for c in WHATSAPP_CONTACTS if c['send_alert']])}")
        logger.info("=" * 60)
        logger.info("🔧 Features:")
        logger.info("  - Sends alert ONLY when stock changes")
        logger.info("  - Heartbeat every hour")
        logger.info("  - Network error detection & retry")
        logger.info("  - Pending messages stored & sent when online")
        logger.info("=" * 60)
        logger.info("\n🔄 Starting in 3 seconds...")
        time.sleep(3)
        
        try:
            while True:
                try:
                    logger.info(f"\n📅 Checking at {datetime.now().strftime('%H:%M:%S')}")
                    results, network_error = self.check_all_products()
                    
                    # Display status
                    logger.info("\n" + "="*50)
                    logger.info("📊 CURRENT STATUS:")
                    for key, (in_stock, price, url, success) in results.items():
                        if success:
                            status = "✅ IN STOCK" if in_stock else "❌ OUT OF STOCK"
                            logger.info(f"  {key}: {status} - Rs.{price}")
                        else:
                            logger.info(f"  {key}: ⚠️ NETWORK ERROR")
                    logger.info("="*50)
                    
                    self.process_results(results, network_error)
                    
                    # If network error, wait longer before retry
                    if network_error:
                        logger.info(f"⏰ Network error - waiting {RETRY_INTERVAL//60} minutes before retry...")
                        time.sleep(RETRY_INTERVAL)
                    else:
                        logger.info(f"⏰ Next check in {CHECK_INTERVAL} seconds...")
                        time.sleep(CHECK_INTERVAL)
                    
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logger.error(f"❌ Error in main loop: {e}")
                    time.sleep(60)  # Wait 1 minute on error
                    
        except KeyboardInterrupt:
            logger.info("\n🛑 Tracker stopped by user")
        except Exception as e:
            logger.error(f"❌ Fatal error: {e}")

# ==================== MAIN ====================

if __name__ == "__main__":
    try:
        import pyperclip
    except ImportError:
        print("📦 Installing pyperclip...")
        os.system("pip install pyperclip")
        import pyperclip
    
    print("\n" + "="*60)
    print("🚀 PRODUCT AVAILABILITY TRACKER - FINAL")
    print("="*60)
    print("\n📌 FEATURES:")
    print("  ✅ Sends alert ONLY when stock changes")
    print("  💓 Heartbeat every hour")
    print("  ⚠️ Network error detection & retry")
    print("  📨 Pending messages stored & sent when online")
    print("\n⚠️  IMPORTANT:")
    print("  - Keep WhatsApp Web logged in")
    print("  - Do not use Chrome while script runs")
    print("  - Press Ctrl+C to stop\n")
    
    tracker = ProductTracker()
    tracker.run()