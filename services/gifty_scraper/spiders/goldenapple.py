import scrapy
import re
import json
from scrapy_playwright.page import PageMethod
from gifty_scraper.base_spider import GiftyBaseSpider
from gifty_scraper.items import CategoryItem

class GoldAppleSpider(GiftyBaseSpider):
    name = "goldenapple"
    allowed_domains = ["goldapple.ru"]
    site_key = "goldenapple"


    category_selector = 'a[href^="/catalog/"]'

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": True,
        },
        "PLAYWRIGHT_CONTEXT_ARGS": {
            "viewport": {"width": 375, "height": 812},
            "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            "is_mobile": True,
            "has_touch": True,
        },
        "USER_AGENT": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
        },
    }

    def start_requests(self):
        if not self.url:
            self.url = "https://goldapple.ru/makijazh"
        
        self.logger.info("Initializing GA session (Homepage -> Category)...")
        yield scrapy.Request(
            "https://goldapple.ru/",
            callback=self.parse_rendered,
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    PageMethod("wait_for_timeout", 5000),
                    PageMethod("goto", self.url),
                    PageMethod("wait_for_timeout", 15000),
                    PageMethod("content"),
                ],
            },
            dont_filter=True
        )


    async def parse_rendered(self, response):
        """
        Called after Playwright renders the page. Gets the fully rendered HTML
        via page.content() so we can parse JS-rendered product data.
        """
        page = response.meta.get("playwright_page")
        if page:
            rendered_html = await page.content()
            await page.close()
            rendered_response = response.replace(body=rendered_html.encode("utf-8"))
            for item in self.parse(rendered_response):
                yield item
        else:
            for item in self.parse(response):
                yield item

    # --------------------------------------------------
    # Discovery (categories)
    # --------------------------------------------------
    def parse_discovery(self, response):
        links = response.css(self.category_selector)
        seen = set()

        for link in links:
            url = response.urljoin(link.css("::attr(href)").get())
            if not url or url in seen or url == response.url:
                continue
            seen.add(url)

            name = link.xpath(".//text()").get()
            name = name.strip() if name else None

            yield CategoryItem(
                name=name,
                title=name,
                url=url,
                parent_url=response.url,
                site_key=self.site_key,
            )

    # --------------------------------------------------
    # Catalog
    # --------------------------------------------------
    def parse_catalog(self, response):
        self.logger.info(f"Parsing GoldApple catalog: {response.url}")

        # Extract the initial JSON state
        state = self._extract_initial_state(response)
        if not state:
            self.logger.warning("GoldApple: __INITIAL_STATE__ not found")
            return

        products = state.get("catalog", {}).get("data", {}).get("items", [])
        if not products:
            self.logger.warning("GoldApple: no products extracted from state")
            return

        # Iterate over products
        for product in products:
            title = product.get("name")
            brand = product.get("brand", {}).get("name")
            full_title = f"{brand} {title}".strip() if brand else title

            slug = product.get("url") or product.get("slug")
            price = self._extract_price(product)
            image = self._extract_image(product)

            if not full_title or not slug:
                continue

            yield self.create_product(
                title=full_title,
                product_url=response.urljoin(slug),
                price=price,
                image_url=image,
                merchant="GoldApple",
                raw_data={
                    "source": "json_state",
                    "product_id": product.get("id"),
                },
            )

        # Pagination
        if self.strategy in ["deep", "discovery"]:
            for next_request in self._paginate(response, state):
                yield next_request

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    def _extract_initial_state(self, response):
        """Extract JSON __INITIAL_STATE__ safely from page source."""
        # This regex might need tuning if GoldApple changes their frontend
        match = re.search(r"window\.__INITIAL_STATE__\s*=\s*({.*?});", response.text, re.DOTALL)
        if not match:
            # Debug: log first 500 chars to see what we actually got
            self.logger.info(f"Regex failed. Response preview: {response.text[:1000]}")
            return None
        try:
            return json.loads(match.group(1))
        except Exception as e:
            self.logger.debug(f"GoldApple: failed to parse INITIAL_STATE: {e}")
            return None

    def _extract_price(self, product):
        price_data = product.get("price", {})
        # Price structure varies: ensure we get the actual value
        price = price_data.get("actual", {}).get("amount")
        if price is None:
             price = price_data.get("value")
        
        return float(price) if price else None

    def _extract_image(self, product):
        images = product.get("image", [])
        if not images:
             return None
        # Return first image URL, ensuring it's absolute if needed
        return images[0].get("url")

    def _paginate(self, response, state):
        # Implement pagination based on state or next page link
        # This is a placeholder logic
        meta = state.get("catalog", {}).get("meta", {})
        current_page = meta.get("current_page", 1)
        last_page = meta.get("last_page", 1)

        if current_page < last_page:
            next_page = current_page + 1
            # Assuming URL parameter logic ?p=2
            yield response.follow(
                f"{response.url.split('?')[0]}?p={next_page}", 
                callback=self.parse_catalog
            )


    def parse(self, response):
        # Entry point router
        # GoldenApple uses /makijazh, /parfyumeriya etc without "catalog" in URL
        # Check if page has __INITIAL_STATE__ with catalog data
        if "window.__INITIAL_STATE__" in response.text:
            yield from self.parse_catalog(response)
        else:
            yield from self.parse_discovery(response)