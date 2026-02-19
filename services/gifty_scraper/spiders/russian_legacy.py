import scrapy
import re
from gifty_scraper.base_spider import GiftyBaseSpider


class RussianLegacySpider(GiftyBaseSpider):
    name = "russian_legacy"
    allowed_domains = ["russianlegacy.com"]
    site_key = "russian_legacy"
    # Placeholder: Usually navigation links
    category_selector = 'nav a, ul.menu a'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    def parse_catalog(self, response):
        """
        Parses the catalog page for russianlegacy.com
        """
        self.logger.info(f"Parsing catalog: {response.url}")
        
        # Generic product card selector - likely needs adjustment
        cards = response.css('div.product-wrapper, div.item, li.product')
        
        if not cards:
            self.logger.warning(f"No product cards found on {response.url} (check selectors)")
            return

        for card in cards:
            try:
                # Title and Link
                title_link = card.css('a.product-name, h2.product-name a, h3.name a')
                title = title_link.xpath('.//text()').get()
                url = title_link.css('::attr(href)').get()
                
                # Fallback check
                if not url:
                    url = card.css('a::attr(href)').get()
                
                # Price
                price_text = "".join(card.css('.price::text, .amount::text').getall())
                current_price = None
                if price_text:
                    # Extract numbers removing currency symbols like $
                    price_match = re.search(r'([\d\.,]+)', price_text)
                    if price_match:
                        current_price = price_match.group(1).replace(",", "").strip() # Assuming USD $1,200.00
                
                # Image
                image = card.css('img::attr(src), img::attr(data-src)').get()
                
                if not title or not url:
                    continue

                yield self.create_product(
                    title=title.strip() if title else "?",
                    product_url=response.urljoin(url),
                    price=current_price,
                    image_url=response.urljoin(image) if image else None,
                    merchant="Russian Legacy",
                    raw_data={
                        "source": "scrapy_v1",
                        # Try to find a unique ID
                        "product_id": card.attrib.get('id') or card.attrib.get('data-product-id')
                    }
                )
            except Exception as e:
                self.logger.debug(f"Error parsing card: {e}")
                continue

        # Pagination
        if self.strategy in ["deep", "discovery"]:
            next_page = response.css('a.next::attr(href), li.pagination-next a::attr(href)').get()
            if next_page:
                yield response.follow(next_page, self.parse_catalog)
