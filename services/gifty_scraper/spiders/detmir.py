import re
import json
from gifty_scraper.base_spider import GiftyBaseSpider
from gifty_scraper.items import CategoryItem


class DetmirSpider(GiftyBaseSpider):
    name = "detmir"
    allowed_domains = ["detmir.ru"]
    site_key = "detmir"
    category_selector = 'a[data-testid^="category-"], a[href*="/catalog/index/name/"]'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'DEFAULT_REQUEST_HEADERS': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Upgrade-Insecure-Requests': '1',
        }
    }

    def parse_discovery(self, response):
        """
        Parse sitemap / hub pages and return CategoryItem entries.
        """
        links = response.css(self.category_selector)
        seen = set()

        for link in links:
            url = response.urljoin(link.css("::attr(href)").get())
            if not url or url in seen or url == response.url:
                continue
            seen.add(url)

            name = link.css("::text").get()
            name = name.strip() if name else None

            yield CategoryItem(
                name=name,
                title=name,
                url=url,
                parent_url=response.url,
                site_key=self.site_key,
            )

    def parse_catalog(self, response):
        """
        Parses the catalog page.
        """
        self.logger.info(f"Parsing catalog: {response.url}")

        # Extract product data from JSON state (essential for lazy-loaded items after the first 4)
        image_lookup = {}
        try:
            # Look for window.appData = JSON.parse("...") which contains the full product list for the page
            match = re.search(r'window\.appData = JSON\.parse\("(.*?)"\)', response.text)
            if match:
                # The content is a JSON string escaped for JS (e.g. \" instead of ")
                json_raw = match.group(1)
                json_str = json_raw.encode('utf-8').decode('unicode_escape')
                app_data = json.loads(json_str)
                
                # Path to products varies but catalog.data.items is common for listing pages
                items = app_data.get('catalog', {}).get('data', {}).get('items', [])
                for item in items:
                    pid = str(item.get('id') or item.get('productId') or "")
                    if pid:
                        pics = item.get('pictures', [])
                        if pics:
                            # Try to find a good image URL in the JSON
                            img_url = pics[0].get('web') or pics[0].get('original')
                            if img_url:
                                image_lookup[pid] = img_url
        except Exception as e:
            self.logger.debug(f"Failed to extract image_lookup from appData: {e}")
        
        # Detmir uses section tags for product cards
        cards = response.css('section[id^="product-"]')
        
        if not cards:
            self.logger.warning(f"No product cards found on {response.url}")
            return

        for card in cards:
            # Title and Link
            title_link = card.css('a[data-testid="titleLink"]')
            title = title_link.xpath('.//text()').get()
            url = title_link.css('::attr(href)').get()
            
            # Price
            price_nodes = card.css('[data-testid="productPrice"] *::text').getall()
            price_str = "".join(price_nodes) if price_nodes else ""
            
            current_price = None
            price_matches = re.findall(r'(\d[\d\s\u2009\xa0]*)₽', price_str)
            if price_matches:
                current_price = price_matches[0].replace("\u2009", "").replace("\xa0", "").replace(" ", "")
            
            # Image extraction
            image = None
            product_id = card.attrib.get('data-product-id')

            # 1. Try JSON lookup (most reliable for lazy-loaded items)
            if product_id and product_id in image_lookup:
                image = image_lookup[product_id]

            # 2. Try various srcset combinations from img and source tags
            if not image:
                srcset_selectors = [
                    'img::attr(srcset)', 
                    'source::attr(srcset)',
                    'img::attr(data-srcset)',
                    'source::attr(data-srcset)'
                ]
                
                for selector in srcset_selectors:
                    srcset = card.css(selector).get()
                    if srcset:
                        # Parse first URL from srcset, handling any whitespace (removes 2x, 3x etc)
                        parts = srcset.split(',')
                        if parts:
                            first_part = parts[0].strip()
                            if first_part:
                                cand_image = first_part.split()[0]
                                if cand_image and 'data:image' not in cand_image:
                                    image = cand_image
                                    break
            
            # 3. Try common lazy-loading attributes
            if not image or 'data:image' in image:
                lazy_attrs = ['data-src', 'data-original', 'data-lazy-src', 'data-image', 'data-main-image']
                for attr in lazy_attrs:
                    cand_image = card.css(f'img::attr({attr})').get() or card.css(f'div::attr({attr})').get()
                    if cand_image and 'data:image' not in cand_image:
                        image = cand_image
                        break
            
            # 4. Try meta tags inside the card
            if not image or 'data:image' in image:
                image = (card.css('meta[itemprop="image"]::attr(content)').get() or 
                         card.css('[itemprop="image"]::attr(src)').get())

            # 5. Fallback to standard src
            if not image or 'data:image' in image or 'placeholder' in image:
                image = card.css('img::attr(src)').get()
            
            if not image and title:
                 self.logger.debug(f"Missing image for {title}. Card HTML snippet: {card.get()[:500]}")
            
            if not title or not url:
                continue

            yield self.create_product(
                title=title.strip(),
                product_url=response.urljoin(url),
                price=current_price,
                image_url=response.urljoin(image) if image else None,
                merchant="Detmir",
                raw_data={
                    "source": "scrapy_v1",
                    "product_id": product_id
                }
            )

        # Pagination
        if self.strategy == "deep":
            # Extract current page from URL
            current_page = 1
            page_match = re.search(r'page=(\d+)', response.url)
            if page_match:
                current_page = int(page_match.group(1))
            
            # Find max page from pagination nav
            max_page = 1
            pagination_text = response.xpath('//nav[@aria-label="pagination"]//text()').getall()
            for text in pagination_text:
                if text.isdigit():
                    max_page = max(max_page, int(text))
            
            self.logger.info(f"Page {current_page} of {max_page}")
            
            if current_page < max_page:
                next_page = current_page + 1
                # Construct next page URL
                if '?' in response.url:
                    if 'page=' in response.url:
                         next_url = re.sub(r'page=\d+', f'page={next_page}', response.url)
                    else:
                         next_url = f"{response.url}&page={next_page}"
                else:
                    next_url = f"{response.url}?page={next_page}"
                
                yield response.follow(next_url, self.parse_catalog)
