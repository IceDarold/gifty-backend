import scrapy
import json
import re
from urllib.parse import urlencode
from gifty_scraper.base_spider import GiftyBaseSpider


class MVideoSpider(GiftyBaseSpider):
    name = "mvideo"
    allowed_domains = ["mvideo.ru", "www.mvideo.ru"]
    site_key = "mvideo"
    
    # Discovery strategy uses this to find category links
    category_selector = 'a[href*="/catalog/"], a.category-card__name, a.catalog-navigation-list__link, a.f-menu__link'

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 2.0,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'DEFAULT_REQUEST_HEADERS': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9',
            'Referer': 'https://www.mvideo.ru/',
            'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        },
        'COOKIES_ENABLED': True
    }

    def __init__(self, url=None, strategy="deep", source_id=None, *args, **kwargs):
        # Default to "all categories" if no URL provided
        if not url:
            url = "https://www.mvideo.ru/vse-kategorii"
        super(MVideoSpider, self).__init__(url=url, strategy=strategy, source_id=source_id, *args, **kwargs)

    def start_requests(self):
        url = getattr(self, 'url', "https://www.mvideo.ru/smartfony-i-svyaz-10/smartfony-205")
        yield scrapy.Request(
            url, 
            callback=self.parse_catalog,
            dont_filter=True,
            headers={
                'Referer': 'https://www.google.com/',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'cross-site',
                'Upgrade-Insecure-Requests': '1'
            }
        )

    def parse_catalog(self, response):
        """
        Parses the catalog page. Use __NEXT_DATA__ for initial products and POST API for pagination.
        """
        category_id = None
        
        # DEBUG: Save full response to inspect
        with open("last_response.html", "w", encoding="utf-8") as f:
            f.write(response.text)
            
        match = re.search(r'-(\d+)$', response.url.rstrip('/'))
        if not match:
             match = re.search(r'"categoryId":"(\d+)"', response.text)
        
        # Debug: Check what page we actually landed on
        page_title = response.css('title::text').get()
        self.logger.info(f"Page Title: {page_title}")
        self.logger.info(f"Body snippet: {response.text[:500]}")
        
        if match:
            category_id = match.group(1)
            self.logger.info(f"Found category ID: {category_id}. Using BFF v2 API (GET)...")
            
            # API v2 endpoint found in source: products/v2/search
            # Analysis of 'd' function in JS suggests GET with query params
            
        if match:
             category_id = match.group(1)
             self.logger.info(f"Found category ID: {category_id}. Using BFF v2 API (GET)...")
             # ... (API logic remains the same)
             # Verified working params: categoryIds (plural), GET method
             params = {
                 "categoryIds": category_id,
                 "offset": "0",
                 "limit": "24",
                 "doTransliteration": "true"
             }
             query_string = urlencode(params)
             api_url = f"https://www.mvideo.ru/bff/products/v2/search?{query_string}"
             
             yield scrapy.Request(
                 api_url,
                 method="GET",
                 callback=self.parse_api_response,
                 errback=self.parse_api_error,
                 meta={'category_id': category_id, 'offset': 0},
                 headers={
                     'Accept': 'application/json',
                     'X-Requested-With': 'XMLHttpRequest',
                     'Referer': response.url
                 }
             )
        else:
            self.logger.warning("No category ID found. Trying discovery.")
            yield from self.parse_discovery(response)

    def parse_discovery(self, response):
        """
        Custom discovery for M.Video category structure.
        Looks for links in the 'vse-kategorii' page or similar hub pages.
        """
        self.logger.info("Starting discovery on: %s", response.url)
        
        links = response.css('a::attr(href)').getall()
        unique_links = set()
        
        for link in links:
            url = response.urljoin(link)
            
            # Filter for category-like URLs
            # e.g., /smartfony-i-svyaz-10, /televizory-audio-video-hi-fi-1
            # They usually end in digits and are not product details
            if re.search(r'-[\d]+', url) and '/products/' not in url and 'vse-kategorii' not in url:
                unique_links.add(url)
                
        self.logger.info(f"Found {len(unique_links)} potential category links.")
        
        for url in unique_links:
            yield response.follow(url, self.parse_catalog)

    def parse_api_error(self, failure):
        self.logger.error(f"API Request Failed: {failure.type} {failure.value}")
        if failure.check(scrapy.spidermiddlewares.httperror.HttpError):
            response = failure.value.response
            self.logger.error(f"Response status: {response.status}")
            self.logger.error(f"Response body: {response.text[:1000]}")

    def parse_api_response(self, response):
        """
        Parses JSON from BFF API.
        """
        try:
            # Handle potential 400/403/404
            if response.status != 200:
                 self.logger.warning(f"API Error {response.status}: {response.url}")
                 return

            data = json.loads(response.text)
            body = data.get('body', {})
            products_ids = body.get('products', [])
            
            if not products_ids:
                 self.logger.info(f"No product IDs in response.")
                 return

            self.logger.info(f"Fetched {len(products_ids)} IDs from API. Fetching details...")

            # 1. Fetch Details first
            details_url = "https://www.mvideo.ru/bff/product-details/list"
            yield scrapy.Request(
                details_url,
                method="POST",
                body=json.dumps({
                    "productIds": products_ids,
                    "addBonusRubles": True,
                    "isLightDetails": True
                }),
                callback=self.parse_details_then_prices,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Referer': response.url
                },
                meta={**response.meta, 'products_ids': products_ids}
            )

            # Pagination
            total = body.get('total', 0)
            offset = response.meta.get('offset', 0)
            if offset + 24 < total:
                next_offset = offset + 24
                cat_id = response.meta.get('category_id')
                
                api_url = "https://www.mvideo.ru/bff/products/v2/search"
                params = {
                    "categoryIds": cat_id,
                    "offset": str(next_offset),
                    "limit": "24",
                    "doTransliteration": "true"
                }
                query_string = urlencode(params)
                next_url = f"{api_url}?{query_string}"
                
                yield scrapy.Request(
                    next_url,
                    method="GET",
                    callback=self.parse_api_response,
                    meta={'category_id': cat_id, 'offset': next_offset},
                    headers={
                        'Accept': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                        'Referer': response.url
                    }
                )
        except Exception as e:
            self.logger.error(f"API parse error: {e}")

    def parse_details_then_prices(self, response):
        """
        Parses details, then queues a price fetch.
        """
        parsed_products = {} # id -> partial item
        try:
            data = json.loads(response.text)
            items = data.get('body', {}).get('products', [])
            
            for item in items:
                p_id = item.get('productId')
                name = item.get('name')
                image = item.get('image')
                if image and not image.startswith('http'):
                    image = f"https://static.mvideo.ru{image}"
                    
                parsed_products[p_id] = {
                    "title": name,
                    "product_url": f"https://www.mvideo.ru/products/{p_id}",
                    "image_url": image,
                    "merchant": "М.Видео",
                    "raw_data": {"source": "bff_v3", "id": p_id},
                    "price": None # Placeholder
                }
            
            # Now fetch prices
            products_ids = response.meta.get('products_ids', [])
            prices_url = "https://www.mvideo.ru/bff/products/prices"
            
            full_prices_url = f"{prices_url}?productIds={','.join(products_ids)}&addBonusRubles=true&isPromoApplied=true"
            
            yield scrapy.Request(
                full_prices_url,
                method="GET",
                callback=self.parse_prices,
                headers={
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Referer': response.url
                },
                meta={**response.meta, 'parsed_products': parsed_products}
            )
            
        except Exception as e:
            self.logger.error(f"Details parse error: {e}")

    def parse_prices(self, response):
        parsed_products = response.meta.get('parsed_products', {})
        try:
            data = json.loads(response.text)
            # Structure usually: body -> materialPrices -> [ { productId, price: { salePrice } } ]
            prices_list = data.get('body', {}).get('materialPrices', [])
            
            # Use a dict for faster lookup
            price_map = {}
            for p in prices_list:
                p_id = p.get('price', {}).get('productId') # sometimes it's here
                if not p_id:
                     p_id = p.get('productId')

                sale_price = p.get('price', {}).get('salePrice')
                if p_id and sale_price:
                    price_map[str(p_id)] = sale_price

            # Now combine and yield
            for p_id, item_data in parsed_products.items():
                if str(p_id) in price_map:
                    item_data['price'] = str(price_map[str(p_id)])
                
                yield self.create_product(**item_data)
                
        except Exception as e:
            self.logger.error(f"Prices parse error: {e}")
            # Yield what we have even if prices fail
            for p in parsed_products.values():
                yield self.create_product(**p)

    def _extract_from_next_data(self, data):
        """
        Heuristic to extract products from Next.js initial state.
        The exact path can change frequently.
        """
        products = []
        try:
            # Common paths in M.Video Next.js props
            page_props = data.get('props', {}).get('pageProps', {})
            
            # Path 1: initialData in products
            listing_data = page_props.get('initialData', {}).get('products', [])
            
            # Path 2: listing state in initialState
            if not listing_data:
                listing_data = page_props.get('initialState', {}).get('listing', {}).get('products', [])

            # Path 3: search results
            if not listing_data:
                 listing_data = page_props.get('initialState', {}).get('search', {}).get('products', [])

            for item in listing_data:
                p_id = item.get('productId') or item.get('id')
                name = item.get('name') or item.get('title')
                
                # Construct URL if not present
                p_url = item.get('productUrl') or item.get('url')
                if p_url and not p_url.startswith('http'):
                    p_url = f"https://www.mvideo.ru{p_url}"
                elif not p_url and p_id:
                    p_url = f"https://www.mvideo.ru/products/{p_id}"

                price = item.get('price', {}).get('salePrice') or item.get('salePrice')
                image = item.get('image') or item.get('imageUrl')
                if image and not image.startswith('http'):
                    image = f"https://static.mvideo.ru{image}"

                if name and p_url:
                    products.append({
                        "title": name,
                        "product_url": p_url,
                        "price": str(price) if price else None,
                        "image_url": image,
                        "merchant": "М.Видео",
                        "raw_data": {"source": "next_data", "id": p_id}
                    })
        except Exception:
            pass
        return products
