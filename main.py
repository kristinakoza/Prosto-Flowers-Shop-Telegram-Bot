import math
import hashlib
import os
import time
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler
)
import ssl
import certifi
import json
# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
SHOPIFY_STORE = os.getenv('SHOPIFY_STORE')
SHOPIFY_STOREFRONT_TOKEN = os.getenv('SHOPIFY_STOREFRONT_TOKEN')
INSTAGRAM_USERNAME = os.getenv('INSTAGRAM_USERNAME')
WHATSAPP_NUMBER = os.getenv('WHATSAPP_NUMBER')

# Verify critical variables
if not TELEGRAM_TOKEN:
    logger.error("❌ Telegram token not found in environment variables")
    exit(1)

if not SHOPIFY_STORE or not SHOPIFY_STOREFRONT_TOKEN:
    logger.error("❌ Shopify configuration incomplete - product features disabled")
    SHOPIFY_ENABLED = False
else:
    SHOPIFY_ENABLED = True
    logger.info("✅ Shopify integration enabled")

# Debug store info
logger.info(f"Shopify Store: {SHOPIFY_STORE}")

# Determine current API version
API_VERSION = "2025-07"  # Using a stable, known working version

# GraphQL endpoint for Storefront API
if SHOPIFY_ENABLED:
    SHOPIFY_GRAPHQL_URL = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/graphql.json"
    logger.info(f"Using Shopify API URL: {SHOPIFY_GRAPHQL_URL}")
    
TAG_MAPPINGS = {
    # Price ranges
    "under50": ["under50", "under 50", "cheap", "budget"],
    "50-150": ["50-150", "50 to 150", "midrange", "affordable"],
    "151-250": ["151-250", "151 to 250", "premium"],
    "over250": ["over250", "over 250", "luxury"],
    
    # Occasions
    "anniversary": ["anniversary", "anniversaries"],
    "valentine": ["valentine", "valentines", "valentine's day"],
    "romantic": ["romantic", "romance", "love"],
    "getwell": ["getwell", "get well", "recovery", "feel better"],
    "wedding": ["wedding", "bridal", "bridesmaid"],
    "birthday": ["birthday", "bday", "birthdays"],
    "fathersday": ["fathersday", "father's day", "dad"],
    
    # Flower types
    "roses": ["roses", "rose"],
    "lilies": ["lilies", "lily"],
    "tulips": ["tulips", "tulip"],
    "orchids": ["orchids", "orchid"],
    "sunflowers": ["sunflowers", "sunflower"],
    "mixed": ["mixed", "assorted", "variety"]
}

FAQ_DATA = {
    "delivery": {
        "question": "🚚 Delivery Information",
        "answer": (
            "🌺 *Delivery Details:*\n\n"
            "• We offer same-day delivery for orders\n"
            "• Delivery areas: Abu Dhabi\n"
            "• Delivery fee: AED 20 (free for orders over AED 150)\n"
            "• Delivery hours: 10am - 10pm\n\n"
            "We carefully package all bouquets to ensure they arrive fresh and beautiful!"
        )
    },
    "payment": {
        "question": "💳 Payment Methods",
        "answer": (
            "💳 *Payment Options:*\n\n"
            "We accept:\n"
            "• Cash on delivery\n"
            "• Credit/Debit Cards (Visa, MasterCard)\n"
            "• Apple Pay & Google Pay\n"
            "• Bank transfer (for advance orders)\n\n"
            "All online payments are secured with SSL encryption."
        )
    },
    "care": {
        "question": "🌼 Flower Care Tips",
        "answer": (
            "💧 *Keeping Flowers Fresh:*\n\n"
            "1. Trim stems at 45° angle before placing in water\n"
            "2. Use clean vase and fresh water daily\n"
            "3. Add flower food if provided\n"
            "4. Keep away from direct sunlight and heat\n"
            "5. Remove any submerged leaves\n\n"
            "Follow these tips to enjoy your flowers for 7-10 days!"
        )
    },
    "contact": {
        "question": "📞 Contact Information",
        "answer": (
            "📱 *Reach Us Anytime:*\n\n"
            f"• WhatsApp: {WHATSAPP_NUMBER}\n" 
            f"• Phone: {WHATSAPP_NUMBER}\n"
            "• Email: contact@prostoflowers.com\n"
            "• Store: Al Rutab St, Al Nahyan, Abu Dhabi - UAE\n"
            "•https://maps.app.goo.gl/sz2fChViqh7q2zTAA \n\n"
            "We're available 10 AM - 10 PM daily!"
        )
    }
}

