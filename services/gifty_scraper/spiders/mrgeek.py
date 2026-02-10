from gifty_scraper.base_spider import GiftyBaseSpider
from gifty_scraper.items import CategoryItem

class MrGeekSpider(GiftyBaseSpider):
    name = "mrgeek"
    allowed_domains = ["mrgeek.ru"]
    site_key = "mrgeek"

    def parse_catalog(self, response):
        items = response.css('div.product-item')
        for item in items:
            yield self.create_product(
                title=item.css('a.product-title::text').get('').strip(),
                product_url=response.urljoin(item.css('a.product-title::attr(href)').get()),
                price=item.css('span.price::text').re_first(r'(\d+)'),
                image_url=item.css('img::attr(src)').get(),
                merchant="MrGeek",
                raw_data={"source": "scrapy_mrgeek"}
            )

        if self.strategy in ["deep", "discovery"]:
            next_page = response.css('a.next-page-link::attr(href)').get()
            if next_page:
                yield response.follow(next_page, self.parse_catalog)

    def parse_discovery(self, response):
        category_links = response.css('div.category-list a::attr(href)').getall()
        for link in category_links:
            item = CategoryItem()
            item['url'] = response.urljoin(link)
            item['name'] = "" 
            item['site_key'] = self.site_key
            item['parent_url'] = response.url
            yield item
