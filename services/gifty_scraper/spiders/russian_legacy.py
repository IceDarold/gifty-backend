import scrapy
import re
from gifty_scraper.base_spider import GiftyBaseSpider
from gifty_scraper.items import CategoryItem


class RussianLegacySpider(GiftyBaseSpider):
    """
    Scraper for russianlegacy.com.
    """
    name = "russianlegacy"
    allowed_domains = ["russianlegacy.com"]
    site_key = "russianlegacy"
    category_selector = '#top-categories-menu li a.cat'

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'DEFAULT_REQUEST_HEADERS': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Upgrade-Insecure-Requests': '1',
        },
        'DOWNLOAD_DELAY': 1.0,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
    }

    def parse_discovery(self, response):
        """
        Parses the home page or category hub to find all category links.
        """
        self.logger.info(f"Discovery: Parsing categories from {response.url}")
        
        # Select all category links from the top menu
        categories = response.css(self.category_selector)
        
        for category in categories:
            url = response.urljoin(category.css('::attr(href)').get())
            name = category.css('::text').get()
            
            if url and name:
                # If we are just doing discovery, yield the category info
                if self.strategy == "discovery":
                    yield {
                        "name": name.strip(),
                        "title": name.strip(),
                        "product_url": url,
                        "image_url": None,
                        "price": "0.00",
                        "site_key": self.site_key
                    }
                else:
                    # If we are in deep mode, follow the category link to get products
                    yield response.follow(url, self.parse_catalog)

    def parse_catalog(self, response):
        """
        Parses the product listing page.
        """
        self.logger.info(f"Parsing catalog: {response.url}")
        
        # 1. Yield products from current page
        cards = response.css('div.product-item')
        for card in cards:
            title = card.css('div.name a::text').get() or card.css('div.img img::attr(alt)').get()
            url = card.css('div.img a::attr(href)').get() or card.css('div.name a::attr(href)').get()
            
            # Price extraction
            price_text = card.css('span.regular-price::text').get() or \
                         card.css('span.price::text').get() or \
                         card.css('div.price::text').get()
            
            current_price = "0.00"
            if price_text:
                price_match = re.search(r'([\d,.]+)', price_text)
                if price_match:
                    current_price = price_match.group(1).replace(',', '').strip()
            
            image = card.css('div.img img::attr(src)').get() or \
                    card.css('div.img img::attr(data-src)').get()
            
            if title and url:
                yield self.create_product(
                    title=title.strip(),
                    product_url=response.urljoin(url),
                    price=current_price,
                    image_url=response.urljoin(image) if image else None,
                    merchant="Russian Legacy",
                    raw_data={
                        "source": "scrapy_v1",
                        "catalog_id": card.attrib.get('data-catalogid')
                    }
                )

        # 2. Yield subcategories/category links to crawl deeper
        # We ALWAYS check for discovery links if we are NOT in discovery strategy mode
        # (This allows us to find the menu on the home page even if featured products are present)
        if self.strategy != "discovery":
            yield from self.parse_discovery(response)

        # 3. Handle Pagination (Next Page)
        if self.strategy in ["deep", "discovery"]:
            next_page = response.xpath('//a[contains(text(), "Next Page")]/@href').get() or \
                        response.css('link[rel="next"]::attr(href)').get()
            
            if next_page:
                self.logger.info(f"Following next page: {next_page}")
                yield response.follow(next_page, self.parse_catalog)