def normalize_tag(tag):
    """Normalize tags for consistent matching"""
    return tag.lower().strip().replace(" ", "").replace("-", "").replace("'", "")
# Shopify GraphQL helper with SSL fix
def shopify_graphql_query(query, variables=None):
    if not SHOPIFY_ENABLED:
        return None
        
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": SHOPIFY_STOREFRONT_TOKEN
    }
    payload = {'query': query}
    if variables:
        payload['variables'] = variables
        
    try:
        # Get the path to certifi's CA bundle
        ca_bundle = certifi.where()
        
        response = requests.post(
            SHOPIFY_GRAPHQL_URL,
            json=payload,
            headers=headers,
            timeout=10,
            verify=ca_bundle  # Use the CA bundle path directly
        )
        
        # Log detailed error information
        if response.status_code != 200:
            logger.error(f"Shopify API error: {response.status_code} {response.reason}")
            logger.error(f"Request URL: {response.url}")
            
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Shopify API request failed: {e}")
        if hasattr(e, 'response') and e.response:
            try:
                logger.error(f"Response content: {e.response.text[:500]}")
            except:
                logger.error("Could not extract response text")
        return None

    
# DONT TOUCH
def get_shopify_product(handle):
    if not SHOPIFY_ENABLED:
        return None
        
    query = f"""
    {{
        products(first: 1, query: "handle:\\"{handle}\\"") {{
            edges {{
                node {{
                    id
                    title
                    handle
                    description
                    featuredImage {{
                        url
                    }}
                    onlineStoreUrl
                    variants(first: 1) {{
                        edges {{
                            node {{
                                price
                            }}
                        }}
                    }}
                }}
            }}
        }}
    }}
    """
    variables = {'handle': f'"{handle}"'}
    try:
        data = shopify_graphql_query(query, variables)
        # Enhanced error handling
        if not data:
            logger.error(f"No data received for handle: {handle}")
            return None
            
        if 'errors' in data:
            logger.error(f"GraphQL errors for handle {handle}: {data['errors']}")
            return None
            
        # Check for valid product structure
        if 'data' not in data or not data['data'].get('products'):
            logger.error(f"Products field missing in response for handle: {handle}")
            return None
            
        products = data['data']['products']['edges']
        if not products:
            logger.error(f"No product found for handle: {handle}")
            return None
            
        product = products[0]['node']
        product['handle'] = handle  # Ensure handle exists in response
        return product
        
    except Exception as e:
        logger.error(f"Error fetching product: {e}")
        return None
# Instagram URL
def get_instagram_url():
    return f"https://www.instagram.com/{INSTAGRAM_USERNAME}/"

# WhatsApp URL generator
def get_whatsapp_url(product_title=None):
    base_url = f"https://wa.me/{WHATSAPP_NUMBER}?text="
    message = "Hello%20Florist!%20I'm%20interested%20in%20"
    
    if product_title:
        # Clean product title for URL
        clean_title = product_title.replace(' ', '%20').replace('&', '%26')
        message += f"the%20'{clean_title}'%20bouquet.%20"
    
    message += "Could%20you%20tell%20me%20more%20about%20it?"
    return base_url + message

async def test_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not SHOPIFY_ENABLED:
        await update.message.reply_text("Shopify disabled")
        return
        
    handle = context.args[0] if context.args else "test-handle"
    product = get_shopify_product(handle)
    
    if product:
        message = (
            f"✅ Found product: {product['title']}\n"
            f"Handle: {product['handle']}\n"
            f"Status: {product.get('status')}\n"
            f"Published: {product.get('publishedOnCurrentPublication')}\n"
            f"URL: {product.get('onlineStoreUrl')}"
        )
    else:
        message = "❌ Product not found"
        
    await update.message.reply_text(message)
