import scrapy
import json
import re
from gifty_scraper.base_spider import GiftyBaseSpider


class MVideoSpider(GiftyBaseSpider):
    name = "mvideo"
    allowed_domains = ["mvideo.ru", "www.mvideo.ru"]
    site_key = "mvideo"
    
    # Discovery strategy uses this to find category links
    category_selector = 'a[href*="/catalog/"], a.category-card__name, a.catalog-navigation-list__link, a.f-menu__link'

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 2.0,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'DEFAULT_REQUEST_HEADERS': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9',
            'Referer': 'https://www.mvideo.ru/',
            'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        },
        'COOKIES_ENABLED': True
    }

    def __init__(self, url=None, strategy="deep", source_id=None, *args, **kwargs):
        # Default to "all categories" if no URL provided
        if not url:
            url = "https://www.mvideo.ru/vse-kategorii"
        super(MVideoSpider, self).__init__(url=url, strategy=strategy, source_id=source_id, *args, **kwargs)

    def parse_catalog(self, response):
        """
        Parses the catalog page for M.Video.
        Attempts to use both CSS selectors and __NEXT_DATA__ if available.
        """
        self.logger.info(f"Parsing catalog: {response.url}")

        # 1. Attempt to extract data from __NEXT_DATA__ (Next.js specific)
        next_data_script = response.xpath('//script[@id="__NEXT_DATA__"]/text()').get()
        if next_data_script:
            try:
                data = json.loads(next_data_script)
                products_from_json = self._extract_from_next_data(data)
                if products_from_json:
                    self.logger.info(f"Extracted {len(products_from_json)} products from __NEXT_DATA__")
                    for p in products_from_json:
                        yield self.create_product(**p)
                    
                    # If we got products from JSON, we might still want to check for pagination
                    # often JSON contains the next page info too.
            except Exception as e:
                self.logger.error(f"Error parsing __NEXT_DATA__: {e}")

        # 2. Fallback to CSS Selectors
        # MVideo uses custom elements or standard layout depending on the version/experiment
        cards = response.css('mvid-product-card, .product-cards-layout__item, .product-card, .product-tile')
        
        found_css_count = 0
        for card in cards:
            title = card.css('.product-title__text::text').get() or \
                    card.css('a.mvid-product-card__title::text').get() or \
                    card.css('.product-tile__title::text').get()
            
            url = card.css('a.product-title__text::attr(href)').get() or \
                  card.css('a.mvid-product-card__title::attr(href)').get() or \
                  card.css('a.product-tile__title::attr(href)').get()
            
            price_text = card.css('.price__main-value::text').get() or \
                         card.css('.product-tile__price::text').get()
            
            current_price = None
            if price_text:
                current_price = "".join(re.findall(r'\d+', price_text))

            image = card.css('.product-card-image__img::attr(src)').get() or \
                    card.css('img.mvid-product-card-image__img::attr(src)').get() or \
                    card.css('.product-card-image__img::attr(data-src)').get() or \
                    card.css('.product-tile__image::attr(src)').get()

            if title and url:
                found_css_count += 1
                yield self.create_product(
                    title=title.strip(),
                    product_url=response.urljoin(url),
                    price=current_price,
                    image_url=response.urljoin(image) if image else None,
                    merchant="М.Видео",
                    raw_data={"source": "scrapy_v1_css"}
                )

        if not next_data_script and found_css_count == 0:
            self.logger.warning(f"No products found on {response.url}. The site might be blocking or using dynamic rendering.")

        # 3. Pagination
        if self.strategy in ["deep", "discovery"]:
            next_page = response.css('a.pagination-button--next::attr(href)').get() or \
                        response.css('.pagination__next a::attr(href)').get() or \
                        response.xpath('//a[contains(@class, "pagination") and contains(., "Дальше")]/@href').get() or \
                        response.xpath('//link[@rel="next"]/@href').get()
            
            if next_page:
                next_page_url = response.urljoin(next_page)
                if next_page_url != response.url:
                    self.logger.info(f"Following next page: {next_page_url}")
                    yield response.follow(next_page_url, self.parse_catalog)

    def _extract_from_next_data(self, data):
        """
        Heuristic to extract products from Next.js initial state.
        The exact path can change frequently.
        """
        products = []
        try:
            # Common paths in M.Video Next.js props
            page_props = data.get('props', {}).get('pageProps', {})
            
            # Path 1: initialData in products
            listing_data = page_props.get('initialData', {}).get('products', [])
            
            # Path 2: listing state in initialState
            if not listing_data:
                listing_data = page_props.get('initialState', {}).get('listing', {}).get('products', [])

            # Path 3: search results
            if not listing_data:
                 listing_data = page_props.get('initialState', {}).get('search', {}).get('products', [])

            for item in listing_data:
                p_id = item.get('productId') or item.get('id')
                name = item.get('name') or item.get('title')
                
                # Construct URL if not present
                p_url = item.get('productUrl') or item.get('url')
                if p_url and not p_url.startswith('http'):
                    p_url = f"https://www.mvideo.ru{p_url}"
                elif not p_url and p_id:
                    p_url = f"https://www.mvideo.ru/products/{p_id}"

                price = item.get('price', {}).get('salePrice') or item.get('salePrice')
                image = item.get('image') or item.get('imageUrl')
                if image and not image.startswith('http'):
                    image = f"https://static.mvideo.ru{image}"

                if name and p_url:
                    products.append({
                        "title": name,
                        "product_url": p_url,
                        "price": str(price) if price else None,
                        "image_url": image,
                        "merchant": "М.Видео",
                        "raw_data": {"source": "next_data", "id": p_id}
                    })
        except Exception:
            pass
        return products
