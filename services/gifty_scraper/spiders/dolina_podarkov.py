import scrapy
import json
from gifty_scraper.base_spider import GiftyBaseSpider


class DolinaPodarkovSpider(GiftyBaseSpider):
    name = "dolina_podarkov"
    allowed_domains = ["www.dolina-podarkov.ru", "dolina-podarkov.ru"]
    site_key = "dolina_podarkov"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    }

    def __init__(self, *args, **kwargs):
        super(DolinaPodarkovSpider, self).__init__(*args, **kwargs)
        if not self.start_urls:
            url = kwargs.get("url") or "https://www.dolina-podarkov.ru/catalog/nachalyniku-38"
            self.start_urls = [url]

    def parse_catalog(self, response):
        """Основной метод парсинга листинга товаров"""
        
        # Сначала пробуем извлечь данные из JSON-LD
        ld_json_scripts = response.xpath('//script[@type="application/ld+json"]/text()').getall()
        found_products = False
        
        for script_text in ld_json_scripts:
            try:
                data = json.loads(script_text)
                # JSON-LD может быть объектом или списком объектов
                items = data if isinstance(data, list) else [data]
                
                item_list = next((i for i in items if i.get("@type") == "ItemList"), None)
                if item_list and "itemListElement" in item_list:
                    for element in item_list["itemListElement"]:
                        product_data = element.get("item")
                        if product_data and product_data.get("@type") == "Product":
                            offer = product_data.get("offers", {})
                            
                            yield self.create_product(
                                title=product_data.get("name"),
                                product_url=response.urljoin(product_data.get("url")),
                                price=self._clean_price(offer.get("price")),
                                image_url=response.urljoin(product_data.get("image")),
                                merchant="Долина Подарков",
                                raw_data={"source": "ld+json"}
                            )
                            found_products = True
                    
                    if found_products:
                        break
            except Exception as e:
                self.logger.error(f"Error parsing LD+JSON: {e}")

        # Если JSON-LD не сработал или пуст, используем селекторы
        if not found_products:
            self.logger.info("Falling back to CSS selectors")
            for card in response.css('a.group[href*="/product/"]'):
                # На основе увиденного в браузере
                title = card.css('div:nth-child(2) > div:nth-child(2)::text').get()
                price_text = card.css('div:nth-child(2) > div:first-child span:first-child::text').get()
                image_url = card.css('img::attr(src)').get()
                
                if title:
                    yield self.create_product(
                        title=title.strip(),
                        product_url=response.urljoin(card.attrib.get('href')),
                        price=self._clean_price(price_text),
                        image_url=response.urljoin(image_url),
                        merchant="Долина Подарков",
                        raw_data={"source": "selectors"}
                    )

        # Пагинация
        next_page = response.css('a[aria-label="Следующая страница"]::attr(href)').get()
        if next_page:
            yield response.follow(next_page, self.parse_catalog)

    def _clean_price(self, value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        # Если пришла строка, удаляем все кроме цифр и точек
        import re
        clean = re.sub(r'[^\d.]', '', value.replace(',', '.'))
        try:
            return float(clean) if clean else None
        except ValueError:
            return None

    def parse_discovery(self, response):
        """Дискавери категорий из меню"""
        # Ищем ссылки в основном меню каталога
        # На основе скриншота, там есть кнопка "Каталог товаров"
        # Мы можем собрать все ссылки из разделов каталога
        for link in response.css('a[href*="/catalog/"]'):
            name = link.css('::text').get()
            url = response.urljoin(link.attrib['href'])
            
            if name and "/catalog/" in url:
                yield self.create_category(
                    name=name.strip(),
                    url=url,
                    site_key=self.site_key
                )
