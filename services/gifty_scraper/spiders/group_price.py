from gifty_scraper.base_spider import GiftyBaseSpider


class GroupPriceSpider(GiftyBaseSpider):
    name = "groupprice"
    allowed_domains = ["groupprice.ru"]
    site_key = "groupprice"

    def parse_catalog(self, response):
        # Each product card
        cards = response.css("div._product")

        for card in cards:
            # Prefer data attributes as they contain FULL information (not truncated)
            title = card.attrib.get("data-product-name")
            price = card.attrib.get("data-product-price")
            url = card.css("a::attr(href)").get()
            
            # Image: try to get the one with better quality if possible, 
            # usually replacing 'thumb' with 'original' or just removing 'thumb' works on some CDNs
            image = card.css("img._cover::attr(src)").get()
            if image and "thumb" in image:
                # GroupPrice specific: they have 'thumb.webp', let's see if we can get a larger one
                # Usually 'normal' or 'original' works, but let's keep thumb for safety if not sure,
                # or try to guess. For now, let's just make sure it's absolute.
                pass

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