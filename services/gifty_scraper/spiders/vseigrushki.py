import scrapy
import re
from gifty_scraper.base_spider import GiftyBaseSpider


class VseIgrushkiSpider(GiftyBaseSpider):
    name = "vseigrushki"
    allowed_domains = ["vseigrushki.com"]
    site_key = "vseigrushki"
    category_selector = 'div.footer__item a[href*="/"]' 
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    def parse_catalog(self, response):
        """
        Parses the catalog page.
        """
        self.logger.info(f"Parsing catalog: {response.url}")
        
        # Product cards
        cards = response.css('div.products__item')
        
        if not cards:
            self.logger.warning(f"No product cards found on {response.url}")
            return

        for card in cards:
            # Title
            title = card.css('span.products__item-info-name::text').get()
            if not title:
                title = card.css('meta[itemprop="name"]::attr(content)').get()
            
            # URL
            url = card.css('a::attr(href)').get()
            
            # Price
            price_text = card.css('div.products__price-new::text').get()
            current_price = None
            if price_text:
                price_match = re.search(r'([\d\s]+)', price_text)
                if price_match:
                    current_price = price_match.group(1).replace(" ", "").strip()
            
            if not current_price:
                current_price = card.css('meta[itemprop="price"]::attr(content)').get()
            
            # Image
            image = card.css('img.lazy-img::attr(data-src)').get()
            if not image:
                image = card.css('meta[itemprop="image"]::attr(content)').get()
            
            if not title or not url:
                continue

            yield self.create_product(
                title=title.strip(),
                product_url=response.urljoin(url),
                price=current_price,
                image_url=response.urljoin(image) if image else None,
                merchant="VseIgrushki",
                raw_data={
                    "source": "scrapy_v1",
                    "product_id": card.css('input[name="product_id"]::attr(value)').get()
                }
            )

        # Pagination
        if self.strategy in ["deep", "discovery"]:
            next_page = response.css('div.pagination a.next::attr(href)').get() or \
                        response.xpath('//a[contains(@class, "next")]/@href').get() or \
                        response.css('div.pagination a:last-child[href*="page="]::attr(href)').get()
            
            if next_page:
                yield response.follow(next_page, self.parse_catalog)
