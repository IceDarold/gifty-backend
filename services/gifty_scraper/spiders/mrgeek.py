import scrapy
from gifty_scraper.items import ProductItem, CategoryItem

class MrGeekSpider(scrapy.Spider):
    name = "mrgeek"
    allowed_domains = ["mrgeek.ru"]

    def __init__(self, url=None, strategy="deep", source_id=None, *args, **kwargs):
        super(MrGeekSpider, self).__init__(*args, **kwargs)
        self.start_urls = [url] if url else []
        self.strategy = strategy
        self.source_id = source_id

    def parse(self, response):
        if self.strategy == "discovery":
            yield from self.parse_discovery(response)
        else:
            yield from self.parse_catalog(response)

    def parse_catalog(self, response):
        # Based on previous BeautifulSoup analysis
        items = response.css('div.product-item')
        for item in items:
            product = ProductItem()
            product['title'] = item.css('a.product-title::text').get('').strip()
            product['product_url'] = response.urljoin(item.css('a.product-title::attr(href)').get())
            product['price'] = item.css('span.price::text').re_first(r'(\d+)')
            product['image_url'] = item.css('img::attr(src)').get()
            product['merchant'] = "MrGeek"
            product['site_key'] = "mrgeek"
            product['source_id'] = self.source_id
            product['raw_data'] = {"source": "scrapy_mrgeek"}
            yield product

        # Pagination (Strategy: deep)
        if self.strategy == "deep":
            next_page = response.css('a.next-page-link::attr(href)').get()
            if next_page:
                yield response.follow(next_page, self.parse_catalog)

    def parse_discovery(self, response):
        # Extract category links from a hub page
        category_links = response.css('div.category-list a::attr(href)').getall()
        for link in category_links:
            item = CategoryItem()
            item['url'] = response.urljoin(link)
            item['name'] = "" # Would need more logic to extract name
            item['site_key'] = "mrgeek"
            item['parent_url'] = response.url
            yield item
