# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class ProductItem(scrapy.Item):
    name = scrapy.Field()  # Added for consistency
    title = scrapy.Field()
    description = scrapy.Field()
    price = scrapy.Field()
    currency = scrapy.Field()
    image_url = scrapy.Field()
    product_url = scrapy.Field()
    merchant = scrapy.Field()
    category = scrapy.Field()
    raw_data = scrapy.Field()
    site_key = scrapy.Field()
    source_id = scrapy.Field()

class CategoryItem(scrapy.Item):
    name = scrapy.Field()
    title = scrapy.Field() # Added for consistency
    price = scrapy.Field() # Added for consistency (always None)
    url = scrapy.Field()
    parent_url = scrapy.Field()
    site_key = scrapy.Field()
