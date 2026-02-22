import os
import re

spiders_dir = "services/gifty_scraper/spiders"
files = [f for f in os.listdir(spiders_dir) if f.endswith(".py") and f != "__init__.py"]

print(f"{'Filename':<20} | {'Spider Name':<20}")
print("-" * 45)

for f in files:
    path = os.path.join(spiders_dir, f)
    with open(path, "r") as file:
        content = file.read()
        match = re.search(r'name\s*=\s*["\'](.*?)["\']', content)
        if match:
            spider_name = match.group(1)
            filename_key = f.replace(".py", "")
            print(f"{filename_key:<20} | {spider_name:<20}")
            if filename_key != spider_name:
                print(f"⚠️  MISMATCH FOUND: {filename_key} != {spider_name}")
