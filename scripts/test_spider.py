#!/usr/bin/env python3
import sys
import os
import argparse
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

def main():
    parser = argparse.ArgumentParser(description="Gifty Spider Tester")
    parser.add_argument("spider", help="Name of the spider to test")
    parser.add_argument("url", help="Start URL for the spider")
    parser.add_argument("--strategy", default="deep", choices=["deep", "discovery"], help="Crawl strategy")
    parser.add_argument("--limit", type=int, default=10, help="Limit number of items (approx)")
    parser.add_argument("--output", default="test_results.json", help="Output JSON file")
    
    args = parser.parse_args()

    # Добавляем путь к сервисам, чтобы Scrapy нашел проект
    sys.path.append(os.path.join(os.getcwd(), "services"))
    os.environ['SCRAPY_SETTINGS_MODULE'] = 'gifty_scraper.settings'

    settings = get_project_settings()
    
    # Отключаем IngestionPipeline для тестов, чтобы не слать данные в API
    settings.set('ITEM_PIPELINES', {
        'scrapy.pipelines.images.ImagesPipeline': None,
    })
    
    # Добавляем сохранение в файл
    settings.set('FEEDS', {
        args.output: {
            'format': 'json',
            'encoding': 'utf8',
            'store_empty': False,
            'fields': None,
            'indent': 4,
            'item_export_kwargs': {
                'export_empty_fields': True,
            },
        },
    })
    
    # Ограничиваем количество страниц/элементов для теста
    settings.set('CLOSESPIDER_ITEMCOUNT', args.limit)

    process = CrawlerProcess(settings)
    process.crawl(args.spider, url=args.url, strategy=args.strategy)
    process.start()
    
    print(f"\n--- Done! results saved to {args.output} ---")

if __name__ == "__main__":
    main()
