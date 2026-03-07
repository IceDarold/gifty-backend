import scrapy
import re
from gifty_scraper.base_spider import GiftyBaseSpider


class PichShopSpider(GiftyBaseSpider):
    """
    Scraper for pichshop.ru.
    """
    name = "pichshop"
    allowed_domains = ["pichshop.ru"]
    site_key = "pichshop"
    category_selector = 'a[href*="/catalog/"]'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'DEFAULT_REQUEST_HEADERS': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US,en;q=0.8',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.google.com/',
        },
        'DOWNLOAD_TIMEOUT': 30,
        'DOWNLOAD_DELAY': 1.0,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'COOKIES_ENABLED': True,
    }

    def parse_discovery(self, response):
        """
        Parses the home page to find all category links.
        """
        self.logger.info(f"Discovery: Parsing categories from {response.url}")
        
        # Select category links using the defined selector
        links = response.css(self.category_selector)
        
        found_urls = set()
        for link in links:
            url = response.urljoin(link.css('::attr(href)').get())
            name = link.css('::text').get()
            
            if url and name and "/catalog/" in url and url not in found_urls:
                name = name.strip()
                if not name or len(name) < 2:
                    continue
                
                # Exclude obvious non-category or static links
                if any(x in url for x in ['/sale/', '/hit/', '/novinki/', '/gift/']):
                    # We still want these, but usually we prefer broad categories
                    pass
                
                found_urls.add(url)
                
                if self.strategy == "discovery":
                    yield {
                        "name": name,
                        "title": name,
                        "product_url": url,
                        "image_url": None,
                        "price": "0.00",
                        "site_key": self.site_key
                    }
                else:
                    self.logger.debug(f"Discovery: Following category {name} -> {url}")
                    yield response.follow(url, self.parse_catalog)

    def parse_catalog(self, response):
        """
        Parses the product listing page.
        """
        self.logger.info(f"Parsing catalog: {response.url}")
        
        # 1. Yield products from current page
        cards = response.css('div.product-card')
        for card in cards:
            title = card.attrib.get('data-name') or card.css('.product-card__name::text').get()
            url = card.css('a.product-card__img::attr(href)').get()
            
            # Price extraction
            price_text = card.attrib.get('data-price')
            current_price = "0.00"
            if price_text:
                price_match = re.search(r'(\d+)', price_text)
                if price_match:
                    current_price = price_match.group(1)
            
            # Image extraction
            image = card.css('a.product-card__img img::attr(src)').get() or \
                    card.css('a.product-card__img img::attr(data-src)').get()
            
            if not image:
                image = card.css('picture source::attr(srcset)').get()
                if image and "," in image:
                    image = image.split(",")[0].split(" ")[0]
            
            if title and url:
                yield self.create_product(
                    title=title.strip(),
                    product_url=response.urljoin(url),
                    price=current_price,
                    image_url=response.urljoin(image) if image else None,
                    merchant="PichShop",
                    raw_data={
                        "source": "scrapy_v1",
                        "catalog_id": card.attrib.get('data-id')
                    }
                )

        # 2. Yield subcategories/category links to crawl deeper
        if self.strategy != "discovery":
            yield from self.parse_discovery(response)

        # 3. Handle Pagination (Next Page)
        if self.strategy in ["deep", "discovery"]:
            next_page = response.css('.pagination__next a::attr(href)').get()
            if next_page:
                self.logger.info(f"Following next page: {next_page}")
                yield response.follow(next_page, self.parse_catalog)