# menu start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_message = (
        f"🌸 Welcome to Prosto Flowers, {user.first_name}! 🌸\n\n"
        "I'm your floral assistant! How can I help you today?\n\n"
        "Browse our collection by category:"
    )
    
    keyboard = [
        [InlineKeyboardButton("💰 Filter by Price", callback_data="category_price")],
        [InlineKeyboardButton("🎉 Filter by Occasion", callback_data="category_occasion")],
        [InlineKeyboardButton("🌷 Filter by Flower Type", callback_data="category_flowers")],
        [InlineKeyboardButton("💐 Show All Bouquets", callback_data="show_all")],
        [
            InlineKeyboardButton("📸 Instagram", url=get_instagram_url()),
            InlineKeyboardButton("💬 WhatsApp", url=get_whatsapp_url())
        ],
        [InlineKeyboardButton("❓ FAQ", callback_data="faq_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

# FAQ Main Menu
async def faq_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for key, data in FAQ_DATA.items():
        keyboard.append([InlineKeyboardButton(data["question"], callback_data=f"faq_{key}")])
    
    # Add back button
    keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text="❓ *Frequently Asked Questions* ❓\n\nSelect a topic:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# FAQ Detail Handler
async def faq_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Extract FAQ key
    faq_key = query.data.split("_")[1]
    faq = FAQ_DATA.get(faq_key)
    
    if not faq:
        await query.edit_message_text(text="⚠️ Question not found")
        return
    
    # Create response with back buttons
    keyboard = [
        [InlineKeyboardButton("🔙 Back to FAQ", callback_data="faq_main")],
        [InlineKeyboardButton("💬 Contact Us", url=get_whatsapp_url())]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=f"*{faq['question']}*\n\n{faq['answer']}",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Category menus
async def category_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Cache products if not already cached
    await cache_products(context)
    
    # Extract category from callback data
    category_type = query.data.split("_")[1]
    
    # Define menu options
    menus = {
        "price": {
            "title": "💰 Select Price Range",
            "options": [
                ("Under AED50", "under50"),
                ("AED50-150", "50-150"),
                ("AED151-250", "151-250"),
                ("Over AED250", "over250")
            ]
        },
        "occasion": {
            "title": "🎉 Select Occasion",
            "options": [
                ("Anniversary", "anniversary"),
                ("Valentine", "valentine"),
                ("Romantic", "romantic"),
                ("Get Well Soon", "getwell"),
                ("Wedding", "wedding"),
                ("Happy Birthday", "birthday"),
                ("Father's Day", "fathersday")
            ]
        },
        "flowers": {
            "title": "🌷 Select Flower Type",
            "options": [
                ("Roses", "roses"),
                ("Lilies", "lilies"),
                ("Tulips", "tulips"),
                ("Orchids", "orchids"),
                ("Sunflowers", "sunflowers"),
                ("Mixed Flowers", "mixed")
            ]
        }
    }
    
    menu = menus.get(category_type)
    if not menu:
        await query.edit_message_text(text="⚠️ Invalid category selection")
        return
    
    keyboard = []
    for label, value in menu["options"]:
        keyboard.append([InlineKeyboardButton(label, callback_data=f"filter_{category_type}_{value}")])
    
    # Add back button
    keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=menu["title"],
        reply_markup=reply_markup
    )
def safe_callback_data(prefix, data):
    """Generate safe callback data within 64-byte limit"""
    max_length = 64 - len(prefix) - 1  # Reserve 1 byte for separator
    if len(data) <= max_length:
        return f"{prefix}_{data}"
    
    # Use hash for long data
    hash_id = hashlib.sha1(data.encode()).hexdigest()[:8]
    return f"{prefix}_{hash_id}"


def filter_products_by_tag(products, filter_value):  # Corrected: Only 2 parameters
    """Filter products using flexible tag matching"""
    if not products:
        return []
    
    # Get all possible tags for this filter
    possible_tags = TAG_MAPPINGS.get(filter_value, [filter_value])
    
    # Normalize tags for matching
    normalized_possible = [normalize_tag(t) for t in possible_tags]
    
    filtered = []
    for product in products:
        product_tags = product.get('tags', [])
        
        # Convert string to list if needed
        if isinstance(product_tags, str):
            product_tags = [t.strip() for t in product_tags.split(',')]
        
        # Normalize product tags
        normalized_product_tags = [normalize_tag(t) for t in product_tags]
        
        # Check for any match
        if any(tag in normalized_product_tags for tag in normalized_possible):
            filtered.append(product)
            
    return filtered

def get_all_products():
    """Fetch all active products using Admin API"""
    if not SHOPIFY_ENABLED:
        return []
    
    query = """
    {
        products(first: 250, query: "status:active") {
            edges {
                node {
                    id
                    handle
                    title
                    description
                    featuredImage {
                        url
                    }
                    onlineStoreUrl
                    tags
                    variants(first: 1) {
                        edges {
                            node {
                                price
                            }
                        }
                    }
                }
            }
        }
    }
    """
    
    try:
        data = shopify_graphql_query(query)
        if not data or 'data' not in data or 'products' not in data['data']:
            logger.error("Invalid response when fetching all products")
            return []
            
        products = []
        for edge in data['data']['products']['edges']:
            product = edge['node']
            # Ensure we have a price
            if product['variants']['edges']:
                product['price'] = product['variants']['edges'][0]['node']['price']
                products.append(product)
                
        return products
    except Exception as e:
        logger.error(f"Error fetching all products: {e}")
        return []

def filter_products_by_price(products, price_range):
    """Filter products by price range from pre-fetched list"""
    if not products or not price_range:
        return []
    
    price_mapping = {
        "under50": (0, 50),
        "50-150": (50, 150),
        "151-250": (151, 250),
        "over250": (251, float('inf'))
    }
    
    min_price, max_price = price_mapping.get(price_range, (0, float('inf')))
    
    filtered = []
    for p in products:
        try:
            price = float(p.get('price', 0))
            if min_price <= price <= max_price:
                filtered.append(p)
        except (TypeError, ValueError):
            continue
            
    return filtered

def get_shopify_products():
    if not SHOPIFY_ENABLED:
        return []
    
    query = """
    {
        products(first: 50) {
            edges {
                node {
                    id
                    handle
                    title
                    description
                    featuredImage {
                        url
                    }
                    onlineStoreUrl
                    publishedOnCurrentPublication
                    status
                    totalInventory
                    variants(first: 1) {
                        edges {
                            node {
                                price
                                inventoryQuantity
                            }
                        }
                    }
                }
            }
        }
    }
    """
    try:
        data = shopify_graphql_query(query)
        if not data or 'data' not in data or 'products' not in data['data']:
            logger.error("Invalid Shopify response structure")
            # Add detailed error logging
            if data and 'errors' in data:
                logger.error(f"GraphQL errors: {data['errors']}")
            return []
            
        valid_products = []
        for edge in data['data']['products']['edges']:
            product = edge['node']
            # Only include ACTIVE products with a store URL
            if product.get('status') == 'ACTIVE' and product.get('onlineStoreUrl'):
                valid_products.append(product)
            else:
                status = product.get('status', 'UNKNOWN')
                logger.warning(f"Skipping product: {product.get('title')} | Status: {status}")
                
        return valid_products
    except Exception as e:
        logger.error(f"Error fetching products: {e}")
        return []
async def products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not SHOPIFY_ENABLED:
        await update.message.reply_text("⚠️ Product browsing is currently unavailable. Please try again later.")
        return
    
    products = get_shopify_products()
    if not products:
        await update.message.reply_text("❌ Currently no products available. Please check back later!")
        return
    
    keyboard = []
    available_count = 0
    
    for product in products:
        # Use the data directly from the products list
        if not product.get('onlineStoreUrl') or product.get('status') != 'ACTIVE':
            logger.warning(f"Skipping unavailable product: {product['handle']}")
            continue
            
        title = product['title']
        handle = product['handle']
        keyboard.append([InlineKeyboardButton(title, callback_data=f"product_{handle}")])
        available_count += 1
    
    if available_count == 0:
        await update.message.reply_text("❌ No available products found. Please check back later!")
        return
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("✨ Our Available Bouquets ✨", reply_markup=reply_markup)

async def cache_products(context: ContextTypes.DEFAULT_TYPE):
    """Cache products in bot context for 10 minutes"""
    if not hasattr(context, 'cached_products') or not context.cached_products:
        context.cached_products = get_all_products()
        context.cache_time = time.time()
    # Refresh cache every 10 minutes
    elif time.time() - context.cache_time > 600:
        context.cached_products = get_all_products()
        context.cache_time = time.time()
    return context.cached_products

def escape_shopify_query(query_str):
    """Escape special characters for Shopify query strings"""
    # Escape backslashes first
    escaped = query_str.replace('\\', '\\\\')
    # Escape double quotes
    escaped = escaped.replace('"', '\\"')
    return escaped

# Get similar products by tags
def get_similar_products(current_handle, current_tags, limit=3):
    if not current_tags:
        logger.info("No tags available for similar products")
        return []
    
    # Escape each tag and format query
    escaped_tags = [escape_shopify_query(tag) for tag in current_tags]
    tag_query = " OR ".join([f'tag:"{tag}"' for tag in escaped_tags])
    
    # Admin API query
    query = """
    query getSimilarProducts($tagQuery: String!) {
        products(first: 5, query: $tagQuery) {
            edges {
                node {
                    id
                    handle
                    title
                    onlineStoreUrl
                    featuredImage {
                        url
                    }
                    status
                    publishedOnCurrentPublication
                }
            }
        }
    }
    """
    
    variables = {
        "tagQuery": tag_query
    }
    
    try:
        logger.info(f"Fetching similar products with query: {tag_query}")
        data = shopify_graphql_query(query, variables)
        if not data:
            logger.error("No data received for similar products")
            return []
            
        if 'errors' in data:
            logger.error(f"GraphQL errors in similar products: {json.dumps(data['errors'], indent=2)}")
            return []
            
        if 'data' not in data or 'products' not in data['data']:
            logger.error(f"Invalid similar products response: {json.dumps(data, indent=2)}")
            return []
            
        similar = []
        for edge in data['data']['products']['edges']:
            product = edge['node']
            # Only include ACTIVE, published products
            if (product['handle'] != current_handle and 
                product.get('status') == 'ACTIVE' and
                product.get('publishedOnCurrentPublication') and
                product.get('onlineStoreUrl')):
                similar.append(product)
                if len(similar) >= limit:
                    break
                    
        logger.info(f"Found {len(similar)} similar products")
        return similar
        
    except Exception as e:
        logger.error(f"Error fetching similar products: {e}", exc_info=True)
        return []

async def apply_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Cache products if not already cached
    products = await cache_products(context)
    
    # Extract filter details
    parts = query.data.split("_", 2)
    if len(parts) < 3:
        logger.error(f"Invalid callback data: {query.data}")
        await query.edit_message_text(text="⚠️ Invalid filter request")
        return
        
    _, category_type, filter_value = parts
    
    # Get filter label
    filter_labels = {
        "under50": "Under AED50",
        "50-150": "AED50-150",
        "151-250": "AED151-250",
        "over250": "Over AED250",
        "anniversary": "Anniversary",
        "valentine": "Valentine's Day",
        "romantic": "Romantic",
        "getwell": "Get Well Soon",
        "wedding": "Wedding",
        "birthday": "Birthday",
        "fathersday": "Father's Day",
        "roses": "Roses",
        "lilies": "Lilies",
        "tulips": "Tulips",
        "orchids": "Orchids",
        "sunflowers": "Sunflowers",
        "mixed": "Mixed Flowers"
    }
    filter_label = filter_labels.get(filter_value, filter_value)
    
    # Apply filters with flexible matching
    if category_type == "price":
        filtered_products = filter_products_by_price(products, filter_value)
    else:
        filtered_products = filter_products_by_tag(products, filter_value)
    # If no products found, try broader search
    # If still no products, show error message
    if not filtered_products:
        await query.edit_message_text(
            text=f"❌ No bouquets found in '{filter_label}' category\n\n"
                 "We're adding new arrangements daily! Please check back soon or browse other categories.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Categories", callback_data="back_to_main")]]
            )
        )
        return
    
    # Create product list
    keyboard = []
    for product in filtered_products:
        # Use ONLY the handle in callback data (64-byte limit)
        keyboard.append([
            InlineKeyboardButton(
                f"{product['title'][:25]} - AED{float(product.get('price', 0)):.2f}",
                callback_data=f"product_{product['handle']}"
            )
        ])
    
    # Add back buttons
    keyboard = []
    for product in filtered_products:
        # Generate safe callback data
        callback_data = safe_callback_data("product", product['handle'])
        
        # Create button with price info
        title = product['title'][:25] + "..." if len(product['title']) > 25 else product['title']
        try:
            price = float(product.get('price', 0))
            btn_text = f"{title} - AED{price:.2f}"
        except:
            btn_text = title
            
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=f"💐 Bouquets in '{filter_label}' category:",
        reply_markup=reply_markup
    )
