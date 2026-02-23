import scrapy
import re
from scrapy_playwright.page import PageMethod
from gifty_scraper.base_spider import GiftyBaseSpider


class LetuSpider(GiftyBaseSpider):
    name = "letu"
    allowed_domains = ["www.letu.ru", "letu.ru"]
    site_key = "letu"
    
    # Default category discovery selector
    category_selector = 'a[data-testid="category-card-link"], .f-menu a[href*="/browse/"], .footer__item a[href*="/browse/"]'

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_HANDLERS': {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        'TWISTED_REACTOR': "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 60000,
        'PLAYWRIGHT_LAUNCH_OPTIONS': {
            "headless": True,
        },
        'PLAYWRIGHT_CONTEXT_ARGS': {
            "viewport": {"width": 375, "height": 812},
            "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
            "is_mobile": True,
            "has_touch": True,
        },
        'DOWNLOAD_DELAY': 3.0,
        'USER_AGENT': "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
        'DEFAULT_REQUEST_HEADERS': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Upgrade-Insecure-Requests': '1',
            'Accept-Encoding': 'gzip, deflate, br',
        },
        'COOKIES_ENABLED': True
    }

    def start_requests(self):
        if not self.url:
             self.url = "https://www.letu.ru/browse/makiyazh"
             
        self.logger.info("Initializing session via Playwright (HP -> Category)...")
        yield scrapy.Request(
            "https://www.letu.ru/",
            callback=self.parse_rendered,
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    PageMethod("wait_for_timeout", 5000),
                    PageMethod("goto", self.url),
                    PageMethod("wait_for_selector", ".re-product-tile, .product-tile", timeout=30000),
                    PageMethod("content"),
                ],
            },
            dont_filter=True
        )



    async def parse_rendered(self, response):
        """
        Called after Playwright renders the page. Uses the rendered HTML content
        from PageMethod('content') to parse product tiles.
        """
        page = response.meta.get("playwright_page")
        if page:
            rendered_html = await page.content()
            await page.close()
            # Replace response body with rendered content
            rendered_response = response.replace(body=rendered_html.encode("utf-8"))
            for item in self.parse_catalog(rendered_response):
                yield item
        else:
            for item in self.parse_catalog(response):
                yield item

    def parse_discovery(self, response):
        """
        Parse hub pages to find category links.
        """
        links = response.css(self.category_selector)
        seen = set()

        for link in links:
            url = response.urljoin(link.css("::attr(href)").get())
            if not url or url in seen or url == response.url:
                continue
            seen.add(url)

            name = link.css("::text").get() or link.css("span::text").get()
            if name:
                 name = name.strip()

            yield self.create_category(url=url, name=name)

    def parse_catalog(self, response):
        """
        Parses the catalog page for Letu.ru using SSR-rendered content.
        """
        # 1. Product cards extraction
        cards = response.css('.re-product-tile, .product-tile')
        self.logger.info(f"Catalog {response.url}: found {len(cards)} products.")
        
        if not cards:
            self.logger.warning(f"No product cards found on {response.url}. The site might be blocking or requiring a real browser.")

        for i, card in enumerate(cards):
            # Brand and Title
            brand_list = card.css('[data-at-product-tile-brand]::text').getall() or \
                         card.css('.re-product-tile-name__text--brand::text').getall() or \
                         card.css('.product-tile-name__text--brand::text').getall()
            brand = " ".join([b.strip() for b in brand_list if b.strip()]).strip()
            
            title_list = card.css('[data-at-product-tile-title]::text').getall()
            title_part = " ".join([t.strip() for t in title_list if t.strip()]).strip()
            
            full_title = ""
            if brand:
                full_title += brand + " "
            if title_part:
                full_title += title_part
            
            # URL
            url = card.css('a.re-product-tile__item-container::attr(href)').get() or \
                  card.css('a.product-tile__item-container::attr(href)').get() or \
                  card.css('a::attr(href)').get()
            
            # Fallback for URL if href is missing (ID-based)
            if not url:
                item_id = card.css('a.re-product-tile__item-container::attr(data-at-product-list-item)').get() or \
                          card.css('[data-at-product-list-item]::attr(data-at-product-list-item)').get()
                if item_id:
                    url = f"/product/{item_id}"
            
            if not full_title or not url:
                continue

            # Price
            price_text = card.css('.re-product-tile-price__text--actual::text').get() or \
                         card.css('.product-tile-price__text--actual::text').get() or \
                         card.css('.product-tile-price__text::text').get()
            
            current_price = None
            if price_text:
                price_match = re.search(r'([\d\s\xa0]+)', price_text)
                if price_match:
                    current_price = price_match.group(1).replace(" ", "").replace("\xa0", "").replace("\u00a0", "").strip()

            # Image
            image = card.css('img.le-lazy-image-v2__image::attr(src)').get() or \
                    card.css('img.le-lazy-image__image::attr(src)').get() or \
                    card.css('img::attr(src)').get()

            yield self.create_product(
                title=full_title.strip(),
                product_url=response.urljoin(url),
                price=current_price,
                image_url=response.urljoin(image) if image else None,
                merchant="Л'Этуаль",
                raw_data={
                    "source": "scrapy_playwright_v1"
                }
            )

        # 2. Pagination
        if self.strategy == "deep":
            # Traditional pagination link
            next_page = response.css('.le-pagination__item--next a::attr(href)').get() or \
                        response.css('link[rel="next"]::attr(href)').get()
            
            if next_page:
                next_page_url = response.urljoin(next_page)
                if next_page_url != response.url:
                    self.logger.info(f"Following next page: {next_page_url}")
                    yield scrapy.Request(
                        next_page_url, 
                        callback=self.parse_rendered,
                        meta={
                            "playwright": True,
                            "playwright_include_page": True,
                            "playwright_page_methods": [
                                PageMethod("wait_for_timeout", 10000),
                            ],
                        }
                    )
