import scrapy
import re
from scrapy_playwright.page import PageMethod
from gifty_scraper.base_spider import GiftyBaseSpider
from gifty_scraper.items import CategoryItem


class KassirSpider(GiftyBaseSpider):
    name = "kassir"
    allowed_domains = ["kassir.ru", "fg.kassir.ru"]
    site_key = "kassir"
    
    # Discovery patterns for Kassir.ru
    category_selector = 'nav a[href*="/bilety-na-"], nav a[href*="/bilety-v-"], .header__menu a[href*="/bilety-"]'

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_HANDLERS': {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        'TWISTED_REACTOR': "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 60000,
        'PLAYWRIGHT_LAUNCH_OPTIONS': {
            "headless": True, # Keep headless for now, but we can try False if needed locally
        },
        'PLAYWRIGHT_CONTEXT_ARGS': {
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        },
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    }

    def start_requests(self):
        # Use starting URL from kwargs or default to concerts
        url = getattr(self, 'url', "https://msk.kassir.ru/bilety-na-koncert")
        
        urls = [url]
        if not url and self.strategy == "discovery":
             urls = ["https://msk.kassir.ru/"]

        for u in urls:
            yield scrapy.Request(
                u,
                callback=self.parse,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_timeout", 5000), # Wait for potential redirect to settle
                        PageMethod("wait_for_selector", ".event-card, article[class*='event-card'], .event-item", timeout=20000),
                    ],
                },
                errback=self.errback_close_page,
            )

    async def errback_close_page(self, failure):
        page = failure.request.meta.get("playwright_page")
        if page:
            await page.close()

    def parse_discovery(self, response):
        """
        Extracts category links (Concerts, Theatre, etc.) from the header.
        """
        self.logger.info("Starting discovery on: %s", response.url)
        links = response.css(self.category_selector)
        seen = set()
        
        for link in links:
            url = response.urljoin(link.css('::attr(href)').get())
            name = link.css('::text').get()
            if url and url not in seen and '/bilety-' in url:
                seen.add(url)
                yield CategoryItem(
                    name=name.strip() if name else "Category",
                    url=url,
                    parent_url=response.url,
                    site_key=self.site_key
                )
        
        # Fallback if discovery fails due to structure changes
        if not seen:
            self.logger.warning("No category links found via CSS. Trying fallback links.")
            fallbacks = [
                "/bilety-na-koncert", "/bilety-v-teatr", "/bilety-na-sport", 
                "/bilety-v-tsirk", "/bilety-v-muzey", "/bilety-na-stendap"
            ]
            for path in fallbacks:
                url = response.urljoin(path)
                yield CategoryItem(
                    name=path.replace("/bilety-", "").replace("-", " ").title(),
                    url=url,
                    parent_url=response.url,
                    site_key=self.site_key
                )

    def parse_catalog(self, response):
        """
        Parses event cards from a listing page.
        """
        self.logger.info(f"Parsing catalog: {response.url}")
        
        # City extraction
        city_match = re.search(r'https?://([^.]+)\.kassir\.ru', response.url)
        city_slug = city_match.group(1) if city_match else "msk"
        city_names = {
            "msk": "Москва", "spb": "Санкт-Петербург", "sochi": "Сочи",
            "ekb": "Екатеринбург", "nn": "Нижний Новгород", "kzn": "Казань"
        }
        city = city_names.get(city_slug, city_slug.upper())

        # Event cards
        cards = response.css('.event-card, article[class*="event-card"], .event-item')
        
        if not cards:
            self.logger.warning(f"No event cards found on {response.url}")
            return

        for card in cards:
            # Title
            title = card.css('.event-card__title::text').get() or \
                    card.css('[class*="title"]::text').get() or \
                    card.xpath('.//h3//text()').get()
            
            # URL
            url = card.css('a::attr(href)').get()
            if not url and title:
                 # Try to get from title link
                 url = card.css('a[class*="title"]::attr(href)').get()
            
            # Price range (e.g., "от 1000 ₽" or "1000 — 5000 ₽")
            price_text = card.css('.event-card__price::text').get() or \
                         card.css('[class*="price"]::text').get()
            
            # Image
            image = card.css('.event-card__image img::attr(src)').get() or \
                    card.css('img::attr(src)').get() or \
                    card.css('.image-wrapper img::attr(src)').get()
            
            # Venue
            venue = card.css('.event-card__venue::text').get() or \
                    card.css('[class*="venue"]::text').get() or \
                    card.css('.venue::text').get()

            if not title or not url:
                continue

            # Parse numeric minimum price for schema consistency
            min_price = None
            if price_text:
                price_digits = re.findall(r'(\d[\d\s]*)', price_text)
                if price_digits:
                    min_price = price_digits[0].replace(" ", "").replace("\u00a0", "").strip()

            yield self.create_product(
                title=title.strip(),
                product_url=response.urljoin(url),
                price=min_price,
                image_url=response.urljoin(image) if image else None,
                merchant="Kassir.ru",
                raw_data={
                    "source": "scrapy_playwright",
                    "city": city,
                    "price_range": price_text.strip() if price_text else None,
                    "venue": venue.strip() if venue else None
                }
            )

        # Pagination: "Load more" or numeric pages
        next_page = response.css('a.pagination__next::attr(href)').get() or \
                    response.xpath('//a[contains(@class, "next")]/@href').get()
        
        if next_page:
            yield response.follow(
                next_page, 
                self.parse_catalog,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_methods": [
                        {"method": "wait_for_selector", "args": [".event-card", {"timeout": 10000}]},
                    ],
                }
            )
