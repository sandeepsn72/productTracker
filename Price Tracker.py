"""
High-Speed Product Availability Tracker
Supports: Amazon.in, Reliance Digital, JioMart
Notifications: WhatsApp Web (Chrome) + Desktop Alerts
Supports: Multiple contacts and groups
"""

import requests
import json
import time
import re
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import pywhatkit as kit
import winsound
import webbrowser
from typing import Dict, List, Optional, Tuple

# ==================== CONFIGURATION ====================

# PRODUCTS TO TRACK - Updated with your MacBook links
PRODUCTS = [
    # Amazon Products (Using ASIN from URL)
    {
        "name": "MacBook Air M5 13-inch (Variant 1)",
        "amazon_asin": "B0GR1JFTPR",  # ASIN from the URL
        "reliance_url": None,
        "jiomart_url": None,
    },
    {
        "name": "MacBook Air M5 13-inch (Variant 2)",
        "amazon_asin": "B0GR1HPR1W",
        "reliance_url": None,
        "jiomart_url": None,
    },
    {
        "name": "MacBook Air M5 13-inch (Variant 3)",
        "amazon_asin": "B0GR1RQ144",
        "reliance_url": None,
        "jiomart_url": None,
    },
    
    # Reliance Digital Products
    {
        "name": "MacBook Air M5 13-inch Silver",
        "amazon_asin": None,
        "reliance_url": "https://www.reliancedigital.in/product/apple-mdh74hna-macbook-air-13-10-core-apple-m5-chip16-gb512-gb-ssdmac-osliquid-retina-3446-cm-136-inch-silver-mmc4sn-9969452",
        "jiomart_url": None,
    },
    {
        "name": "MacBook Air M5 13-inch Sky Blue",
        "amazon_asin": None,
        "reliance_url": "https://www.reliancedigital.in/product/apple-mdhh4hna-macbook-air-13-10-core-apple-m5-chip16-gb512-gb-ssdmac-osliquid-retina-3446-cm-136-inch-sky-blue-mmc4sg-9969472",
        "jiomart_url": None,
    },
    {
        "name": "MacBook Air M5 13-inch Midnight",
        "amazon_asin": None,
        "reliance_url": "https://www.reliancedigital.in/product/apple-mdhe4hna-macbook-air-13-10-core-apple-m5-chip16-gb512-gb-ssdmac-osliquid-retina-3446-cm-136-inch-midnight-mmc4t9-9969451",
        "jiomart_url": None,
    }
]
    {
        "name": "Product Name 1",
        "amazon_asin": "B0XXXXX",  # Amazon ASIN from URL
        "reliance_url": "https://www.reliancedigital.in/product-id/p",
        "jiomart_url": "https://www.jiomart.com/product-id",
    },
    # Add more products
    {
        "name": "Product Name 2",
        "amazon_asin": "B0YYYYY",
        "reliance_url": "https://www.reliancedigital.in/another-product/p",
        "jiomart_url": "https://www.jiomart.com/another-product",
    }
]

# ==================== WHATSAPP CONTACTS ====================

# Option 1: Individual contacts (Add as many as you want)
WHATSAPP_CONTACTS = [
    {
        "name": "Sandeep Saini",
        "number": "+918899700262",  # Your number
        "send_alert": True
    },
    {
        "name": "Sakshi Saini",
        "number": "+918010488591",  # Partner's number
        "send_alert": True
    },
    
    # Add more contacts
]

# Option 2: WhatsApp Group (You can add group IDs too)
# For groups: Use the group ID from WhatsApp Web URL
# When you open a group on web.whatsapp.com, the URL looks like:
# https://web.whatsapp.com/group/GROUP_ID_HERE
# Note: This requires the group to be open in WhatsApp Web
# WHATSAPP_GROUPS = [
#     {
#         "name": "Business Team",
#         "group_id": "GROUP_ID_HERE",  # From WhatsApp Web URL
#         "send_alert": True
#     }
# ]

# ==================== MESSAGE TEMPLATE ====================

WHATSAPP_MESSAGE_TEMPLATE = """🔥 STOCK ALERT! 🔥

Product: {product_name}
Site: {site}
Price: ₹{price:,.2f}
URL: {url}

HURRY! Add to cart NOW!
Time: {timestamp}"""

# ==================== MONITORING CONFIG ====================

CHECK_INTERVAL = 3  # Seconds between checks (2-5 recommended)
MAX_RETRIES = 3
REQUEST_TIMEOUT = 3

