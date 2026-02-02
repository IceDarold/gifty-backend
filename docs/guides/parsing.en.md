# Creating New Parsers 🕷️

In Gifty, data collection is automated using **Scrapy**. For rapid development, we use a base class that handles boilerplate tasks related to task queues and API integration.

---

## 🚀 Quick Start

### 1. Environment Setup
Make sure you have the development dependencies installed:
```bash
pip install -r requirements.txt
```

### 2. Create Spider File
Create a new file in the `services/gifty_scraper/spiders/` directory.
Name it after the target website, e.g., `ozon.py` or `my_shop.py`.

### 3. Write Core Logic
Inherit from `GiftyBaseSpider` to minimize template code.

```python
from gifty_scraper.base_spider import GiftyBaseSpider

class MyShopSpider(GiftyBaseSpider):
    name = "my_shop"        # Unique name for console execution
    allowed_domains = ["myshop.ru"]
    site_key = "myshop"    # Key used by the scheduler to find this spider

    def parse_catalog(self, response):
        # Locate product card containers
        items = response.css('.product-card')
        
        for item in items:
            yield self.create_product(
                title=item.css('.title::text').get().strip(),
                product_url=response.urljoin(item.css('a::attr(href)').get()),
                price=item.css('.price-value::text').re_first(r'(\d+)'),
                image_url=item.css('img::attr(src)').get(),
                merchant="My Shop",
                raw_data={"source": "scrapy_v1"}
            )

        # Handle pagination (if strategy="deep")
        if self.strategy == "deep":
            next_page = response.css('a.next-btn::attr(href)').get()
            if next_page:
                yield response.follow(next_page, self.parse_catalog)
```

---

## 🛠️ Testing and Debugging

Use the provided script to verify logic without running the full infrastructure (Docker/API):

```bash
python3 scripts/test_spider.py my_shop "https://myshop.ru/catalog" --limit 10
```

*   **`--limit`**: Limits collection (e.g., first 10 items).
*   **`--output`**: Result filename (defaults to `test_results.json`).

Check the generated JSON file — if it contains data, your selectors are working correctly.

---

## ⛓️ System Registration

To enable the system to use the new spider automatically:

### 1. Update the Worker
Open `services/run_worker.py` and add your class to the `SPIDERS` dictionary:

```python
from gifty_scraper.spiders.my_shop import MyShopSpider

SPIDERS = {
    "mrgeek": MrGeekSpider,
    "myshop": MyShopSpider,  # <-- Add here
}
```

### 2. Add Source to Database
To start receiving tasks from the scheduler, create an entry in the `parsing_sources` table:

```sql
INSERT INTO parsing_sources (url, type, site_key, priority, refresh_interval_hours, is_active)
VALUES ('https://myshop.ru/catalog', 'list', 'myshop', 50, 24, true);
```

---

## 💡 Best Practices

1.  **Throttling**: Default delay is 1s. If blocked, increase `DOWNLOAD_DELAY` in `settings.py`.
2.  **CSS vs XPath**: Use CSS selectors wherever possible for better readability.
3.  **Images**: Always ensure `image_url` is an absolute URL (use `response.urljoin`).
4.  **Batching**: Our Pipeline automatically batches items (default 50) before sending them to the API to save resources.
