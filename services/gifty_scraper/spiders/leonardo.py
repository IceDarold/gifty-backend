import scrapy
import re
from scrapy_playwright.page import PageMethod
from gifty_scraper.base_spider import GiftyBaseSpider
from gifty_scraper.items import ProductItem, CategoryItem

class LeonardoSpider(GiftyBaseSpider):
    name = "leonardo"
    allowed_domains = ["leonardo.ru"]
    site_key = "leonardo"

    custom_settings = {
        "DOWNLOAD_DELAY": 1.0,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
    }

    def __init__(self, *args, **kwargs):
        super(LeonardoSpider, self).__init__(*args, **kwargs)
        if not self.start_urls:
            self.start_urls = ["https://leonardo.ru/ishop/"]

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
                        PageMethod("wait_for_timeout", 3000), 
                    ],
                }
            )

    def parse_discovery(self, response):
        """Парсинг структуры категорий из меню"""
        # 1-й уровень
        sections = response.css('a.menu-catalog__section-link')
        for section in sections:
            name = section.css('.menu-catalog__section-title::text').get() or section.css('::text').get()
            url = section.attrib.get('href')
            if not name or not url:
                continue
            
            name = name.strip()
            full_url = response.urljoin(url)
            
            yield CategoryItem(
                name=name,
                title=name,
                url=full_url,
                parent_url=None,
                site_key=self.site_key
            )
        
        # 2-й уровень
        cat_titles = response.css('a.menu-catalog__categorie-title')
        for cat in cat_titles:
            name = cat.css('::text').get()
            url = cat.attrib.get('href')
            if not name or not url:
                continue
            
            name = name.strip()
            full_url = response.urljoin(url)
            
            yield CategoryItem(
                name=name,
                title=name,
                url=full_url,
                parent_url=None,
                site_key=self.site_key
            )

        # 3-й уровень
        sub_cats = response.css('a.menu-catalog__subcategorie-link')
        for sub in sub_cats:
            name = sub.css('::text').get()
            url = sub.attrib.get('href')
            if not name or not url:
                continue
            
            name = name.strip()
            full_url = response.urljoin(url)
            
            yield CategoryItem(
                name=name,
                title=name,
                url=full_url,
                parent_url=None,
                site_key=self.site_key
            )

    def parse_catalog(self, response):
        """Парсинг списка товаров"""
        # Селектор самого товара может варьироваться
        products = response.css('.goods-preview__item') or response.css('.goods-preview')

        for p in products:
            # Ищем заголовок
            title_el = p.css('.goods-preview__title')
            if not title_el:
                continue
                
            title = title_el.css('::text').get() or title_el.attrib.get('title')
            url_path = title_el.attrib.get('href') or p.css('a::attr(href)').get()
            
            if not title or not url_path:
                continue
                
            product_url = response.urljoin(url_path)
            
            # Цена
            price_text = p.css('.sale-price::text').get() or p.css('.goods-preview__price::text').get() or p.css('.goods-preview__original-price::text').get()
            price = self._clean_price(price_text)
            
            # Изображение - пробуем data-src (lazy) потом src
            img_el = p.css('img')
            image_url = img_el.attrib.get('data-src') or img_el.attrib.get('src')
            if image_url:
                image_url = response.urljoin(image_url)

            yield self.create_product(
                title=title.strip(),
                product_url=product_url,
                price=price,
                image_url=image_url,
                merchant="Leonardo"
            )

        # Пагинация
        next_page = response.css('.to-next-state::attr(href)').get()
        if next_page:
            yield scrapy.Request(
                response.urljoin(next_page), 
                callback=self.parse_catalog,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_selector", "body"),
                        PageMethod("wait_for_timeout", 2000), 
                    ],
                }
            )

    def _clean_price(self, price_str):
        if not price_str:
            return None
        # Удаляем лишние символы: ₽, пробелы и т.д.
        clean = re.sub(r'[^\d.]', '', price_str.replace(',', '.'))
        try:
            return float(clean)
        except (ValueError, TypeError):
            return None
