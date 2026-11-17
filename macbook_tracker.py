"""
Product Availability Tracker - Fixed Reliance Detection
Properly detects out-of-stock status on Reliance Digital
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

CONSOLIDATED_MESSAGE_TEMPLATE = """[📊 STOCK STATUS UPDATE]
Time: {timestamp}

{product_status}

---
Total Products: {total}
✅ In Stock: {in_stock_count}
❌ Out of Stock: {out_of_stock_count}
"""

CHECK_INTERVAL = 120  # Seconds between checks
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
        
        for product in PRODUCTS:
            key = f"{product['name']}_{product['site']}"
            self.last_status[key] = False
        
        logger.info(f"✅ Tracker initialized with {len(PRODUCTS)} products")

    def open_url_and_read(self, url: str, product_name: str) -> str:
        """Open URL in Chrome and read page content"""
        try:
            chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            
            logger.info(f"📂 Opening: {product_name}")
            subprocess.Popen([chrome_path, "--new-window", url])
            time.sleep(10)  # Wait for page to load
            
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
            
            return page_text
            
        except Exception as e:
            logger.error(f"❌ Error reading {product_name}: {e}")
            try:
                pyautogui.hotkey('alt', 'f4')
            except:
                pass
            return ""

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
        """Check Reliance product - FIXED for out of stock"""
        # Log first 500 chars for debugging
        logger.debug(f"Reliance page snippet: {text[:500]}")
        
        # === OUT OF STOCK INDICATORS ===
        out_of_stock_keywords = [
            'out of stock',
            'sold out',
            'not available',
            'out-of-stock',
            'currently unavailable',
            'not in stock',
            'temporarily out of stock',
            'unavailable'
        ]
        
        for keyword in out_of_stock_keywords:
            if keyword in text.lower():
                logger.info(f"❌ Reliance: OUT OF STOCK - found '{keyword}'")
                return False, 0.0
        
        # === CHECK FOR "ADD TO CART" BUTTON ===
        # Look for the actual Add to Cart button
        has_add_to_cart = False
        add_to_cart_patterns = [
            r'add-to-cart[^>]*>',  # Class name
            r'id="add-to-cart"',   # ID
            r'addtocart',          # Combined text
            r'add to cart',        # Text
            r'Add to Cart',        # Text with caps
        ]
        
        for pattern in add_to_cart_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                has_add_to_cart = True
                logger.info(f"✅ Found Add to Cart pattern: {pattern}")
                break
        
        # === CHECK FOR DEAL PRICE WITH DISABLED BUTTON ===
        has_deal_price = 'deal price' in text.lower() or 'deal-price' in text.lower()
        has_product_price = 'product-price' in text
        
        # If Add to Cart button exists, it's IN STOCK
        if has_add_to_cart:
            price = self.extract_reliance_price(text)
            logger.info(f"✅ Reliance: IN STOCK - Add to Cart found! Price: Rs.{price}")
            return True, price
        
        # If no Add to Cart but has price and deal price, it's OUT OF STOCK
        if has_deal_price or has_product_price:
            logger.info(f"❌ Reliance: OUT OF STOCK - Price shown but no Add to Cart button")
            return False, 0.0
        
        logger.info("❌ Reliance: OUT OF STOCK - No Add to Cart or price found")
        return False, 0.0

    def check_amazon(self, text: str) -> Tuple[bool, float]:
        """Check Amazon product"""
        # Out of stock indicators
        out_of_stock = ['out of stock', 'currently unavailable', 'not available', 'sold out']
        for indicator in out_of_stock:
            if indicator in text.lower():
                logger.info(f"❌ Amazon: OUT OF STOCK - found '{indicator}'")
                return False, 0.0
        
        # Check for in stock
        has_add_to_cart = 'add to cart' in text.lower() or 'add-to-cart' in text.lower()
        has_buy_now = 'buy now' in text.lower() or 'buy-now' in text.lower()
        has_in_stock = 'in stock' in text.lower()
        
        logger.info(f"Amazon indicators - Add to Cart: {has_add_to_cart}, Buy Now: {has_buy_now}")
        
        if has_add_to_cart or has_buy_now or has_in_stock:
            price = self.extract_amazon_price(text)
            logger.info(f"✅ Amazon: IN STOCK - Price: Rs.{price}")
            return True, price
        
        return False, 0.0

    def check_product(self, product: dict) -> Tuple[bool, float]:
        """Check a single product"""
        try:
            page_text = self.open_url_and_read(product['url'], product['name'])
            
            if not page_text:
                logger.error(f"❌ Failed to read {product['name']}")
                return False, 0.0
            
            if product['site'] == 'reliance':
                return self.check_reliance(page_text)
            else:
                return self.check_amazon(page_text)
                
        except Exception as e:
            logger.error(f"❌ Error checking {product['name']}: {e}")
            return False, 0.0

    def check_all_products(self):
        """Check all products"""
        results = {}
        
        logger.info("\n" + "="*50)
        logger.info("🔍 STARTING PRODUCT CHECK")
        logger.info("="*50)
        
        # Click on desktop to focus
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
        
        logger.info("="*50)
        logger.info("✅ PRODUCT CHECK COMPLETE")
        logger.info("="*50)
        
        return results

    def format_consolidated_message(self, results: Dict) -> str:
        """Format consolidated message with all products"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        product_lines = []
        in_stock_count = 0
        out_of_stock_count = 0
        
        for key, (in_stock, price, url) in results.items():
            product_name, site = key.rsplit('_', 1)
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
        
        return message

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
                time.sleep(5)
            
            for _ in range(3):
                pyautogui.press('enter')
                time.sleep(0.5)
            
            pyautogui.hotkey('alt', 'f4')
            time.sleep(1)
            
            logger.info(f"✅ WhatsApp sent to {phone_number}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send WhatsApp: {e}")
            return False

    def process_results(self, results: Dict):
        """Process results and send consolidated alerts"""
        current_status = tuple((key, in_stock, price) for key, (in_stock, price, url) in results.items())
        
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
            try:
                logger.info(f"📤 Sending to {contact['name']} ({contact['number']})")
                self.send_whatsapp(contact['number'], message)
                time.sleep(3)
            except Exception as e:
                logger.error(f"❌ Failed to send to {contact['name']}: {e}")
        
        self.last_alert_status = current_status
        
        for key, (in_stock, price, url) in results.items():
            self.last_status[key] = in_stock
        
        if ENABLE_SOUND:
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
        """Main loop"""
        logger.info("=" * 60)
        logger.info("🚀 PRODUCT TRACKER STARTED")
        logger.info("=" * 60)
        logger.info(f"📦 Products: {len(PRODUCTS)}")
        logger.info(f"⏱️  Check Interval: {CHECK_INTERVAL} seconds")
        logger.info(f"👤 Contacts: {len([c for c in WHATSAPP_CONTACTS if c['send_alert']])}")
        logger.info("=" * 60)
        logger.info("🔧 Reliance Detection Fixed:")
        logger.info("  - Checks for 'Add to Cart' button")
        logger.info("  - Identifies out-of-stock properly")
        logger.info("  - Distinguishes price display vs availability")
        logger.info("=" * 60)
        logger.info("\n🔄 Starting in 3 seconds...")
        time.sleep(3)
        
        try:
            while True:
                logger.info(f"\n📅 Checking at {datetime.now().strftime('%H:%M:%S')}")
                results = self.check_all_products()
                
                logger.info("\n" + "="*50)
                logger.info("📊 CURRENT STATUS:")
                for key, (in_stock, price, url) in results.items():
                    status = "✅ IN STOCK" if in_stock else "❌ OUT OF STOCK"
                    logger.info(f"  {key}: {status} - Rs.{price}")
                logger.info("="*50)
                
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
    
    print("\n" + "="*60)
    print("🚀 PRODUCT AVAILABILITY TRACKER")
    print("="*60)
    print("\n📌 FIXED - Reliance Out of Stock Detection")
    print("   ✅ Checks for 'Add to Cart' button")
    print("   ✅ Identifies out-of-stock properly")
    print("   ✅ Distinguishes price display vs availability")
    print("\n⚠️  IMPORTANT:")
    print("- Keep WhatsApp Web logged in")
    print("- Do not use Chrome while script runs")
    print("- Press Ctrl+C to stop\n")


    
    tracker = ProductTracker()
    tracker.run()