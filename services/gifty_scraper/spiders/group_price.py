from gifty_scraper.base_spider import GiftyBaseSpider
from gifty_scraper.items import CategoryItem
from urllib.parse import urlparse


class GroupPriceSpider(GiftyBaseSpider):
    name = "group_price"
    allowed_domains = ["groupprice.ru"]
    site_key = "group_price"

    
    def parse_discovery(self, response):
        """
        Parses the gifts hub page to find all specific gift categories (hubs).
        """
        # Page markup changed (Vite/Turbo). Keep discovery resilient by extracting
        # gift landing links from anchors instead of relying on old carousel/grid selectors.
        found_hubs = {}  # url -> name

        def clean_name(n):
            if not n:
                return None
            return " ".join(str(n).split()).strip() or None

        def is_candidate(url: str) -> bool:
            try:
                parsed = urlparse(url)
            except Exception:
                return False
            if parsed.netloc and parsed.netloc not in {"groupprice.ru", "www.groupprice.ru"}:
                return False
            path = parsed.path or ""
            return path.startswith("/l/") or path.startswith("/categories/")

        for a in response.css("a"):
            href = a.attrib.get("href") or ""
            if not href.strip():
                continue
            url = response.urljoin(href.strip())
            if not is_candidate(url):
                continue

            # Skip header category menu links to reduce noise.
            cls = (a.attrib.get("class") or "").strip()
            if cls.split() == ["_link"] or "_category-links" in cls:
                continue
            if "_link" in cls and "_category" in cls:
                continue

            name = clean_name(
                a.attrib.get("title")
                or a.css("img::attr(alt)").get()
                or a.xpath("string(.)").get()
            )
            if not name:
                slug = (urlparse(url).path or "").rstrip("/").split("/")[-1]
                name = clean_name(slug.replace("-", " ").replace("_", " ").title())

            if url:
                found_hubs[url] = name

        self.logger.info(f"Discovery hubs extracted: {len(found_hubs)} from {response.url}")

        for url, name in found_hubs.items():
            # Yield CategoryItem to be saved as a new ParsingSource
            yield self.create_category(
                name=name,
                url=url,
                parent_url=response.url
            )

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

        if self.strategy == "deep":
            next_page = response.css("a.__ajax-pagination::attr(href)").get()
            if not next_page:
                next_page = response.css("nav.pagy a[rel='next']::attr(href)").get()
            if next_page:
                yield response.follow(next_page, self.parse_catalog)
