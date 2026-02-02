import scrapy
import re
from gifty_scraper.base_spider import GiftyBaseSpider


class VseIgrushkiSpider(GiftyBaseSpider):
    name = "vseigrushki"
    allowed_domains = ["vseigrushki.com"]
    site_key = "vseigrushki"
    category_selector = '.f-menu a[href$="/"], .footer__item a[href*="/"]' # Target cleaner footer category links
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 0.5,
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    # Categories to focus on or skip
    ignored_patterns = ['/o-magazine/', '/reviews/', '/vozvrat/', '/dostavka/', '/kontakty/', '/politika/', '/htmlmaps/']

    def parse_discovery(self, response):
        """
        Discovers main category links while ignoring info pages.
        """
        selector = getattr(self, 'category_selector', 'a[href*="/"]')
        found_urls = set()
        
        links = response.css(selector)
        for link in links:
            rel_url = link.css('::attr(href)').get()
            if not rel_url:
                continue
                
            # Skip ignored patterns
            if any(pattern in rel_url for pattern in self.ignored_patterns):
                continue
                
            url = response.urljoin(rel_url)
            
            # Simple heuristic to avoid redundant links and root domain
            if url and url != response.url and url not in found_urls:
                # Ensure it's likely a category (e.g. has more than 1 slash)
                path = rel_url.strip('/')
                if '/' in path or any(p in rel_url for p in ['/konstruktory/', '/myagkie-igrushki/', '/figurki/', '/shkola/']):
                    found_urls.add(url)
                    self.logger.info(f"Discovered category: {url}")
                    yield response.follow(url, self.parse_catalog)

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
            image = None
            srcset = card.css('img.lazy-img::attr(data-srcset)').get()
            if srcset:
                # Try to get the 2x version if it exists
                parts = [p.strip() for p in srcset.split(',')]
                for p in parts:
                    if '2x' in p:
                        image = p.split()[0]
                        break
                if not image:
                    image = parts[0].split()[0]
            
            if not image:
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
            # Try multiple common pagination patterns for InSales platform
            next_page = response.css('a.next::attr(href)').get() or \
                        response.xpath('//a[contains(text(), "→") or contains(text(), "Вперед")]/@href').get() or \
                        response.css('a.paging-next::attr(href)').get() or \
                        response.xpath('//a[contains(@class, "inline-link") and contains(@href, "page=")]/@href').get()
            
            # Filter matches to ensure we only follow actual pagination
            if next_page:
                next_page_url = response.urljoin(next_page)
                if 'page=' in next_page_url and next_page_url != response.url:
                    self.logger.info(f"Following next page: {next_page_url}")
                    yield response.follow(next_page_url, self.parse_catalog)
