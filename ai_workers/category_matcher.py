"""
KAGGLE NOTEBOOK TEMPLATE: Category Matcher
"""

# Список внутренних категорий Gifty (можно запрашивать из API или держать в коде)
INTERNAL_CATEGORIES = [
    {"id": 1, "name": "Электроника"},
    {"id": 2, "name": "Дом и сад"},
    {"id": 3, "name": "Игрушки"},
    # ...
]

def match_category(external_name):
    # Логика сопоставления через LLM или Sentence Embeddings
    # Например: "Прикольные чашки" -> "Кухня / Посуда" (ID: 45)
    return 1 # Placeholder

def run_category_worker():
    client = GiftyInternalClient("https://api.giftyai.ru", "YOUR_TOKEN")
    
    while True:
        tasks = client.get_category_tasks(limit=50)
        if not tasks:
            print("No new categories to match.")
            time.sleep(300)
            continue
            
        results = []
        for task in tasks:
            internal_id = match_category(task['external_name'])
            results.append({
                "external_name": task['external_name'],
                "internal_category_id": internal_id
            })
            
        client.submit_categories(results)
        print(f"Matched {len(results)} categories")

# run_category_worker()
