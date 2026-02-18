import scrapy
from gifty_scraper.items import ProductItem, CategoryItem

from gifty_scraper.redis_logger import setup_redis_logging

class GiftyBaseSpider(scrapy.Spider):
    """
    Базовый класс для всех пауков Gifty.
    Автоматически обрабатывает входные параметры и стратегии.
    """
    site_key = None  # Должен быть переопределен в потомке

    def __init__(self, url=None, strategy="deep", source_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.url = url
        self.strategy = strategy
        self.source_id = source_id
        
        # If url provided in init, set start_urls
        if self.url:
            self.start_urls = [self.url]
        
        # Enable live logging if source_id is provided
        if self.source_id:
            try:
                setup_redis_logging(self)
                self.logger.info(f"Live logging enabled for source {self.source_id}")
            except Exception:
                pass  # Ignore if redis/logging setup fails in tests

    def log_progress(self, message: str):
        """Helper for showing clean progress in the UI"""
        self.logger.info(f"[PROGRESS] {message}")




    def parse(self, response):
        """Распределяет логику в зависимости от стратегии."""
        if self.strategy == "discovery":
            self.logger.info("Running DISCOVERY strategy on %s", response.url)
            yield from self.parse_discovery(response)
        else:
            self.logger.info("Running DEEP parsing strategy on %s", response.url)
            yield from self.parse_catalog(response)

    def parse_catalog(self, response):
        """Парсинг списка товаров и пагинация. Должен быть переопределен."""
        raise NotImplementedError

    def parse_discovery(self, response):
        """Парсинг структуры категорий (Hub). Должен быть переопределен."""
        raise NotImplementedError

    def create_product(self, **kwargs):
        """Helper для создания ProductItem с общими полями"""
        product = ProductItem()
        for key, value in kwargs.items():
            if key in product.fields:
                product[key] = value
        
        if 'title' in kwargs and 'name' not in kwargs:
            product['name'] = kwargs['title']
        elif 'name' in kwargs and 'title' not in kwargs:
            product['title'] = kwargs['name']
        
        product['site_key'] = self.site_key
        product['source_id'] = self.source_id
        return product

    def create_category(self, url, name=None, title=None, parent_url=None):
        """Helper для создания CategoryItem"""
        item = CategoryItem()
        item['url'] = url
        item['name'] = name or title
        item['title'] = title or name
        item['parent_url'] = parent_url or self.url
        item['site_key'] = self.site_key
        return item