# New function to get product with tags
def get_shopify_product_with_tags(handle):
    if not SHOPIFY_ENABLED:
        return None
        
    query = f"""
    {{
        products(first: 1, query: "handle:\\"{handle}\\"") {{
            edges {{
                node {{
                    id
                    title
                    handle
                    description
                    featuredImage {{
                        url
                    }}
                    onlineStoreUrl
                    tags
                    variants(first: 1) {{
                        edges {{
                            node {{
                                price
                            }}
                        }}
                    }}
                }}
            }}
        }}
    }}
    """
    
    try:
        data = shopify_graphql_query(query)
        if not data:
            logger.error("No data received from Shopify API")
            return None
            
        if 'errors' in data:
            logger.error(f"GraphQL errors: {json.dumps(data['errors'], indent=2)}")
            return None
            
        products = data['data']['products']['edges']
        if not products:
            logger.error(f"No product found for handle: {handle}")
            return None
            
        product = products[0]['node']
        product['handle'] = handle
        
        # Convert tags string to list
        if 'tags' in product and isinstance(product['tags'], str):
            product['tags'] = [tag.strip() for tag in product['tags'].split(',') if tag.strip()]
            
        return product
        
    except Exception as e:
        logger.error(f"Error fetching product: {e}")
        return None

# New handler for back to menu action
async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        # Try to delete the current message (product detail)
        await query.message.delete()
    except Exception as e:
        logger.warning(f"Couldn't delete message: {e}")
        # If deletion fails, just edit it instead
        try:
            await query.edit_message_text(text="Returning to menu...")
        except:
            pass
    
    # Resend the product list menu
    if not SHOPIFY_ENABLED:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="⚠️ Product browsing is currently unavailable."
        )
        return
    
    # Get fresh products list
    products_list = get_shopify_products()
    if not products_list:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="❌ Currently no products available."
        )
        return
    
    # Create product buttons
    keyboard = []
    for product in products_list:
        if not product.get('onlineStoreUrl'):
            continue
        title = product['title']
        handle = product['handle']
        keyboard.append([InlineKeyboardButton(title, callback_data=f"product_{handle}")])
    
    if not keyboard:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="❌ No available products found."
        )
        return
    
    # Create menu with back button
    keyboard.append([
        InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main"),
        InlineKeyboardButton("🔄 Refresh", callback_data="back_to_menu")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="✨ Our Available Bouquets ✨",
        reply_markup=reply_markup
    )

async def instagram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ig_url = get_instagram_url()
    keyboard = [[InlineKeyboardButton("📸 View Instagram", url=ig_url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🌸 *Our Instagram Gallery* 🌸\n\nSee our latest floral creations:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wa_url = get_whatsapp_url()
    keyboard = [[InlineKeyboardButton("💬 Chat on WhatsApp", url=wa_url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "💌 *Contact Us*\n\nWe're available on WhatsApp:\n",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    await update.message.reply_text(
        "💌 *Contact Us*\n\nWe're available on WhatsApp:\n",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

#DEBUG
async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not SHOPIFY_ENABLED:
        await update.message.reply_text("❌ Shopify integration disabled")
        return
        
    query = """
    {
        shop {
            name
        }
        products(first: 5) {
            edges {
                node {
                    id
                    handle
                    title
                    # UPDATED FIELDS FOR STOREFRONT API
                    onlineStoreUrl
                    availableForSale
                }
            }
        }
    }
    """
    
    try:
        data = shopify_graphql_query(query)
        if not data:
            await update.message.reply_text("⚠️ No response from Shopify API")
            return
            
        message = "🛠️ *Shopify Debug Information*\n\n"
        
        # Shop info
        if 'data' in data and 'shop' in data['data']:
            message += f"🏬 *Store Name:* {data['data']['shop']['name']}\n\n"
        
        # Products info
        if 'data' in data and 'products' in data['data']:
            products = data['data']['products']['edges']
            message += f"📦 *Products Found:* {len(products)}\n\n"
            
            for idx, edge in enumerate(products[:3]):  # Show first 3
                product = edge['node']
                message += (
                    f"*Product #{idx+1}*\n"
                    f"Title: {product['title']}\n"
                    f"Handle: `{product['handle']}`\n"
                    f"Published: {'✅' if product['publishedOnCurrentPublication'] else '❌'}\n"
                    f"Status: {product.get('status', 'N/A')}\n"
                    f"URL: {product.get('onlineStoreUrl', 'N/A')}\n\n"
                )
        else:
            message += "⚠️ No products found in response\n"
            
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Debug command failed: {e}")
        await update.message.reply_text(f"❌ Debug failed: {str(e)}")

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Reuse the start menu
    user = query.from_user
    welcome_message = (
        f"🌸 Welcome back, {user.first_name}! 🌸\n\n"
        "How can I help you today?\n\n"
        "Browse our collection by category:"
    )
    
    keyboard = [
        [InlineKeyboardButton("💰 Filter by Price", callback_data="category_price")],
        [InlineKeyboardButton("🎉 Filter by Occasion", callback_data="category_occasion")],
        [InlineKeyboardButton("🌷 Filter by Flower Type", callback_data="category_flowers")],
        [InlineKeyboardButton("💐 Show All Bouquets", callback_data="show_all")],
        [
            InlineKeyboardButton("📸 Instagram", url=get_instagram_url()),
            InlineKeyboardButton("💬 WhatsApp", url=get_whatsapp_url())
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=welcome_message, reply_markup=reply_markup)

# Handler for "Show All Bouquets"
async def show_all_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Cache products if not already cached
    products = await cache_products(context)
    
    if not products:
        await query.edit_message_text(text="❌ Currently no products available.")
        return
    
    # Create product list
    keyboard = []
    for product in products:
        # Generate safe callback data
        callback_data = safe_callback_data("product", product['handle'])
        
        # Create button with price info
        title = product['title'][:25] + "..." if len(product['title']) > 25 else product['title']
        try:
            price = float(product.get('price', 0))
            btn_text = f"{title} - AED{price:.2f}"
        except:
            btn_text = title
            
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])
    
    # Add back button
    keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text="✨ All Available Bouquets ✨",
        reply_markup=reply_markup
    )
async def product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not SHOPIFY_ENABLED:
        await update.callback_query.answer("⚠️ Product details unavailable", show_alert=True)
        return
        
    query = update.callback_query
    await query.answer()
    
    # Extract handle safely
    if '_' not in query.data:
        logger.error(f"Invalid callback data: {query.data}")
        await query.edit_message_text(text="⚠️ Invalid product request")
        return
        
    handle = query.data.split('_', 1)[1]  # Split only on first underscore
    logger.info(f"Fetching product with handle: {handle}")
    
    # Get product with tags
    product = get_shopify_product_with_tags(handle)
    if not product:
        await query.edit_message_text(text="⚠️ Product not found in our system")
        return
        
    # Format message
    title = product['title']
    description = product.get('description', 'No description available')
    price = product['variants']['edges'][0]['node']['price']
    image_url = product.get('featuredImage', {}).get('url') if product.get('featuredImage') else None
    tags = product.get('tags', [])
    
    callback_data = query.data
    if '_' not in callback_data:
        logger.error(f"Invalid callback data: {callback_data}")
        await query.edit_message_text(text="⚠️ Invalid product request")
        return
        
    prefix, data = callback_data.split('_', 1)
    
    # Handle hashed handles
    if len(data) == 8:  # SHA1 hash length
        # Find product by hash match
        product = None
        for p in await cache_products(context):
            if hashlib.sha1(p['handle'].encode()).hexdigest()[:8] == data:
                product = p
                break
    else:
        # Regular handle lookup
        product = next((p for p in await cache_products(context) if p['handle'] == data), None)
    
    if not product:
        await query.edit_message_text(text="⚠️ Product not found in our system")
        return

    # Use the actual store URL if available
    product_url = product.get('onlineStoreUrl', f"https://{SHOPIFY_STORE}.myshopify.com/products/{handle}")
    
    # Generate WhatsApp URL with product title
    whatsapp_url = get_whatsapp_url(title)
    
    # Create inline keyboard with action buttons
    keyboard = [
        [
            InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu"),
            InlineKeyboardButton("🛒 Order Now", url=product_url)
        ],
        [
            InlineKeyboardButton("📸 Order via Instagram", url=get_instagram_url()),
            InlineKeyboardButton("💬 Order via WhatsApp", url=whatsapp_url)
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        f"💐 *{title}* 💐\n\n"
        f"{description}\n\n"
        f"*Price:* AED{price}\n\n"
        f"[View on our website]({product_url})"
    )
    
    try:
        if image_url:
            # Send as new message with photo
            sent_message = await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=image_url,
                caption=message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            # Send as new message without photo
            sent_message = await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        # Delete the original product list message
        await query.message.delete()
        
        # Add similar products section if available
        if tags:
            similar_products = get_similar_products(handle, tags, limit=3)
            if similar_products:
                similar_message = "🌸 *You Might Also Like* 🌸\n\n"
                similar_keyboard = []
                
                for prod in similar_products:
                    # Use URL-safe product title for button text
                    short_title = prod['title'][:20] + "..." if len(prod['title']) > 20 else prod['title']
                    similar_message += f"• [{prod['title']}]({prod['onlineStoreUrl']})\n"
                    similar_keyboard.append(
                        [InlineKeyboardButton(
                            f"🌷 {short_title}", 
                            callback_data=f"product_{prod['handle']}"
                        )]
                    )
                
                # Add navigation button
                similar_keyboard.append(
                    [InlineKeyboardButton("🔙 Back to All Products", callback_data="back_to_menu")]
                )
                
                similar_reply_markup = InlineKeyboardMarkup(similar_keyboard)
                
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=similar_message,
                    parse_mode='Markdown',
                    reply_markup=similar_reply_markup,
                    disable_web_page_preview=True
                )
        
    except Exception as e:
        logger.error(f"Failed to send product details: {e}")
        # Fallback: Edit the existing message
        try:
            await query.edit_message_text(
                text=message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except Exception as e2:
            logger.error(f"Failed to edit message: {e2}")
            await query.edit_message_text(text="⚠️ Failed to load product details. Please try again later.")

def main():
    try:
        # Create the Application
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Command handlers
        application.add_handler(CommandHandler("start", start))
        
        # Callback handlers
        application.add_handler(CallbackQueryHandler(category_menu, pattern=r"^category_"))
        application.add_handler(CallbackQueryHandler(apply_filter, pattern=r"^filter_"))
        application.add_handler(CallbackQueryHandler(back_to_main, pattern=r"^back_to_main$"))
        application.add_handler(CallbackQueryHandler(show_all_products, pattern=r"^show_all$"))
        application.add_handler(CallbackQueryHandler(back_to_menu, pattern=r"^back_to_menu$"))
        application.add_handler(CallbackQueryHandler(faq_main, pattern=r"^faq_main$"))
        application.add_handler(CallbackQueryHandler(faq_detail, pattern=r"^faq_"))
        
        if SHOPIFY_ENABLED:
            application.add_handler(CommandHandler("products", products))
            application.add_handler(CallbackQueryHandler(product_detail, pattern=r"^product_"))
            application.add_handler(CallbackQueryHandler(show_all_products, pattern=r"^show_all$"))
        
        application.add_handler(CommandHandler("instagram", instagram))
        application.add_handler(CommandHandler("contact", contact))
        
        # Start bot
        logger.info("🌸 Flower Shop Bot is now blooming! 🌸")
        application.run_polling()
        
    except Exception as e:
        logger.error(f"🚨 Bot startup failed: {e}")

if __name__ == '__main__':
    main()