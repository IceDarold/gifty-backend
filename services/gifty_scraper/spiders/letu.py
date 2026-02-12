import re
from gifty_scraper.base_spider import GiftyBaseSpider


class LetuSpider(GiftyBaseSpider):
    name = "letu"
    allowed_domains = ["www.letu.ru", "letu.ru"]
    site_key = "letu"
    
    # Default category discovery selector
    category_selector = 'a[data-testid="category-card-link"], .f-menu a[href*="/browse/"], .footer__item a[href*="/browse/"]'

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 2.0,
        'USER_AGENT': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
        'DEFAULT_REQUEST_HEADERS': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Upgrade-Insecure-Requests': '1',
        }
    }

    def parse_catalog(self, response):
        """
        Parses the catalog page for Letu.ru using SSR-rendered content.
        """
        self.logger.info(f"Parsing catalog: {response.url}")
        
        # 1. Product cards extraction
        cards = response.css('.product-tile')
        
        if not cards:
            self.logger.warning(f"No product cards found on {response.url}. The site might be blocking or requiring a real browser.")

        for card in cards:
            # Brand and Title
            brand = card.css('.product-tile-name__text--brand::text').get()
            title_part = card.css('[data-at-product-tile-title]::text').get()
            
            full_title = ""
            if brand:
                full_title += brand.strip() + " "
            if title_part:
                full_title += title_part.strip()
            
            # URL
            url = card.css('a.product-tile__item-container::attr(href)').get()
            
            # Price
            # Look for actual price (can handle discounts)
            price_text = card.css('.product-tile-price__text--actual::text').get() or \
                         card.css('.product-tile-price__text::text').get()
            
            current_price = None
            if price_text:
                price_match = re.search(r'([\d\s\xa0]+)', price_text)
                if price_match:
                    current_price = price_match.group(1).replace(" ", "").replace("\xa0", "").strip()

            # Image
            image = card.css('img.le-lazy-image__image::attr(src)').get()

            if full_title and url:
                yield self.create_product(
                    title=full_title.strip(),
                    product_url=response.urljoin(url),
                    price=current_price,
                    image_url=response.urljoin(image) if image else None,
                    merchant="Л'Этуаль",
                    raw_data={
                        "source": "scrapy_v1"
                    }
                )

        # 2. Pagination
        if self.strategy in ["deep", "discovery"]:
            # Googlebot version uses link rel="next"
            next_page = response.css('link[rel="next"]::attr(href)').get()
            
            if next_page:
                next_page_url = response.urljoin(next_page)
                if next_page_url != response.url:
                    self.logger.info(f"Following next page: {next_page_url}")
                    yield response.follow(next_page_url, self.parse_catalog)
