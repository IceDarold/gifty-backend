# Scrapy settings for gifty_scraper project

BOT_NAME = "gifty_scraper"

SPIDER_MODULES = ["gifty_scraper.spiders"]
NEWSPIDER_MODULE = "gifty_scraper.spiders"

ADDONS = {}

# Crawl responsibly
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"

ROBOTSTXT_OBEY = False

CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_DELAY = 1.5
RANDOMIZE_DOWNLOAD_DELAY = True

COOKIES_ENABLED = True

DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

RETRY_ENABLED = True
RETRY_TIMES = 5
RETRY_HTTP_CODES = [500, 502, 503, 504, 400, 403, 408, 429]

ITEM_PIPELINES = {
    "gifty_scraper.pipelines.IngestionPipeline": 300,
}

FEED_EXPORT_ENCODING = "utf-8"

# Playwright Settings
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
}

PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30000

def should_abort_request(request):
    """Optimization: block some requests in Playwright"""
    if request.resource_type in ["image", "media", "font", "stylesheet"]:
        return True
    
    blocked_domains = [
        "google-analytics.com",
        "yandex.ru",
        "mc.yandex",
        "facebook.net",
        "doubleclick.net",
        "bidswitch.net",
        "usedesk.ru",
        "sbermarketing.ru",
        "vk.com",
    ]
    if any(domain in request.url for domain in blocked_domains):
        return True
    
    return False

PLAYWRIGHT_ABORT_REQUEST = should_abort_request
