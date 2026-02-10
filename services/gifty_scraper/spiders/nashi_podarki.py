from gifty_scraper.base_spider import GiftyBaseSpider
from gifty_scraper.items import CategoryItem


class NashiPodarkiSpider(GiftyBaseSpider):
    name = "nashipodarki"
    allowed_domains = ["nashipodarki.ru"]
    site_key = "nashipodarki"

    def parse_discovery(self, response):
        """
        Parses the main gifts page to find subcategories.
        """
        # Subcategories are usually listed in the side menu or main content
        # Looking for links in the menu or sections list
        hubs = response.css("li.menu-item a")
        
        # If menu-item is not found, try the sections grid if any
        if not hubs:
             hubs = response.css(".sections-list .item a")

        found_urls = set()
        for hub in hubs:
            url = response.urljoin(hub.css("::attr(href)").get())
            name = hub.css("span.name::text").get() or hub.css("::attr(title)").get()
            
            if url and "/catalog/" in url and url != response.url and url not in found_urls:
                found_urls.add(url)
                yield CategoryItem(
                    name=name.strip() if name else None,
                    url=url,
                    parent_url=response.url,
                    site_key=self.site_key
                )

    def parse_catalog(self, response):
        """
        Parses a category page for product cards.
        """
        cards = response.css("div.item_block")
        
        max_products = int(getattr(self, 'max_products', 0))
        if max_products > 0:
            cards = cards[:max_products]
            self.logger.info(f"Limiting to {max_products} products on {response.url}")

        for card in cards:
            # Title and URL
            title_el = card.css(".item-title a")
            title = title_el.css("::attr(title)").get() or title_el.css("span::text").get() or title_el.xpath("string(.)").get()
            url = title_el.css("::attr(href)").get()
            
            # Price
            price = card.css(".price_value::text").get()
            if price:
                # Remove spaces and currency symbol if needed (usually Bitrix stores raw digits here or formatted text)
                price = price.replace(" ", "").replace("\xa0", "")
            
            # Image
            image = card.css("img.lazy::attr(data-src)").get() or card.css("img::attr(src)").get()
            
            if not title or not url:
                continue

            yield self.create_product(
                title=title.strip(),
                product_url=response.urljoin(url),
                price=price,
                image_url=response.urljoin(image) if image else None,
                merchant="NashiPodarki",
                raw_data={
                    "source": "scrapy_v1"
                }
            )

        # Pagination
        if self.strategy in ["deep", "discovery"]:
            next_page = response.css("div.nums a.next::attr(href)").get()
            if next_page:
                yield response.follow(next_page, self.parse_catalog)
