# Система парсинга каталогов Gifty

Эта система предназначена для извлечения данных о товарах с различных сайтов. Она построена на паттерне **"Стратегия"**, что позволяет использовать как универсальные методы (метаданные), так и специфичные для конкретных магазинов "VIP-парсеры".

---

## Архитектура

1.  **Схемы (`schemas.py`)**: Строгий формат данных (`ParsedProduct`, `ParsedCatalog`). Все парсеры обязаны возвращать данные в этих структурах.
2.  **Базовые классы (`base.py`, `catalog_base.py`)**: Интерфейсы, которые описывают, какие методы должны быть у парсера (`parse` для карточки товара и `parse_catalog` для списков).
3.  **Фабрика (`factory.py`)**: Диспетчер, который по домену URL определяет, какой класс использовать. Если домен неизвестен, используется `GenericParser`.
4.  **Generic Parser (`generic.py`)**: "Умный" парсер по умолчанию. Пытается найти данные через JSON-LD (Schema.org), OpenGraph и мета-теги.

---

## Как использовать

Самый простой способ — использовать `ParserFactory`. Она сама создаст нужный объект.

```python
from app.parsers.factory import ParserFactory

url = "https://mrgeek.ru/category/vse-tovary/"

# 1. Получаем парсер (фабрика вернет MrGeekParser или GenericParser)
parser = ParserFactory.get_parser(url)

# 2. Если это список товаров (каталог)
if hasattr(parser, 'parse_catalog'):
    catalog_data = await parser.parse_catalog(url)
    for product in catalog_data.products:
        print(product.title, product.price)

# 3. Если это одиночная карточка товара
product = await parser.parse("https://mrgeek.ru/product/some-kind-of-gift/")
print(product.title)
```

---

## Как добавить новый сайт (Создание VIP-парсера)

Если `GenericParser` плохо справляется с каким-то сайтом (например, не видит цену), нужно создать для него отдельный класс.

### Шаг 1: Создайте файл в `app/parsers/sites/`
Назовите его по имени сайта, например `ozon.py`.

### Шаг 2: Реализуйте класс
Наследуйтесь от `BaseCatalogParser` (если нужен парсинг списков) или `BaseParser`.

```python
from app.parsers.catalog_base import BaseCatalogParser
from app.parsers.schemas import ParsedProduct, ParsedCatalog
from bs4 import BeautifulSoup

class OzonParser(BaseCatalogParser):
    async def parse(self, url: str) -> ParsedProduct:
        # Логика извлечения данных с карточки товара
        pass

    async def parse_catalog(self, url: str) -> ParsedCatalog:
        # Логика извлечения списка товаров со страницы категории
        html = await self.fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
        # Используйте soup.select() для поиска элементов
        pass
```

### Шаг 3: Зарегистрируйте парсер в `factory.py`
Добавьте ваш класс в словарь `PARSER_REGISTRY`.

```python
from app.parsers.sites.ozon import OzonParser

PARSER_REGISTRY = {
    "mrgeek.ru": MrGeekParser,
    "ozon.ru": OzonParser,  # Добавили сюда
}
```

---

## Тестирование

Для проверки работы парсера используйте готовый скрипт:

```bash
# Тест универсального парсера
export PYTHONPATH=$PYTHONPATH:$(pwd)
python3 scripts/test_parser.py "https://any-site.com/product"

# Тест специфичного парсера (если домен зарегистрирован)
python3 scripts/test_parser.py "https://mrgeek.ru/category/vse-tovary/"
```

---

## Советы по написанию селекторов
*   **Цена**: Всегда очищайте цену от пробелов и валютных значков перед превращением в `float`. В `MrGeekParser` для этого есть вспомогательный метод `_clean_price`.
*   **Картинки**: Проверяйте, является ли URL картинки полным. Если нет (например, `/img/1.jpg`), используйте `urljoin(url, img_path)`.
*   **Raw Data**: Всегда сохраняйте исходный словарь (или его часть) в поле `raw_data` — это поможет при отладке, если парсер начнет отдавать странные данные.
