import scrapy
from gifty_scraper.items import ProductItem, CategoryItem

class GiftyBaseSpider(scrapy.Spider):
    """
    Базовый класс для всех пауков Gifty.
    Автоматически обрабатывает входные параметры и стратегии.
    """
    site_key = None  # Должен быть переопределен в потомке

    def __init__(self, url=None, strategy="deep", source_id=None, *args, **kwargs):
        super(GiftyBaseSpider, self).__init__(*args, **kwargs)
        self.start_urls = [url] if url else []
        self.strategy = strategy
        self.source_id = source_id

    def parse(self, response):
        if self.strategy == "discovery":
            yield from self.parse_discovery(response)
        else:
            yield from self.parse_catalog(response)

    def parse_catalog(self, response):
        """Парсинг списка товаров и пагинация"""
        raise NotImplementedError

    def parse_discovery(self, response):
        """Парсинг структуры категорий (Hub)"""
        raise NotImplementedError

    def create_product(self, **kwargs):
        """Helper для создания ProductItem с общими полями"""
        product = ProductItem()
        for key, value in kwargs.items():
            product[key] = value
        
        product['site_key'] = self.site_key
        product['source_id'] = self.source_id
        return product
