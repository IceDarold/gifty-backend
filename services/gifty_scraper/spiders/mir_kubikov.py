import scrapy
import re
from gifty_scraper.base_spider import GiftyBaseSpider
from gifty_scraper.items import CategoryItem

class MirKubikovSpider(GiftyBaseSpider):
    name = "mir_kubikov"
    allowed_domains = ["mir-kubikov.ru"]
    site_key = "mir_kubikov"
    
    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2.5,
    }

    def parse_discovery(self, response):
        """Парсинг категорий каталога"""
        category_links = response.css('a.g-nav-categories__item-link, .g-nav-submenu__item-link, a[href^="/catalog/"]')
        seen = set()
        for link in category_links:
            url = response.urljoin(link.css("::attr(href)").get())
            if not url or url in seen or url == response.url or "/catalog/" not in url:
                continue
            
            if re.search(r'/catalog/\d+/', url) or "?" in url:
                continue
                
            seen.add(url)
            name = link.css("::text").get() or link.xpath(".//text()").get()
            name = name.strip() if name else None
            
            if not name or len(name) < 2:
                continue

            yield CategoryItem(
                name=name,
                title=name,
                url=url,
                parent_url=response.url,
                site_key=self.site_key
            )

    def parse_catalog(self, response):
        """Парсинг списка товаров на странице категории"""
        cards = response.css('.g-card')
        self.logger.info(f"Parsing Mir-Kubikov catalog: {response.url}, found {len(cards)} items")
        
        for card in cards:
            data_layer = card.css('.js-datalayer-data')
            
            title = data_layer.attrib.get('data-product-name') or \
                    card.css('a.g-card__name::text').get() or \
                    card.css('.g-card__name::text').get()
            
            product_url = response.urljoin(card.css('a.g-card__name::attr(href)').get() or \
                                         card.css('.g-card__name::attr(href)').get())
            
            price_str = data_layer.attrib.get('data-price')
            price = float(price_str) if price_str and price_str.isdigit() else None
            
            if not price:
                price_text = card.css('.g-card__purchase__sum span::text').get()
                price = self._clean_price(price_text)
            
            image_url = self._extract_image(card, response)
            
            series_info = card.css('.g-card__title a::text').get() or \
                          card.css('.g-text-link::text').get()
            
            if not title or not product_url:
                continue
                
            yield self.create_product(
                title=title.strip(),
                product_url=product_url,
                price=price,
                image_url=image_url,
                merchant="Мир Кубиков",
                raw_data={
                    "series": series_info.strip() if series_info else None,
                    "product_id": data_layer.attrib.get('data-product-id'),
                    "source": "mir-kubikov"
                }
            )
            
        if self.strategy in ["deep", "discovery"]:
            current_page_match = re.search(r'PAGEN_1=(\d+)', response.url)
            current_page = int(current_page_match.group(1)) if current_page_match else 1
            
            next_page_num = current_page + 1
            next_link = response.css(f'.catalog-pages a.page[data-url="{next_page_num}"]::attr(href)').get() or \
                        response.css('.g-pagination__next::attr(href)').get()
            
            if next_link:
                yield response.follow(next_link, callback=self.parse_catalog)
            elif len(cards) >= 12: 
                if next_page_num <= 100:
                    base_url = response.url.split('?')[0]
                    next_url = f"{base_url}?PAGEN_1={next_page_num}"
                    yield response.follow(next_url, callback=self.parse_catalog)

    def _extract_image(self, card, response):
        """Извлечение URL изображения с учетом ленивой загрузки"""
        for attr in ['srcset', 'data-src', 'data-original', 'lazy-src', 'data-srcset']:
            val = card.css(f'.g-card__img::attr({attr})').get() or \
                  card.css(f'.g-card__img-wrapper img::attr({attr})').get()
            if val:
                if 'srcset' in attr:
                    parts = val.split(',')
                    if parts:
                        first_url = parts[0].strip().split(' ')[0]
                        if first_url and not first_url.startswith('data:'):
                            return response.urljoin(first_url)
                elif not val.startswith('data:'):
                    return response.urljoin(val)
        
        image_url = card.css('.g-card__img::attr(src)').get() or \
                    card.css('.g-card__img-wrapper img::attr(src)').get()
        
        if image_url and not image_url.startswith('data:'):
            return response.urljoin(image_url)
            
        return None

    def _clean_price(self, price_str):
        if not price_str:
            return None
        price_digits = re.sub(r'[^\d]', '', price_str)
        try:
            return float(price_digits) if price_digits else None
        except ValueError:
            return None
