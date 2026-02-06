import scrapy
import re
import json
from urllib.parse import urlencode, urlparse, parse_qs
from gifty_scraper.base_spider import GiftyBaseSpider


class SportmasterSpider(GiftyBaseSpider):
    name = "sportmaster"
    allowed_domains = ["sportmaster.ru", "www.sportmaster.ru"]
    site_key = "sportmaster"
    
    # Discovery strategy uses this to find category links
    category_selector = 'a[href*="/catalog/"], a[class*="category"], a[class*="menu"]'

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 2.0,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'DEFAULT_REQUEST_HEADERS': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.sportmaster.ru/',
            'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        },
        'COOKIES_ENABLED': True,
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_TIMEOUT': 30,
    }

    def __init__(self, url=None, strategy="deep", source_id=None, *args, **kwargs):
        # Default to main catalog if no URL provided
        if not url:
            url = "https://www.sportmaster.ru/catalog/"
        super(SportmasterSpider, self).__init__(url=url, strategy=strategy, source_id=source_id, *args, **kwargs)

    def start_requests(self):
        url = getattr(self, 'url', "https://www.sportmaster.ru/catalog/")
        yield scrapy.Request(
            url, 
            callback=self.parse,
            dont_filter=True,
            headers={
                'Referer': 'https://www.google.com/',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'cross-site',
                'Upgrade-Insecure-Requests': '1'
            }
        )

    def parse(self, response):
        """
        Main parse method that routes to catalog or discovery based on strategy.
        """
        # Save response for debugging
        with open("sportmaster_response.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        
        # Check if this is a catalog page with products
        has_products = response.css('[data-test-id*="product"], [class*="product-card"], article[class*="product"]').get()
        
        if has_products:
            yield from self.parse_catalog(response)
        elif self.strategy == "discovery" or "/catalog/" in response.url:
            yield from self.parse_discovery(response)
        else:
            yield from self.parse_catalog(response)

    def parse_catalog(self, response):
        """
        Parses the catalog page with products.
        """
        self.logger.info(f"Parsing catalog: {response.url}")
        
        # Try to extract products from JSON embedded in page
        products_from_json = self._extract_from_json_data(response)
        if products_from_json:
            self.logger.info(f"Found {len(products_from_json)} products from JSON data")
            for product in products_from_json:
                yield self.create_product(**product)
        else:
            # Fallback to HTML parsing
            yield from self._parse_html_products(response)
        
        # Handle pagination
        if self.strategy == "deep":
            yield from self._handle_pagination(response)

    def _extract_from_json_data(self, response):
        """
        Try to extract product data from embedded JSON (Next.js, window.__INITIAL_STATE__, etc.)
        """
        products = []
        
        try:
            # Try Next.js __NEXT_DATA__
            next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', response.text, re.DOTALL)
            if next_data_match:
                data = json.loads(next_data_match.group(1))
                products.extend(self._extract_from_next_data(data))
                if products:
                    return products
        except Exception as e:
            self.logger.debug(f"Failed to parse __NEXT_DATA__: {e}")
        
        try:
            # Try window.__INITIAL_STATE__ or similar
            initial_state_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', response.text, re.DOTALL)
            if initial_state_match:
                data = json.loads(initial_state_match.group(1))
                products.extend(self._extract_from_initial_state(data))
                if products:
                    return products
        except Exception as e:
            self.logger.debug(f"Failed to parse __INITIAL_STATE__: {e}")
        
        try:
            # Try window.appData or window.__APP_DATA__
            app_data_match = re.search(r'window\.(?:appData|__APP_DATA__)\s*=\s*JSON\.parse\(["\'](.+?)["\']\)', response.text)
            if app_data_match:
                json_str = app_data_match.group(1).encode('utf-8').decode('unicode_escape')
                data = json.loads(json_str)
                products.extend(self._extract_from_app_data(data))
                if products:
                    return products
        except Exception as e:
            self.logger.debug(f"Failed to parse appData: {e}")
        
        return products

    def _extract_from_next_data(self, data):
        """Extract products from Next.js __NEXT_DATA__"""
        products = []
        try:
            page_props = data.get('props', {}).get('pageProps', {})
            
            # Common paths for product listings
            possible_paths = [
                page_props.get('initialData', {}).get('products', []),
                page_props.get('initialState', {}).get('catalog', {}).get('products', []),
                page_props.get('products', []),
                page_props.get('catalog', {}).get('items', []),
            ]
            
            for product_list in possible_paths:
                if product_list:
                    for item in product_list:
                        product = self._normalize_product_data(item, 'next_data')
                        if product:
                            products.append(product)
                    break
        except Exception as e:
            self.logger.debug(f"Error extracting from Next.js data: {e}")
        
        return products

    def _extract_from_initial_state(self, data):
        """Extract products from window.__INITIAL_STATE__"""
        products = []
        try:
            # Try various common paths
            catalog = data.get('catalog', {})
            product_list = catalog.get('products', []) or catalog.get('items', [])
            
            for item in product_list:
                product = self._normalize_product_data(item, 'initial_state')
                if product:
                    products.append(product)
        except Exception as e:
            self.logger.debug(f"Error extracting from initial state: {e}")
        
        return products

    def _extract_from_app_data(self, data):
        """Extract products from window.appData"""
        products = []
        try:
            items = data.get('catalog', {}).get('data', {}).get('items', [])
            for item in items:
                product = self._normalize_product_data(item, 'app_data')
                if product:
                    products.append(product)
        except Exception as e:
            self.logger.debug(f"Error extracting from app data: {e}")
        
        return products

    def _normalize_product_data(self, item, source):
        """
        Normalize product data from various JSON structures
        """
        try:
            # Extract ID
            product_id = item.get('id') or item.get('productId') or item.get('code')
            
            # Extract title/name
            title = item.get('name') or item.get('title') or item.get('displayName')
            
            # Extract URL
            url = item.get('url') or item.get('link') or item.get('href')
            if url and not url.startswith('http'):
                url = f"https://www.sportmaster.ru{url}"
            elif not url and product_id:
                url = f"https://www.sportmaster.ru/product/{product_id}/"
            
            # Extract price
            price = None
            price_data = item.get('price', {})
            if isinstance(price_data, dict):
                price = (price_data.get('current') or 
                        price_data.get('sale') or 
                        price_data.get('value') or
                        price_data.get('actual'))
            elif isinstance(price_data, (int, float, str)):
                price = price_data
            
            # Also try direct price fields
            if not price:
                price = item.get('currentPrice') or item.get('salePrice') or item.get('actualPrice')
            
            # Extract image
            image = None
            image_data = item.get('image') or item.get('images', [])
            if isinstance(image_data, str):
                image = image_data
            elif isinstance(image_data, list) and image_data:
                image = image_data[0] if isinstance(image_data[0], str) else image_data[0].get('url')
            elif isinstance(image_data, dict):
                image = image_data.get('url') or image_data.get('src') or image_data.get('original')
            
            # Also try other image fields
            if not image:
                image = item.get('imageUrl') or item.get('picture') or item.get('thumbnail')
            
            if image and not image.startswith('http'):
                image = f"https://www.sportmaster.ru{image}"
            
            if not title or not url:
                return None
            
            return {
                "title": title.strip(),
                "product_url": url,
                "price": str(price) if price else None,
                "image_url": image,
                "merchant": "Спортмастер",
                "raw_data": {
                    "source": source,
                    "id": str(product_id) if product_id else None
                }
            }
        except Exception as e:
            self.logger.debug(f"Error normalizing product data: {e}")
            return None

    def _parse_html_products(self, response):
        """
        Fallback HTML parsing for products
        """
        # Try various common selectors for product cards
        selectors = [
            '[data-test-id*="product"]',
            '[class*="product-card"]',
            'article[class*="product"]',
            '[data-product-id]',
            '.catalog-item',
            '.product-item',
        ]
        
        cards = []
        for selector in selectors:
            cards = response.css(selector)
            if cards:
                self.logger.info(f"Found {len(cards)} products using selector: {selector}")
                break
        
        if not cards:
            self.logger.warning(f"No product cards found on {response.url}")
            return
        
        for card in cards:
            # Extract title
            title = (card.css('h3::text, h2::text, [class*="title"]::text, [class*="name"]::text').get() or
                    card.css('a[class*="title"]::text, a[class*="name"]::text').get())
            
            # Extract URL
            url = (card.css('a::attr(href)').get() or
                  card.css('[class*="link"]::attr(href)').get())
            
            # Extract price
            price = None
            price_text = (card.css('[class*="price"]::text, [data-test-id*="price"]::text').get() or
                         card.css('[itemprop="price"]::attr(content)').get())
            if price_text:
                price_match = re.search(r'(\d[\d\s]*)', price_text.replace('\xa0', '').replace('\u2009', ''))
                if price_match:
                    price = price_match.group(1).replace(' ', '')
            
            # Extract image
            image = (card.css('img::attr(src)').get() or
                    card.css('img::attr(data-src)').get() or
                    card.css('source::attr(srcset)').get())
            
            if image and ',' in image:
                image = image.split(',')[0].split()[0]
            
            # Get product ID
            product_id = card.attrib.get('data-product-id') or card.attrib.get('data-id')
            
            if not title or not url:
                continue
            
            yield self.create_product(
                title=title.strip(),
                product_url=response.urljoin(url),
                price=price,
                image_url=response.urljoin(image) if image else None,
                merchant="Спортмастер",
                raw_data={
                    "source": "html_parse",
                    "product_id": product_id
                }
            )

    def _handle_pagination(self, response):
        """
        Handle pagination - try multiple common patterns
        """
        # Pattern 1: Next page link
        next_page = response.css('a[rel="next"]::attr(href), a[class*="next"]::attr(href), [data-test-id="next-page"]::attr(href)').get()
        if next_page:
            yield response.follow(next_page, self.parse_catalog)
            return
        
        # Pattern 2: Page number in URL
        current_page = 1
        page_match = re.search(r'[?&]page=(\d+)', response.url)
        if page_match:
            current_page = int(page_match.group(1))
        
        # Check if there are more pages
        max_page = current_page
        page_links = response.css('[class*="pagination"] a::attr(href), [data-test-id*="page"] a::attr(href)').getall()
        for link in page_links:
            page_num_match = re.search(r'page=(\d+)', link)
            if page_num_match:
                max_page = max(max_page, int(page_num_match.group(1)))
        
        # Also check pagination text
        pagination_text = response.css('[class*="pagination"]::text, [data-test-id*="pagination"]::text').getall()
        for text in pagination_text:
            if text.strip().isdigit():
                max_page = max(max_page, int(text.strip()))
        
        if current_page < max_page:
            next_page_num = current_page + 1
            if '?' in response.url:
                if 'page=' in response.url:
                    next_url = re.sub(r'page=\d+', f'page={next_page_num}', response.url)
                else:
                    next_url = f"{response.url}&page={next_page_num}"
            else:
                next_url = f"{response.url}?page={next_page_num}"
            
            self.logger.info(f"Following pagination: page {next_page_num} of {max_page}")
            yield response.follow(next_url, self.parse_catalog)

    def parse_discovery(self, response):
        """
        Discovery mode: find all category links and crawl them
        """
        self.logger.info(f"Starting discovery on: {response.url}")
        
        # Find all links that look like categories
        all_links = response.css('a::attr(href)').getall()
        category_urls = set()
        
        for link in all_links:
            url = response.urljoin(link)
            
            # Filter for category-like URLs
            # Sportmaster typically uses /catalog/category-name/ pattern
            if ('/catalog/' in url and 
                url.startswith('https://www.sportmaster.ru') and
                '/product/' not in url and
                url not in category_urls):
                category_urls.add(url)
        
        self.logger.info(f"Found {len(category_urls)} potential category links")
        
        for url in category_urls:
            yield response.follow(url, self.parse_catalog)
