import scrapy
import json
import re
from scrapy_playwright.page import PageMethod
from gifty_scraper.base_spider import GiftyBaseSpider
from gifty_scraper.items import ProductItem, CategoryItem

class StockmannSpider(GiftyBaseSpider):
    name = "stockmann"
    allowed_domains = ["stockmann.ru"]
    site_key = "stockmann"
    
    # Регулярка для извлечения ID категории из URL
    CAT_ID_RE = re.compile(r'/category/(\d+)-')

    custom_settings = {
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": True,
            "args": ["--disable-blink-features=AutomationControlled"]
        },
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    }

    def __init__(self, *args, **kwargs):
        super(StockmannSpider, self).__init__(*args, **kwargs)
        if not self.start_urls:
            self.start_urls = ["https://stockmann.ru/"]

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
        if self.strategy == "discovery":
            yield from self.parse_discovery_json(data, response)

        # 2. Парсинг товаров
        props = data.get('props', {})
        page_props = props.get('pageProps', {})
        
        products = None
        total_count = 0
        
        # Разные варианты вложенности
        inner_props = page_props.get('pageProps', {})
        category_data = inner_props.get('category', {})
        products = category_data.get('products')
        total_count = category_data.get('totalCount') or category_data.get('count') or 0
        
        if not products:
            products = page_props.get('products')
            total_count = page_props.get('totalCount') or 0

        if not products:
            initial_state = page_props.get('initialState', {})
            products_chunk = initial_state.get('products', {})
            products = products_chunk.get('items') or products_chunk.get('products')
            total_count = products_chunk.get('totalCount') or page_props.get('totalCount') or 0

        if products:
            yield from self.parse_products_json(products, response)
            
            # Пагинация
            current_page = int(response.meta.get('page', 1))
            
            if self.strategy in ["deep", "discovery"] and products:
                items_per_page = len(products) if len(products) > 0 else 24
                max_pages = (int(total_count) + items_per_page - 1) // items_per_page
                if current_page < max_pages and current_page < 100:
                    next_page = current_page + 1
                    next_url = response.urljoin(f"?page={next_page}")
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

    def parse_discovery_json(self, data, response):
        """Извлечение иерархии категорий из структуры mainMenu (level1, level2, level3)"""
        props = data.get('props', {})
        page_props = props.get('pageProps', {})
        
        main_menu = None
        # Ищем mainMenu
        layout_props = page_props.get('layoutProps', {})
        main_menu = layout_props.get('mainMenu')
        if not main_menu:
            main_menu = page_props.get('pageProps', {}).get('layoutProps', {}).get('mainMenu')
        if not main_menu:
            main_menu = page_props.get('initialState', {}).get('layout', {}).get('mainMenu')

        if not main_menu:
            self.logger.warning("Main menu not found in JSON structures")
            return

        # Если это словарь с уровнями (как на главной)
        if isinstance(main_menu, dict):
            level1 = main_menu.get('level1', [])
            level2 = main_menu.get('level2', {})
            level3 = main_menu.get('level3', {})

            # 1. Верхний уровень
            for cat1 in level1:
                cat1_id = cat1.get('id')
                cat1_name = cat1.get('name')
                cat1_url = response.urljoin(cat1.get('url'))
                
                yield CategoryItem(
                    name=cat1_name,
                    title=cat1_name,
                    url=cat1_url,
                    parent_url=None,
                    site_key=self.site_key
                )

                # 2. Второй уровень
                sub_cats2 = level2.get(str(cat1_id), [])
                for cat2 in sub_cats2:
                    cat2_id = cat2.get('id')
                    cat2_name = cat2.get('name')
                    cat2_url = response.urljoin(cat2.get('url'))
                    
                    yield CategoryItem(
                        name=cat2_name,
                        title=cat2_name,
                        url=cat2_url,
                        parent_url=cat1_url,
                        site_key=self.site_key
                    )

                    # 3. Третий уровень
                    sub_cats3 = level3.get(str(cat2_id), [])
                    for cat3 in sub_cats3:
                        cat3_name = cat3.get('name')
                        cat3_url = response.urljoin(cat3.get('url'))
                        
                        yield CategoryItem(
                            name=cat3_name,
                            title=cat3_name,
                            url=cat3_url,
                            parent_url=cat2_url,
                            site_key=self.site_key
                        )
        
        # Если это простой список (как случается на некоторых страницах)
        elif isinstance(main_menu, list):
            def process_items(items, parent_url=None):
                for item in items:
                    if not isinstance(item, dict): continue
                    name = item.get('name')
                    url = item.get('url') or item.get('link')
                    if not url or not name: continue
                    
                    full_url = response.urljoin(url)
                    yield CategoryItem(
                        name=name,
                        title=name,
                        url=full_url,
                        parent_url=parent_url,
                        site_key=self.site_key
                    )
                    sub_items = item.get('items', [])
                    if sub_items:
                        yield from process_items(sub_items, parent_url=full_url)
            
            yield from process_items(main_menu)

    def parse_products_json(self, products, response):
        """Парсинг списка товаров"""
        if not isinstance(products, list):
            return

        for p in products:
            if not isinstance(p, dict):
                continue
            
            product_data = p.get('payload') if p.get('type') == 'product' and 'payload' in p else p

            if not isinstance(product_data, dict):
                continue

            product_id = product_data.get('productId') or product_data.get('id')
            sku = product_data.get('xmlId')
            brand = product_data.get('brand')
            name = product_data.get('name')
            
            price_info = product_data.get('price', {})
            if isinstance(price_info, dict):
                current_price = price_info.get('current') or price_info.get('price')
            else:
                current_price = price_info
            
            url_path = product_data.get('url') or product_data.get('link')
            if not url_path:
                continue
            product_url = response.urljoin(url_path)
            
            images = product_data.get('images', [])
            image_url = None
            if images and isinstance(images, list):
                first_img = images[0]
                if isinstance(first_img, dict):
                    img_data = first_img.get('default') or first_img
                    if isinstance(img_data, dict):
                        image_url = img_data.get('webp', {}).get('src') or img_data.get('jpg', {}).get('src') or img_data.get('src')
                    else:
                        image_url = first_img.get('src')
                else:
                    image_url = first_img
            
            if image_url and not image_url.startswith('http'):
                image_url = response.urljoin(image_url)

            yield self.create_product(
                title=f"{brand} {name}" if brand else name,
                product_url=product_url,
                price=float(current_price) if current_price else None,
                image_url=image_url,
                merchant="Stockmann",
                raw_data={
                    "product_id": str(product_id),
                    "sku": str(sku),
                    "brand": brand,
                    "category_id": product_data.get('categoryId')
                }
            )
