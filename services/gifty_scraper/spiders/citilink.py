import scrapy
import json
import re
from scrapy_playwright.page import PageMethod
from gifty_scraper.base_spider import GiftyBaseSpider
from gifty_scraper.items import ProductItem, CategoryItem

class CitilinkSpider(GiftyBaseSpider):
    name = "citilink"
    allowed_domains = ["citilink.ru"]
    site_key = "citilink"
    
    custom_settings = {
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": True,
            "args": ["--disable-blink-features=AutomationControlled"]
        },
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "DOWNLOAD_DELAY": 2.0,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
    }

    def __init__(self, *args, **kwargs):
        super(CitilinkSpider, self).__init__(*args, **kwargs)
        if not self.start_urls:
            self.start_urls = ["https://www.citilink.ru/catalog/"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url, 
                callback=self.parse,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_selector", "body"),
                        PageMethod("wait_for_timeout", 5000), 
                    ],
                }
            )

    def parse(self, response):
        next_data_script = response.css('script#__NEXT_DATA__::text').get()
        
        if not next_data_script:
            self.logger.warning(f"No __NEXT_DATA__ found at {response.url}.")
            return

        try:
            data = json.loads(next_data_script)
        except json.JSONDecodeError:
            self.logger.error(f"Failed to decode JSON from {response.url}")
            return

        # 1. Discovery
        if self.strategy == "discovery" or response.url.endswith("/catalog/"):
            yield from self.parse_discovery_json(data, response)

        # 2. Parsing products
        yield from self.parse_products_state(data, response)

    def parse_discovery_json(self, data, response):
        """Extract categories from various paths in Next.js state"""
        props = data.get('props', {})
        page_props = props.get('pageProps', {})
        initial_state = props.get('initialState', {})
        
        categories = []

        # Attempt 1: effectorValues (hashed keys)
        effector_values = page_props.get('effectorValues', {})
        for key, value in effector_values.items():
            if isinstance(value, list) and len(value) > 0:
                # Check if it looks like a category list
                if isinstance(value[0], dict) and 'name' in value[0] and ('children' in value[0] or 'slug' in value[0]):
                    categories = value
                    break
        
        # Attempt 2: layoutMain catalogMenu
        if not categories:
            catalog_menu = initial_state.get('layoutMain', {}).get('catalogMenu', {})
            items = catalog_menu.get('items', {})
            if isinstance(items, dict) and 'payload' in items:
                categories = items['payload'].get('categories', [])
            elif isinstance(items, list):
                categories = items

        if not categories:
            self.logger.warning("Catalog categories not found in JSON, falling back to DOM")
            # Fallback to DOM parsing
            yield from self.parse_discovery_dom(response)
            return

        def process_menu(items, parent_url=None):
            for item in items:
                name = item.get('name')
                slug = item.get('slug')
                url_path = item.get('url') or (f"/catalog/{slug}/" if slug else None)
                
                if not name or not url_path:
                    continue
                
                cat_url = response.urljoin(url_path)
                
                yield CategoryItem(
                    name=name,
                    title=name,
                    url=cat_url,
                    parent_url=parent_url,
                    site_key=self.site_key
                )
                
                children = item.get('children') or item.get('categories')
                if children:
                    yield from process_menu(children, parent_url=cat_url)

        yield from process_menu(categories)

    def parse_discovery_dom(self, response):
        """Fallback discovery from DOM"""
        # Top level categories
        for link in response.css('a[href^="/catalog/"]'):
            name = link.css('::text').get()
            url_path = link.attrib.get('href')
            if name and url_path:
                yield CategoryItem(
                    name=name.strip(),
                    title=name.strip(),
                    url=response.urljoin(url_path),
                    parent_url=None,
                    site_key=self.site_key
                )

    def parse_products_state(self, data, response):
        """Extract products from initialState subcategory"""
        initial_state = data.get('props', {}).get('initialState', {})
        subcategory = initial_state.get('subcategory', {})
        
        products = []
        total_count = 0
        
        # Path 1: productsFilter
        pf_payload = subcategory.get('productsFilter', {}).get('payload', {}).get('productsFilter', {})
        if isinstance(pf_payload, dict):
            products = pf_payload.get('products', [])
            total_count = pf_payload.get('pagination', {}).get('totalItems', 0)

        # Path 2: productList
        if not products:
            pl_payload = subcategory.get('productList', {}).get('payload', {})
            if isinstance(pl_payload, dict):
                products = pl_payload.get('products', [])
                pagination = pl_payload.get('pagination', {})
                total_count = pagination.get('totalItems', 0)
        
        if products:
            for p in products:
                product_id = p.get('id')
                name = p.get('name') or p.get('shortName')
                # Brand is often in brandName or can be parsed from title
                brand = p.get('brandName')
                
                # Price extraction
                price_info = p.get('price', {})
                current_price = price_info.get('price') if isinstance(price_info, dict) else p.get('price')
                
                url_path = p.get('url') or (f"/product/{p.get('slug')}-{product_id}/" if p.get('slug') else None)
                if not url_path:
                    continue
                product_url = response.urljoin(url_path)
                
                # Image extraction (Citilink uses a list of images)
                image_url = p.get('imageUrl')
                if not image_url:
                    img_list = p.get('imagesList', [])
                    if img_list and isinstance(img_list, list):
                        first_img = img_list[0]
                        if isinstance(first_img, dict):
                            url_obj = first_img.get('url', {})
                            image_url = url_obj.get('VERTICAL') or url_obj.get('HORIZONTAL') or url_obj.get('SHORT')
                
                if image_url and not image_url.startswith('http'):
                    image_url = response.urljoin(image_url)

                yield self.create_product(
                    title=name,
                    product_url=product_url,
                    price=float(current_price) if current_price else None,
                    image_url=image_url,
                    merchant="Citilink",
                    raw_data={
                        "product_id": str(product_id),
                        "brand": brand,
                        "category_id": p.get('categoryId'),
                        "sku": p.get('sku')
                    }
                )

            # Pagination
            current_page = int(response.meta.get('page', 1))
            items_per_page = len(products)
            if items_per_page > 0 and self.strategy in ["deep", "discovery"]:
                max_pages = (int(total_count) + items_per_page - 1) // items_per_page
                if current_page < max_pages and current_page < 100:
                    next_page = current_page + 1
                    next_url = response.urljoin(f"?p={next_page}")
                    yield scrapy.Request(
                        next_url, 
                        callback=self.parse,
                        meta={
                            "page": next_page,
                            "playwright": True,
                            "playwright_include_page": True,
                            "playwright_page_methods": [
                                PageMethod("wait_for_selector", "body"),
                                PageMethod("wait_for_timeout", 3000),
                            ],
                        }
                    )
        else:
            # Fallback to DOM parsing if JSON is empty but we are on a category page
            if "/catalog/" in response.url and not response.url.endswith("/catalog/"):
                yield from self.parse_products_dom(response)

    def parse_products_dom(self, response):
        """Fallback DOM parsing for products"""
        # Based on identified data-meta-name
        products = response.css('[class*="StyledContainer"]')
        for p in products:
            title_el = p.css('[data-meta-name="Snippet__title"]')
            if not title_el:
                continue
            
            title = title_el.attrib.get('title') or title_el.css('::text').get()
            product_url = response.urljoin(title_el.attrib.get('href'))
            
            price_text = p.css('[data-meta-name="Snippet__price"]::text').get()
            price = None
            if price_text:
                # Remove spaces and currency
                price_val = re.sub(r'[^\d.]', '', price_text.replace(',', '.'))
                if price_val:
                    try:
                        price = float(price_val)
                    except:
                        pass
            
            image_url = p.css('img::attr(src)').get()
            if image_url:
                image_url = response.urljoin(image_url)

            yield self.create_product(
                title=title,
                product_url=product_url,
                price=price,
                image_url=image_url,
                merchant="Citilink"
            )
