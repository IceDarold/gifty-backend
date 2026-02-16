import scrapy
import lxml.etree as ET
import re
from gifty_scraper.base_spider import GiftyBaseSpider
from gifty_scraper.items import ProductItem, CategoryItem

class PlatiMarketSpider(GiftyBaseSpider):
    name = "plati_market"
    allowed_domains = ["plati.market"]
    site_key = "plati_market"
    
    # Используем "тестовые" эндпоинты, так как они работают без guid_agent
    SECTIONS_URL = "https://plati.market/xml/test_sections.asp?l=ru-RU"
    GOODS_URL = "https://plati.market/xml/test_goods.asp?id_cat={cat_id}&pagenum={page}&l=ru-RU"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.2,
    }

    def start_requests(self):
        if self.strategy == "discovery":
            yield scrapy.Request(self.SECTIONS_URL, callback=self.parse_discovery)
        else:
            for url in self.start_urls:
                cat_id = self._extract_cat_id(url)
                if cat_id:
                    yield scrapy.Request(
                        self.GOODS_URL.format(cat_id=cat_id, page=1),
                        callback=self.parse_catalog,
                        meta={"cat_id": cat_id, "page": 1}
                    )
                else:
                    # Если передан корень или нераспознанный URL, пробуем дискавери
                    yield scrapy.Request(self.SECTIONS_URL, callback=self.parse_discovery)

    def parse_discovery(self, response):
        """Парсинг списка категорий из XML"""
        try:
            # lxml автоматически определит кодировку из декларации <?xml ... encoding="windows-1251"?>
            parser = ET.XMLParser(recover=True)
            root = ET.fromstring(response.body, parser=parser)
        except Exception as e:
            self.logger.error(f"Failed to parse XML from {response.url}: {e}")
            return

        # Рекурсивный обход папок и уровней
        for folder in root.xpath("//folder"):
            folder_id = folder.get("id")
            folder_name = folder.findtext("name_folder")
            
            if not folder_id or not folder_name:
                continue

            # Формируем читаемый URL для категории
            folder_url = f"https://plati.market/cat/-/{folder_id}/"
            
            yield CategoryItem(
                name=folder_name,
                title=folder_name,
                url=folder_url,
                parent_url=None,
                site_key=self.site_key
            )
            
            # Подсекции
            for section in folder.xpath("section"):
                section_id = section.get("id")
                section_name = section.findtext("name_section")
                
                if not section_id or not section_name:
                    continue

                yield CategoryItem(
                    name=section_name,
                    title=section_name,
                    url=f"https://plati.market/cat/-/{section_id}/",
                    parent_url=folder_url,
                    site_key=self.site_key
                )

    def parse_catalog(self, response):
        """Парсинг списка товаров из XML"""
        try:
            parser = ET.XMLParser(recover=True)
            root = ET.fromstring(response.body, parser=parser)
        except Exception as e:
            self.logger.error(f"Failed to parse XML from {response.url}: {e}")
            return

        cat_id = response.meta.get("cat_id")
        current_page = response.meta.get("page")
        
        rows = root.xpath("//row")
        self.logger.info(f"Parsed {len(rows)} items from category {cat_id} (Page {current_page})")

        for item in rows:
            id_goods = item.findtext("id_goods")
            if not id_goods:
                continue

            name = item.findtext("name_goods")
            price_str = item.findtext("price")
            currency = item.findtext("currency")
            
            # Очистка цены (453,37 -> 453.37)
            price = None
            if price_str:
                try:
                    price = float(price_str.replace(",", "."))
                except ValueError:
                    pass

            product_url = f"https://plati.market/itm/-/{id_goods}"
            
            # Предсказуемый URL изображения через CDN Digiseller (с высоким качеством)
            image_url = f"https://digiseller.mycdn.ink/imgwebp.ashx?w=400&h=400&id_d={id_goods}"
            
            # Статистика продаж
            sales_cnt = item.xpath("statistics/cnt_sell/text()")
            sales_cnt = sales_cnt[0] if sales_cnt else "0"

            yield self.create_product(
                title=name,
                product_url=product_url,
                price=price,
                currency=currency,
                image_url=image_url,
                merchant="Plati.Market",
                raw_data={
                    "item_id": id_goods,
                    "sales_cnt": sales_cnt,
                    "seller_name": item.findtext("name_seller"),
                    "seller_id": item.findtext("id_seller")
                }
            )
            
        # Пагинация (проверяем наличие следующей страницы)
        # В тестовом API может не быть блока <pages>, проверим по количеству товаров на странице
        # Обычно rows=100 или 20. Если мы получили товары, пробуем следующую страницу (до лимита)
        if len(rows) > 0 and self.strategy in ["deep", "discovery"]:
            next_page = current_page + 1
            if next_page <= 50: # Лимит для безопасности
                yield scrapy.Request(
                    self.GOODS_URL.format(cat_id=cat_id, page=next_page),
                    callback=self.parse_catalog,
                    meta={"cat_id": cat_id, "page": next_page}
                )

    def _extract_cat_id(self, url):
        """Извлечение ID категории из URL"""
        # https://plati.market/cat/games/51/
        match = re.search(r'/cat/[^/]+/(\d+)/', url)
        if match:
            return match.group(1)
        # https://plati.market/cat/51/
        match = re.search(r'/cat/(\d+)/', url)
        if match:
            return match.group(1)
        return None