# ALERT CONFIG
ENABLE_SOUND = True
ENABLE_DESKTOP_POPUP = True
SEND_TO_ALL_CONTACTS = True  # If False, only sends to first contact
SEND_TO_GROUPS = True

# ==================== SETUP LOGGING ====================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tracker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== TRACKING FUNCTIONS ====================

class ProductTracker:
    def __init__(self):
        self.last_status = {}  # Track last known status to avoid duplicate alerts
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-IN,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Initialize status tracking
        for product in PRODUCTS:
            product_name = product['name']
            if 'amazon_asin' in product and product['amazon_asin']:
                self.last_status[f"{product_name}_amazon"] = False
            if 'reliance_url' in product and product['reliance_url']:
                self.last_status[f"{product_name}_reliance"] = False
            if 'jiomart_url' in product and product['jiomart_url']:
                self.last_status[f"{product_name}_jiomart"] = False
        
        logger.info(f"Tracker initialized with {len(PRODUCTS)} products")
        logger.info(f"Monitoring: {list(self.last_status.keys())}")
        logger.info(f"Contacts loaded: {len([c for c in WHATSAPP_CONTACTS if c['send_alert']])}")
        logger.info(f"Groups loaded: {len([g for g in WHATSAPP_GROUPS if g['send_alert']])}")

    def check_amazon(self, asin: str) -> Tuple[bool, float]:
        """Check Amazon stock and price"""
        try:
            url = f"https://www.amazon.in/dp/{asin}"
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            
            if response.status_code != 200:
                logger.warning(f"Amazon returned status {response.status_code} for {asin}")
                return False, 0.0
            
            text = response.text.lower()
            
            # Check if product is unavailable
            unavailable_indicators = [
                'out of stock',
                'currently unavailable',
                'not available',
                'sold out',
                'we don\'t know when'
            ]
            
            for indicator in unavailable_indicators:
                if indicator in text:
                    return False, 0.0
            
            # Check if "Add to Cart" or "Buy Now" exists
            if 'add to cart' in text or 'buy now' in text:
                # Try to extract price
                price_match = re.search(r'"price":"?([\d,]+\.?\d*)"?', response.text)
                if not price_match:
                    price_match = re.search(r'₹([\d,]+\.?\d*)', response.text)
                
                if price_match:
                    price = float(price_match.group(1).replace(',', ''))
                    return True, price
                return True, 0.0
            
            return False, 0.0
            
        except requests.exceptions.Timeout:
            logger.error(f"Amazon timeout for {asin}")
            return False, 0.0
        except Exception as e:
            logger.error(f"Amazon error for {asin}: {e}")
            return False, 0.0

    def check_reliance(self, url: str) -> Tuple[bool, float]:
        """Check Reliance Digital stock and price"""
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            
            if response.status_code != 200:
                logger.warning(f"Reliance returned status {response.status_code}")
                return False, 0.0
            
            text = response.text.lower()
            
            # Check for out of stock indicators
            out_of_stock_indicators = [
                'out of stock',
                'sold out',
                'currently unavailable',
                'not available',
                'out-of-stock',
                'not in stock'
            ]
            
            for indicator in out_of_stock_indicators:
                if indicator in text:
                    return False, 0.0
            
            # Check if add to cart exists
            if 'add to cart' in text or 'add to bag' in text or 'buy now' in text:
                # Extract price
                price_match = re.search(r'₹([\d,]+\.?\d*)', text)
                if price_match:
                    price = float(price_match.group(1).replace(',', ''))
                    return True, price
                return True, 0.0
            
            return False, 0.0
            
        except requests.exceptions.Timeout:
            logger.error(f"Reliance timeout for {url}")
            return False, 0.0
        except Exception as e:
            logger.error(f"Reliance error: {e}")
            return False, 0.0

    def check_jiomart(self, url: str) -> Tuple[bool, float]:
        """Check JioMart stock and price"""
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            
            if response.status_code != 200:
                logger.warning(f"JioMart returned status {response.status_code}")
                return False, 0.0
            
            text = response.text.lower()
            
            # Check for out of stock
            if 'out of stock' in text or 'sold out' in text or 'unavailable' in text:
                return False, 0.0
            
            # Check if add to cart exists
            if 'add to cart' in text or 'add to bag' in text:
                price_match = re.search(r'₹([\d,]+\.?\d*)', text)
                if price_match:
                    price = float(price_match.group(1).replace(',', ''))
                    return True, price
                return True, 0.0
            
            return False, 0.0
            
        except requests.exceptions.Timeout:
            logger.error(f"JioMart timeout for {url}")
            return False, 0.0
        except Exception as e:
            logger.error(f"JioMart error: {e}")
            return False, 0.0

    def check_all_products(self):
        """Check all products across all platforms"""
        results = {}
        
        # Check each product
        for product in PRODUCTS:
            product_name = product['name']
            
            # Check Amazon
            if 'amazon_asin' in product and product['amazon_asin']:
                in_stock, price = self.check_amazon(product['amazon_asin'])
                key = f"{product_name}_amazon"
                results[key] = (in_stock, price, f"https://www.amazon.in/dp/{product['amazon_asin']}")
                logger.debug(f"{key}: {'IN STOCK' if in_stock else 'out of stock'} - ₹{price}")
            
            # Check Reliance
            if 'reliance_url' in product and product['reliance_url']:
                in_stock, price = self.check_reliance(product['reliance_url'])
                key = f"{product_name}_reliance"
                results[key] = (in_stock, price, product['reliance_url'])
                logger.debug(f"{key}: {'IN STOCK' if in_stock else 'out of stock'} - ₹{price}")
            
            # Check JioMart
            if 'jiomart_url' in product and product['jiomart_url']:
                in_stock, price = self.check_jiomart(product['jiomart_url'])
                key = f"{product_name}_jiomart"
                results[key] = (in_stock, price, product['jiomart_url'])
                logger.debug(f"{key}: {'IN STOCK' if in_stock else 'out of stock'} - ₹{price}")
            
            # Small delay between products to avoid rate limiting
            time.sleep(0.5)
        
        return results

    def process_results(self, results: Dict):
        """Process results and send alerts for new stock"""
        for key, (in_stock, price, url) in results.items():
            # If stock status changed from False to True
            if in_stock and not self.last_status.get(key, False):
                product_name, site = key.rsplit('_', 1)
                logger.info(f"🔥 STOCK DETECTED: {key} at ₹{price}")
                
                # Send alerts to ALL contacts
                self.send_alerts_to_all(product_name, site, price, url)
                
                # Update status
                self.last_status[key] = True
            
            # If out of stock, update status
            elif not in_stock:
                self.last_status[key] = False

    def send_alerts_to_all(self, product_name: str, site: str, price: float, url: str):
        """Send alerts to all configured contacts and groups"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Format message
        message = WHATSAPP_MESSAGE_TEMPLATE.format(
            product_name=product_name,
            site=site.title(),
            price=price,
            url=url,
            timestamp=timestamp
        )
        
        # Send to individual contacts
        if SEND_TO_ALL_CONTACTS:
            active_contacts = [c for c in WHATSAPP_CONTACTS if c['send_alert']]
            logger.info(f"Sending to {len(active_contacts)} contacts")
            
            for contact in active_contacts:
                try:
                    contact_name = contact['name']
                    contact_number = contact['number']
                    
                    logger.info(f"📱 Sending WhatsApp to {contact_name} ({contact_number})")
                    self.send_whatsapp_message(contact_number, message)
                    
                    # Small delay between messages to avoid rate limiting
                    time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Failed to send to {contact['name']}: {e}")
        
        # Send to groups
        if SEND_TO_GROUPS and WHATSAPP_GROUPS:
            active_groups = [g for g in WHATSAPP_GROUPS if g['send_alert']]
            logger.info(f"Sending to {len(active_groups)} groups")
            
            for group in active_groups:
                try:
                    group_name = group['name']
                    logger.info(f"👥 Sending WhatsApp to group: {group_name}")
                    # Note: For groups, you need to use the group ID
                    self.send_whatsapp_group_message(group['group_id'], message)
                    time.sleep(2)
                except Exception as e:
                    logger.error(f"Failed to send to group {group['name']}: {e}")
        
        # Desktop popup alert (only if enabled)
        if ENABLE_DESKTOP_POPUP:
            self.show_desktop_alert(product_name, site, price, url)
        
        # Sound alert
        if ENABLE_SOUND:
            self.play_sound_alert()

    def send_whatsapp_message(self, phone_number: str, message: str):
        """Send WhatsApp message using pywhatkit"""
        try:
            # Send instantly using pywhatkit
            kit.sendwhatmsg_instantly(
                phone_no=phone_number,
                message=message,
                wait_time=15,  # Wait for page load
                tab_close=True,  # Close tab after sending
                close_time=5  # Wait 5 seconds before closing
            )
            logger.info(f"✅ WhatsApp sent to {phone_number}")
            return True
            
        except Exception as e:
            logger.error(f"❌ WhatsApp send failed for {phone_number}: {e}")
            # Fallback: Open WhatsApp Web URL
            self.send_whatsapp_fallback(phone_number, message)
            return False

    def send_whatsapp_group_message(self, group_id: str, message: str):
        """Send WhatsApp message to a group"""
        try:
            # For groups, we need to use the group ID
            # Note: This is more complex with pywhatkit
            # Alternative: Use the web URL approach
            import webbrowser
            encoded_message = requests.utils.quote(message)
            url = f"https://web.whatsapp.com/group/{group_id}?text={encoded_message}"
            webbrowser.open(url)
            logger.info(f"✅ Group message link opened for {group_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Group message failed: {e}")
            return False

    def send_whatsapp_fallback(self, phone_number: str, message: str):
        """Fallback method: Open WhatsApp Web URL in browser"""
        try:
            import webbrowser
            # Clean phone number (remove +)
            clean_number = phone_number.replace('+', '')
            encoded_message = requests.utils.quote(message)
            url = f"https://web.whatsapp.com/send?phone={clean_number}&text={encoded_message}"
            webbrowser.open(url)
            logger.info(f"WhatsApp link opened in browser for {phone_number}")
            return True
        except Exception as e:
            logger.error(f"Fallback send failed: {e}")
            return False

    def show_desktop_alert(self, product_name: str, site: str, price: float, url: str):
        """Show desktop notification"""
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, 
                f"🔥 {product_name} IN STOCK on {site}!\nPrice: ₹{price:,.2f}\nURL: {url}",
                "STOCK ALERT", 
                0x40  # Information icon
            )
            logger.info("✅ Desktop popup shown")
            return True
        except Exception as e:
            logger.error(f"❌ Desktop popup failed: {e}")
            return False

    def play_sound_alert(self):
        """Play loud sound alerts"""
        try:
            # Play multiple beeps to wake you up
            frequencies = [1000, 1200, 1400, 1600, 1000]
            durations = [500, 500, 500, 500, 1000]
            
            for freq, duration in zip(frequencies, durations):
                winsound.Beep(freq, duration)
            
            logger.info("✅ Sound alert played")
            return True
        except Exception as e:
            logger.error(f"❌ Sound alert failed: {e}")
            return False

    def run(self):
        """Main monitoring loop"""
        logger.info("=" * 60)
        logger.info("🚀 PRODUCT TRACKER STARTED")
        logger.info(f"📦 Products: {len(PRODUCTS)}")
        logger.info(f"⏱️  Check Interval: {CHECK_INTERVAL} seconds")
        logger.info(f"👤 Contacts: {len([c for c in WHATSAPP_CONTACTS if c['send_alert']])}")
        logger.info(f"👥 Groups: {len([g for g in WHATSAPP_GROUPS if g['send_alert']])}")
        logger.info("=" * 60)
        logger.info("📌 IMPORTANT:")
        logger.info("1. Make sure WhatsApp Web is open in Chrome")
        logger.info("2. You must be logged into WhatsApp Web")
        logger.info("3. For groups: Ensure group is visible in WhatsApp Web")
        logger.info("\nPress Ctrl+C to stop\n")
        
        try:
            while True:
                try:
                    # Check all products
                    logger.info(f"\n🔍 Checking at {datetime.now().strftime('%H:%M:%S')}")
                    results = self.check_all_products()
                    
                    # Process results and send alerts
                    self.process_results(results)
                    
                    # Wait before next check
                    time.sleep(CHECK_INTERVAL)
                    
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    time.sleep(CHECK_INTERVAL * 2)  # Wait longer on error
                    
        except KeyboardInterrupt:
            logger.info("\n🛑 Tracker stopped by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}")

# ==================== MAIN EXECUTION ====================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 PRODUCT AVAILABILITY TRACKER")
    print("="*60)
    print("\n📌 IMPORTANT:")
    print("1. Make sure WhatsApp Web is open in Chrome")
    print("2. You must be logged into WhatsApp Web")
    print(f"3. Contacts: {len([c for c in WHATSAPP_CONTACTS if c['send_alert']])}")
    print(f"4. Check interval: {CHECK_INTERVAL} seconds")
    print("\nPress Ctrl+C to stop\n")
    
    # Initialize and run tracker
    tracker = ProductTracker()
    tracker.run()