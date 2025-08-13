# Prosto-Flowers-Shop-Telegram-Bot
A feature-rich Telegram bot for Prosto Flowers, enabling customers to browse bouquets by price, occasion, or flower type. Integrates with Shopify for real-time product listings, provides detailed product information, and facilitates orders via WhatsApp, Instagram, or website. Includes FAQ section, delivery information, and flower care tips.


# Prosto Flowers Telegram Bot 🌸

A comprehensive Telegram bot for Prosto Flowers, designed to enhance customer experience by providing easy access to product information, ordering options, and frequently asked questions.

## Features ✨

- **Product Browsing**: Filter bouquets by price range, occasion, or flower type
- **Shopify Integration**: Real-time product data sync with Shopify store
- **Multi-channel Ordering**: Order via WhatsApp, Instagram, or website
- **FAQ Section**: Answers to common questions about delivery, payment, and flower care
- **Responsive Design**: Optimized for both mobile and desktop Telegram clients
- **Smart Product Recommendations**: Shows similar bouquets based on tags

## Technical Stack 💻

- Python 3.x
- python-telegram-bot library
- Shopify Storefront GraphQL API
- python-dotenv for configuration
- Requests for API calls
- Certifi for SSL verification

## Setup Instructions 🛠️

1. Clone the repository:
   ```bash
   #   git clone https://github.com/yourusername/prosto-flowers-bot.git
   #cd prosto-flowers-bot
  2. Install dependencies:
   #pip install -r requirements.txt
3. Create a .env file with your configuration:
TELEGRAM_TOKEN=your_telegram_bot_token
SHOPIFY_STORE=your-store-name
SHOPIFY_STOREFRONT_TOKEN=your_storefront_access_token / or ADMIN API 
INSTAGRAM_USERNAME=your_instagram_handle
WHATSAPP_NUMBER=
   
