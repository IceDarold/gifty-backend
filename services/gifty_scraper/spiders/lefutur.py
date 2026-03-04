import scrapy
import re
from gifty_scraper.base_spider import GiftyBaseSpider
from gifty_scraper.items import ProductItem, CategoryItem

class LefuturSpider(GiftyBaseSpider):
    name = "lefutur"
    allowed_domains = ["lefutur.ru"]
    site_key = "lefutur"

    custom_settings = {
        "DOWNLOAD_DELAY": 1.0,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
    }

    def __init__(self, *args, **kwargs):
        super(LefuturSpider, self).__init__(*args, **kwargs)
        if not self.start_urls:
            self.start_urls = ["https://lefutur.ru/"]

    def parse_discovery(self, response):
        """Discovery strategy: extract categories from the menu"""
        # Top level categories
        links = response.css('a.menu2-link, a.menu2-sublink')
        for link in links:
            name = link.css('::text').get()
            url = link.attrib.get('href')
            if not name or not url:
                continue
            
            name = name.strip()
            full_url = response.urljoin(url)
            
            if "/catalog/" not in full_url:
                continue
                
            yield CategoryItem(
                name=name,
                title=name,
                url=full_url,
                parent_url=None, # Hierarchical info can be improved but this works
                site_key=self.site_key
            )

    def parse_catalog(self, response):
        """Catalog strategy: parse product listing"""
        products = response.css('a.prod-list-item-link')
        for p in products:
            title = p.css('.prod-list-item-title::text').get()
            url_path = p.attrib.get('href')
            if not title or not url_path:
                continue
                
            product_url = response.urljoin(url_path)
            
            # Price extraction - based on research it's inside spans
            # <span>12&nbsp;990</span> <span class="rub">a</span>
            price_text = p.css('.prod-list-item-price span:first-child::text').get()
            if not price_text:
                # Fallback to general price selector if span:first-child fails
                price_text = p.css('.prod-list-item-price::text').get()
                
            price = self._clean_price(price_text)
            
            # Image extraction
            image_url = p.css('.prod-list-imgbox img::attr(src)').get()
            if image_url:
                image_url = response.urljoin(image_url)

            yield self.create_product(
                title=title.strip(),
                product_url=product_url,
                price=price,
                image_url=image_url,
                merchant="Lefutur"
            )

        # Pagination
        # .pagination .page-next a.next
        next_page = response.css('.pagination .page-next a.next::attr(href)').get()
        if next_page:
            yield scrapy.Request(response.urljoin(next_page), callback=self.parse_catalog)

    def _clean_price(self, price_str):
        if not price_str:
            return None
        # Remove non-breaking spaces and other non-digit chars except dot/comma
        # &nbsp; is often handled by Scrapy/Parsel but we can be explicit
        price_str = price_str.replace('\xa0', '').replace(' ', '')
        clean = re.sub(r'[^\d.]', '', price_str.replace(',', '.'))
        try:
            return float(clean)
        except (ValueError, TypeError):
            return None
