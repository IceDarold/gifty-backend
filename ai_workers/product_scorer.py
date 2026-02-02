"""
KAGGLE NOTEBOOK TEMPLATE: Product Scorer
GPU: T4 x2 (Preferred)
"""
import torch
from transformers import pipeline

# 1. КОНФИГУРАЦИЯ (Скопировать из common.py)
# GiftyInternalClient(...) 

# 2. ИНИЦИАЛИЗАЦИЯ LLM (Пример для Kaggle)
MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct" # Или любая другая доступная на Kaggle
pipe = pipeline(
    "text-generation", 
    model=MODEL_NAME, 
    device_map="auto", 
    model_kwargs={"torch_dtype": torch.bfloat16}
)

def analyze_gift(title, category, text):
    prompt = f"""Проанализируй товар и оцени его как подарок. 
    Название: {title}
    Категория: {category}
    Описание: {text}
    
    Верни JSON с полями:
    - score: от 0.0 до 10.0 (насколько это хороший подарок)
    - reasoning: краткое обоснование на русском языке
    """
    
    messages = [{"role": "user", "content": prompt}]
    result = pipe(messages, max_new_tokens=256)[0]['generated_text'][-1]['content']
    
    # Здесь должна быть логика парсинга JSON из ответа LLM
    # Для примера вернем заглушку
    return 8.5, "Уникальный и полезный подарок для любителей гаджетов"

def run_worker():
    client = GiftyInternalClient("https://api.giftyai.ru", "YOUR_TOKEN")
    
    while True:
        tasks = client.get_scoring_tasks(limit=10)
        if not tasks:
            print("No tasks, sleeping...")
            time.sleep(60)
            continue
            
        results = []
        for task in tasks:
            print(f"Analyzing: {task['title']}")
            score, reason = analyze_gift(task['title'], task['category'], task['content_text'])
            
            results.append({
                "gift_id": task['gift_id'],
                "llm_gift_score": score,
                "llm_gift_reasoning": reason,
                "llm_scoring_model": MODEL_NAME,
                "llm_scoring_version": "v1.0"
            })
            
        client.submit_scoring(results)
        print(f"Submitted {len(results)} items")

# run_worker()
