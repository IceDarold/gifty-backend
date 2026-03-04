from gifty_scraper.base_spider import GiftyBaseSpider
from gifty_scraper.items import CategoryItem


class ColapsarSpider(GiftyBaseSpider):
    name = "colapsar"
    allowed_domains = ["colapsar.ru"]
    site_key = "colapsar"

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'DEFAULT_REQUEST_HEADERS': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US,en;q=0.8',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.google.com/',
        },
        'DOWNLOAD_DELAY': 0.5,
    }

    def parse_discovery(self, response):
        """
        Parses the catalog page or category hub to find all category links.
        """
        # Look for links that belong to the catalog
        # The structure seen in curl: <li id="bx_..."><a href="/catalog/...">...</a></li>
        links = response.css('li a[href*="/catalog/"]')
        
        found_urls = set()
        for link in links:
            href = link.css("::attr(href)").get()
            url = response.urljoin(href)
            name = link.css("::text").get()
            
            # Avoid self-references and duplicates
            if url and url != response.url and "/catalog/filter/" not in url and url not in found_urls:
                found_urls.add(url)
                
                if self.strategy == "discovery":
                    yield CategoryItem(
                        name=name.strip() if name else None,
                        url=url,
                        parent_url=response.url,
                        site_key=self.site_key
                    )
                else:
                    # In deep mode, follow the link to scrape products
                    yield response.follow(url, self.parse_catalog)

    def parse_catalog(self, response):
        """
        Parses a category page for product cards and handles pagination/subcategories.
        """
        cards = response.css("div.card")
        
        # Limit products if max_products is set
        max_products = int(getattr(self, 'max_products', 0))
        if max_products > 0:
            cards = cards[:max_products]

        # Extract products from the current page
        for card in cards:
            title_el = card.css("a.card__title")
            title = title_el.css("::text").get()
            url = title_el.css("::attr(href)").get()
            
            price = card.css(".card__price span.price_base::text").get()
            if price:
                price = "".join(filter(lambda x: x.isdigit() or x == '.' or x == ',', price))
                price = price.replace(",", ".")
            
            image = card.css(".card__image img::attr(src)").get()
            
            if title and url:
                yield self.create_product(
                    title=title.strip(),
                    product_url=response.urljoin(url),
                    price=price if price else "0",
                    image_url=response.urljoin(image) if image else None,
                    merchant="Colapsar",
                    raw_data={"source": "scrapy_v1"}
                )

        # Also look for subcategories to crawl deeper
        if self.strategy != "discovery":
            yield from self.parse_discovery(response)

        # Handle Pagination
        if self.strategy in ["deep", "discovery"]:
            next_page = response.css("li.bx-pag-next a::attr(href)").get()
            if next_page:
                yield response.follow(next_page, self.parse_catalog)
