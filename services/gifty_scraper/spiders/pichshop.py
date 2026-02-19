import scrapy
import re
from gifty_scraper.base_spider import GiftyBaseSpider


class PichShopSpider(GiftyBaseSpider):
    name = "pichshop"
    allowed_domains = ["pichshop.ru"]
    site_key = "pichshop"
    # Placeholder: Usually main menu or catalog links
    category_selector = 'ul.catalog-menu a, a.category-link'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    def parse_catalog(self, response):
        """
        Parses the catalog page for pichshop.ru
        """
        self.logger.info(f"Parsing catalog: {response.url}")
        
        # Generic product card selector - likely needs adjustment
        cards = response.css('div.product-item, div.catalog-item, div.item')
        
        if not cards:
            self.logger.warning(f"No product cards found on {response.url} (check selectors)")
            return

        for card in cards:
            try:
                # Title and Link
                title_link = card.css('a.name, a.title, a.product-link')
                title = title_link.xpath('.//text()').get()
                url = title_link.css('::attr(href)').get()
                
                # Fallback check
                if not url:
                    url = card.css('a::attr(href)').get()
                
                # Price
                price_text = "".join(card.css('.price::text, .current-price::text').getall())
                current_price = None
                if price_text:
                    # Extract numbers
                    price_match = re.search(r'([\d\s]+)', price_text)
                    if price_match:
                        current_price = price_match.group(1).replace(" ", "").strip()
                
                # Image
                image = card.css('img::attr(src), img::attr(data-src)').get()
                
                if not title or not url:
                    continue

                yield self.create_product(
                    title=title.strip(),
                    product_url=response.urljoin(url),
                    price=current_price,
                    image_url=response.urljoin(image) if image else None,
                    merchant="PichShop",
                    raw_data={
                        "source": "scrapy_v1",
                        "product_id": card.css('::attr(data-id)').get()
                    }
                )
            except Exception as e:
                self.logger.debug(f"Error parsing card: {e}")
                continue

        # Pagination
        if self.strategy in ["deep", "discovery"]:
            next_page = response.css('a.next-page::attr(href), a.pagination-next::attr(href)').get()
            if next_page:
                yield response.follow(next_page, self.parse_catalog)
