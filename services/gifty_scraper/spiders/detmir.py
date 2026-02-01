import scrapy
import re
from gifty_scraper.base_spider import GiftyBaseSpider


class DetmirSpider(GiftyBaseSpider):
    """
    Spider for parsing product information from Detmir (detmir.ru).
    Focuses on the gifts catalog and product categories.
    """
    name = "detmir"
    allowed_domains = ["detmir.ru"]
    site_key = "detmir"
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'DEFAULT_REQUEST_HEADERS': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Upgrade-Insecure-Requests': '1',
        }
    }

    def parse(self, response):
        """
        Parses the catalog page.
        """
        self.logger.info(f"Parsing catalog: {response.url}")
        
        # Detmir uses section tags for product cards
        cards = response.css('section[id^="product-"]')
        
        if not cards:
            self.logger.warning(f"No product cards found on {response.url}")
            return

        for card in cards:
            # Title and Link
            title_link = card.css('a[data-testid="titleLink"]')
            title = title_link.xpath('.//text()').get()
            url = title_link.css('::attr(href)').get()
            
            # Price
            # Detmir often shows multiple prices (old, new). We want the current one.
            # Usually the one with currency symbol '₽'
            price_nodes = card.css('[data-testid="productPrice"] *::text').getall()
            price_str = "".join(price_nodes) if price_nodes else ""
            
            # Extract only digits from the price string (taking the first price found)
            # Example: '1 999 ₽ 3 999 ₽' -> we want the first one
            current_price = None
            price_matches = re.findall(r'(\d[\d\s\u2009\xa0]*)₽', price_str)
            if price_matches:
                current_price = price_matches[0].replace("\u2009", "").replace("\xa0", "").replace(" ", "")
            
            # Image
            image = card.css('img::attr(src)').get()
            
            if not title or not url:
                continue

            yield self.create_product(
                title=title.strip(),
                product_url=response.urljoin(url),
                price=current_price,
                image_url=response.urljoin(image) if image else None,
                merchant="Detmir",
                raw_data={
                    "source": "scrapy_v1",
                    "product_id": card.attrib.get('data-product-id')
                }
            )

        # Pagination
        if self.strategy == "deep":
            # Extract current page from URL
            current_page = 1
            page_match = re.search(r'page=(\d+)', response.url)
            if page_match:
                current_page = int(page_match.group(1))
            
            # Find max page from pagination nav
            max_page = 1
            pagination_text = response.xpath('//nav[@aria-label="pagination"]//text()').getall()
            for text in pagination_text:
                if text.isdigit():
                    max_page = max(max_page, int(text))
            
            self.logger.info(f"Page {current_page} of {max_page}")
            
            if current_page < max_page:
                next_page = current_page + 1
                # Construct next page URL
                if '?' in response.url:
                    if 'page=' in response.url:
                         next_url = re.sub(r'page=\d+', f'page={next_page}', response.url)
                    else:
                         next_url = f"{response.url}&page={next_page}"
                else:
                    next_url = f"{response.url}?page={next_page}"
                
                yield response.follow(next_url, self.parse)
