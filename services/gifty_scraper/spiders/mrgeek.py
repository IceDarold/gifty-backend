import scrapy
from gifty_scraper.base_spider import GiftyBaseSpider
from gifty_scraper.items import CategoryItem

class Spider(GiftyBaseSpider):
    name = ""
    allowed_domains = [".ru"]
    site_key = ""

    def parse_catalog(self, response):
        self.logger.info(f"Parsing catalog: {response.url}")
        
        # Strategy: Look for links that look like products (/product/...)
        # and extract info from them and surrounding text
        
        # Find all links containing 'product/'
        product_links = response.css('a[href*="/product/"]')
        
        seen_urls = set()
        
        for link in product_links:
            url = link.attrib.get('href')
            if not url or url in seen_urls:
                continue
                
            seen_urls.add(url)
            full_url = response.urljoin(url)
            
            # Title is often the text of the link
            title = link.css('::text').get()
            if not title:
                # Try finding title in image alt if link wraps image
                title = link.css('img::attr(alt)').get()
            
            if not title:
                continue
                
            title = title.strip()
            
            # Try to find price nearby. 
            # This is tricky without clear container. 
            # We can try to look at siblings or parent's siblings
            # But for now let's just extract title/url/image
            
            # Try to find image inside the link
            image = link.css('img::attr(src)').get()
            if image and not image.startswith('http'):
                 image = response.urljoin(image)
            
            # Ensure it's a valid product title (filter out "buy", "details", etc)
            if len(title) < 3 or title.lower() in ['купить', 'подробнее', 'в корзину']:
                continue

            # Need to visit the product page to get the price and full details
            yield scrapy.Request(
                full_url, 
                callback=self.parse_product,
                meta={
                    'title': title, # Backup title
                    'image_url': image, # Backup image
                }
            )
            
        # Pagination - usually standard links
        next_page = response.css('a.next::attr(href), .pagination a[rel="next"]::attr(href)').get()
        if next_page:
             yield response.follow(next_page, self.parse_catalog)

    def parse_product(self, response):
        """Extracts details from the product page"""
        title = response.css('h1::text').get()
        if not title:
            title = response.meta.get('title')
            
        # Price extraction strategies
        price = None
        
        # Strategy 1: OpenGraph price
        price_text = response.css('meta[property="product:price:amount"]::attr(content)').get()
        
        # Strategy 2: Common price classes
        if not price_text:
             price_text = response.css('.price::text, .product-price::text, .cost::text, span[id*="price"]::text').get()
             
        # Strategy 3: Look for price inside generic containers if still missing
        if not price_text:
             # Just look for something that looks like a price near "rub" or "₽"
             price_text = response.xpath('//*[contains(text(), "₽") or contains(text(), "руб")]/text()').get()

        if price_text:
            import re
            digits = re.findall(r'(\d+)', price_text)
            if digits:
                price = "".join(digits)
                
        image_url = response.css('meta[property="og:image"]::attr(content)').get()
        if not image_url:
            image_url = response.meta.get('image_url')

        yield self.create_product(
            title=title.strip() if title else "",
            product_url=response.url,
            price=price,
            image_url=image_url if image_url else None,
            merchant="",
            raw_data={"source": "scrapy__product_page"}
        )

    def parse_discovery(self, response):
        category_links = response.css('div.category-list a::attr(href)').getall()
        for link in category_links:
            item = CategoryItem()
            item['url'] = response.urljoin(link)
            item['name'] = "" 
            item['site_key'] = self.site_key
            item['parent_url'] = response.url
            yield item
