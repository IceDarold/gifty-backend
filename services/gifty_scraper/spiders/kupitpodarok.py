import scrapy
import json
import re
from gifty_scraper.base_spider import GiftyBaseSpider
from gifty_scraper.items import CategoryItem


class KupitPodarokSpider(GiftyBaseSpider):
    name = "kupitpodarok"
    allowed_domains = ["kupitpodarok.ru"]
    site_key = "kupitpodarok"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    }

    def __init__(self, *args, **kwargs):
        super(KupitPodarokSpider, self).__init__(*args, **kwargs)
        if not self.start_urls:
            self.start_urls = ["https://kupitpodarok.ru/catalog/neobychnye_podarki/"]

    def parse(self, response):
        """Основная точка входа. По умолчанию Bitrix вываливает весь каталог в window.catalog."""
        # Ищем блок window.catalog = [...]
        match = re.search(r'window\.catalog\s*=\s*(\[.*?\]);', response.text, re.DOTALL)
        if match:
            try:
                catalog_raw = match.group(1).strip()
                # Пытаемся распарсить как стандартный JSON
                catalog = json.loads(catalog_raw)
                
                self.logger.info(f"Successfully extracted {len(catalog)} products from window.catalog")
                
                if self.strategy == "discovery":
                    yield from self.extract_categories_from_catalog(catalog, response)
                
                for item in catalog:
                    yield self.parse_item_json(item, response)
                return 
            except Exception as e:
                self.logger.error(f"Failed to parse window.catalog JSON: {e}")

        # Фолбэк на обычный парсинг селекторами
        self.logger.info("Using CSS selectors fallback")
        yield from super().parse(response)

    def extract_categories_from_catalog(self, catalog, response):
        """Извлечение уникальных категорий из глобального списка товаров"""
        seen_cats = set()
        for item in catalog:
            cat_name = item.get("CATEGORY")
            if not cat_name or cat_name in seen_cats:
                continue
            seen_cats.add(cat_name)
            
            yield CategoryItem(
                name=cat_name,
                title=cat_name,
                url=response.urljoin(f"/catalog/?q={cat_name}"),
                parent_url=None,
                site_key=self.site_key
            )

    def parse_item_json(self, item, response):
        """Парсинг одного товара из JSON объекта"""
        title = item.get("NAME")
        url_path = item.get("URL")
        if not url_path:
            return None
            
        product_url = response.urljoin(url_path)
        
        # Разные сайты на Bitrix могут использовать разные ключи
        price = item.get("PRICE") or item.get("DISCOUNT_PRICE") or item.get("BASE_PRICE")
        image_url = response.urljoin(item.get("IMG"))
        
        return self.create_product(
            title=title.strip() if title else "Без названия",
            product_url=product_url,
            price=self._clean_price(price),
            image_url=image_url,
            merchant="КупитьПодарок",
            raw_data={
                "product_id": item.get("ID"),
                "category": item.get("CATEGORY"),
                "source": "kupitpodarok_json"
            }
        )

    def parse_catalog(self, response):
        """Фолбэк парсинг селекторами для товаров"""
        cards = response.css('div.b-catalog-box.product-js, .b-catalog-1emotion')
        for card in cards:
            title_node = card.css('.b-catalog-box__title, .b-catalog-1emotion__title')
            title = title_node.css('::text').get() or title_node.xpath('.//text()').get()
            product_url = response.urljoin(title_node.css('::attr(href)').get())
            price_text = card.css('.b-catalog-box__offer-default-price ::text, .b-catalog-1emotion__offer-default-price ::text').get()
            image_url = response.urljoin(card.css('.b-catalog-box__img-link img::attr(src), .b-catalog-1emotion__img img::attr(src)').get())
            
            if title and product_url:
                yield self.create_product(
                    title=title.strip(),
                    product_url=product_url,
                    price=self._clean_price(price_text),
                    image_url=image_url,
                    merchant="КупитьПодарок",
                    raw_data={"source": "kupitpodarok_html"}
                )

    def _clean_price(self, value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        # Если пришла строка
        clean = re.sub(r'[^\d.]', '', value.replace(',', '.'))
        try:
            return float(clean) if clean else None
        except ValueError:
            return None
