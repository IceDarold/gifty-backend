import scrapy
import re
from gifty_scraper.base_spider import GiftyBaseSpider


class RusBuketSpider(GiftyBaseSpider):
    name = "rus_buket"
    allowed_domains = ["rus-buket.ru"]
    site_key = "rus_buket"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.5,
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    }

    def __init__(self, *args, **kwargs):
        super(RusBuketSpider, self).__init__(*args, **kwargs)
        if not self.start_urls:
            # По умолчанию парсим "все товары", но можно передать конкретную категорию через -a url=...
            self.start_urls = ["https://rus-buket.ru/all-products"]

    def parse_catalog(self, response):
        """Парсинг списка товаров"""
        cards = response.css('.rb-product-card')
        self.logger.info(f"Found {len(cards)} product cards on {response.url}")

        for card in cards:
            title_node = card.css('.rb-product-card__name')
            title = title_node.css('::text').get()
            product_url = response.urljoin(title_node.css('::attr(href)').get())
            
            # Предпочитаем брать чистую цену из атрибута data-price
            price = card.attrib.get('data-price')
            
            if not price:
                # Фолбэк на текстовые селекторы
                price_text = card.css('.rb-product-card__price-actual::text').get() or \
                             card.css('.rb-price-actual::text').get() or \
                             card.css('.rb-product-card__price-box::text').get()
                
                if not price_text:
                    price_text = "".join(card.css('.rb-product-card__price-box *::text').getall())
                price = self._clean_price(price_text)
            else:
                price = float(price)
            
            # Изображение бывает в разных местах в зависимости от слайдера
            image_url = card.css('.product-card__slide-img::attr(data-src)').get() or \
                        card.css('.product-card__slide-img::attr(src)').get() or \
                        card.css('.rb-product-card__image img::attr(src)').get()
            
            # id товара
            product_id = card.attrib.get('data-id')

            if title and product_url:
                yield self.create_product(
                    title=title.strip(),
                    product_url=product_url,
                    price=price,
                    image_url=response.urljoin(image_url),
                    merchant="Русский Букет",
                    raw_data={
                        "product_id": product_id,
                        "source": "rus_buket_listing"
                    }
                )

        # Пагинация
        next_page = response.css('a[rel="next"]::attr(href)').get() or \
                    response.css('.pagination__next::attr(href)').get()
        
        if next_page:
            yield response.follow(next_page, self.parse_catalog)

    def parse_discovery(self, response):
        """Дискавери категорий из меню и футера"""
        # Ссылки из главного меню
        catalog_links = response.css('.rb-menu a, .rb-menu__head-item')
        for link in catalog_links:
            name = link.css('::text').get()
            url = response.urljoin(link.attrib.get('href'))
            
            if name and url and not url.endswith('#'):
                # Очищаем название от лишних тегов (Новинка, Хит)
                name = re.sub(r'Новинка|Хит продаж', '', name).strip()
                if name:
                    yield self.create_category(
                        name=name,
                        url=url,
                        site_key=self.site_key
                    )

    def _clean_price(self, value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        
        # Удаляем неразрывные пробелы и прочий мусор
        value = value.replace('\xa0', ' ').replace('&nbsp;', ' ')
        # Оставляем только цифры, точки и запятые
        clean = re.sub(r'[^\d.,]', '', value)
        
        # Заменяем запятую на точку для float
        clean = clean.replace(',', '.')
        
        # Если в строке несколько точек (например, 1.250.00), оставляем только последнюю или удаляем все кроме цифр
        if clean.count('.') > 1:
            clean = re.sub(r'[^\d]', '', clean)
            
        try:
            return float(clean) if clean else None
        except ValueError:
            return None
