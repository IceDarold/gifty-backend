from gifty_scraper.base_spider import GiftyBaseSpider
from gifty_scraper.items import CategoryItem


class GroupPriceSpider(GiftyBaseSpider):
    name = "groupprice"
    allowed_domains = ["groupprice.ru"]
    site_key = "groupprice"
    
    def parse_discovery(self, response):
        """
        Parses the gifts hub page to find all specific gift categories (hubs).
        """
        # 1. Try carousel (usually has good text names)
        carousel_links = response.css("div.__carousel a._button")
        # 2. Try grid (has nicer images, but often lacks text)
        grid_links = response.css("div.gifts-grid a")
        
        found_hubs = {} # url -> name

        def clean_name(n):
            return n.strip() if n else None

        # Process carousel first as it has better names
        for hub in carousel_links:
            url = response.urljoin(hub.css("::attr(href)").get())
            name = clean_name(hub.xpath("string(.)").get())
            if url:
                found_hubs[url] = name

        # Process grid to find any missing hubs
        for hub in grid_links:
            url = response.urljoin(hub.css("::attr(href)").get())
            if url and (url not in found_hubs or not found_hubs[url]):
                name = clean_name(hub.css("::attr(title)").get() or \
                                 hub.css("img::attr(alt)").get() or \
                                 hub.xpath("string(following-sibling::p)").get())
                
                if not name:
                    # Fallback: pretty-print the URL slug
                    slug = url.split("/")[-1]
                    name = slug.replace("-", " ").replace("_", " ").title()
                
                found_hubs[url] = name

        for url, name in found_hubs.items():
            # Yield CategoryItem with consistent fields (title, price) for easier viewing
            yield CategoryItem(
                name=name,
                title=f"[Category] {name}",
                price=None,
                url=url,
                parent_url=response.url,
                site_key=self.site_key
            )
            
            # Follow to parse products
            yield response.follow(url, self.parse_catalog)

    def parse_catalog(self, response):
        # Each product card
        cards = response.css("div._product")
        
        # Limit products per page if requested (useful for discovery testing)
        max_products = int(getattr(self, 'max_products', 0))
        if max_products > 0:
            cards = cards[:max_products]
            self.logger.info(f"Limiting to {max_products} products on {response.url}")

        for card in cards:
            # Prefer data attributes as they contain FULL information (not truncated)
            title = card.attrib.get("data-product-name")
            price = card.attrib.get("data-product-price")
            url = card.css("a::attr(href)").get()
            
            # Image: try to get the one with better quality if possible, 
            # usually replacing 'thumb' with 'original' or just removing 'thumb' works on some CDNs
            image = card.css("img._cover::attr(src)").get()
            if image and "thumb" in image:
                # GroupPrice specific: they have 'thumb.webp', removing 'thumb' gives the original image.
                image = image.replace("thumb", "")


            if not title or not url:
                continue

            yield self.create_product(
                title=title.strip(),
                product_url=response.urljoin(url),
                price=price,
                image_url=response.urljoin(image) if image else None,
                merchant="GroupPrice",
                raw_data={
                    "source": "scrapy_v1"
                }
            )

        # Pagination (only in deep mode)
        if self.strategy == "deep":
            next_page = response.css("a.__ajax-pagination::attr(href)").get()
            if not next_page:
                next_page = response.css("nav.pagy a[rel='next']::attr(href)").get()
            if next_page:
                yield response.follow(next_page, self.parse_catalog)