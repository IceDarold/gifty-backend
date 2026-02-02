import scrapy
import re
from gifty_scraper.base_spider import GiftyBaseSpider


class IntelToysSpider(GiftyBaseSpider):
    name = "inteltoys"
    allowed_domains = ["inteltoys.ru"]
    site_key = "inteltoys"
    category_selector = 'div.catalog-nav-item a.catalog-nav-controller__whole-link, a.categories-widget__link'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    def parse_catalog(self, response):
        """
        Parses the catalog page.
        """
        self.logger.info(f"Parsing catalog: {response.url}")
        
        cards = response.css('div.product-item')
        
        if not cards:
            self.logger.warning(f"No product cards found on {response.url}")
            return

        for card in cards:
            # Title and Link
            title_link = card.css('a.product-item__link')
            title = title_link.xpath('.//text()').get()
            url = title_link.css('::attr(href)').get()
            
            # Price
            price_text = "".join(card.css('div.product-item__price-current div.price::text').getall())
            current_price = None
            if price_text:
                # Extract numbers from "1 499 р."
                price_match = re.search(r'([\d\s]+)', price_text)
                if price_match:
                    current_price = price_match.group(1).replace(" ", "").strip()
            
            # Image extraction
            image = card.css('img.lozad::attr(data-src)').get() or card.css('img::attr(src)').get()
            
            if not title or not url:
                continue

            yield self.create_product(
                title=title.strip(),
                product_url=response.urljoin(url),
                price=current_price,
                image_url=response.urljoin(image) if image else None,
                merchant="IntelToys",
                raw_data={
                    "source": "scrapy_v1",
                    "product_id": card.css('a.mainButton::attr(data-id)').get()
                }
            )

        # Pagination
        if self.strategy in ["deep", "discovery"]:
            next_page = response.css('ul.paginator li a.next::attr(href)').get()
            if next_page:
                yield response.follow(next_page, self.parse_catalog)
