#!/usr/bin/env python3
import subprocess
import os
import json
import sys
import time

# Dictionary of spiders and a valid category URL to test them with
SPIDERS_TO_TEST = {
    "detmir": "https://www.detmir.ru/catalog/index/name/lego/",  # Fixed: updated URL structure
    "goldenapple": "https://goldapple.ru/makijazh",
    "group_price": "https://groupprice.ru/categories/parfumeriya",  # Updated to valid category
    "inteltoys": "https://inteltoys.ru/catalog",
    "kassir": "https://msk.kassir.ru/bilety-na-koncert",
    "letu": "https://www.letu.ru/browse/makiyazh",
    "mrgeek": "https://mrgeek.ru/catalog/elektronika/",
    "mvideo": "https://www.mvideo.ru/smartfony-i-svyaz-10",
    "nashi_podarki": "https://nashipodarki.ru/catalog/matreshki/",  # Updated to valid category
    "vseigrushki": "https://vseigrushki.com/konstruktory/"  # Fixed: removed /catalog/
}

OUTPUT_DIR = "spider_test_results"

def run_tests():
    # Create output directory
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    results = []

    print(f"Starting test for {len(SPIDERS_TO_TEST)} spiders...")
    print(f"Results will be saved to ./{OUTPUT_DIR}/")
    print("-" * 60)

    for spider, url in SPIDERS_TO_TEST.items():
        print(f"🕷️  Testing spider: {spider}")
        print(f"    URL: {url}")
        
        output_file = os.path.join(OUTPUT_DIR, f"{spider}.json")
        
        # Construct command
        cmd = [
            "python3", "scripts/test_spider.py",
            spider,
            url,
            "--limit", "5",  # Keep it small for quick testing
            "--output", output_file
        ]
        
        start_time = time.time()
        try:
            # Run the test script
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # 1 minute timeout per spider
            )
            duration = time.time() - start_time
            
            # Check if file exists and has content
            item_count = 0
            success = False
            if result.returncode == 0 and os.path.exists(output_file):
                try:
                    with open(output_file, 'r') as f:
                        data = json.load(f)
                        item_count = len(data)
                        success = item_count > 0
                except json.JSONDecodeError:
                    print(f"    ⚠️  JSON Error in output file")
                except Exception as e:
                    print(f"    ⚠️  Error reading output: {e}")
            
            status = "✅ PASS" if success else "❌ FAIL"
            if result.returncode != 0:
                status = "💥 CRASH"
            
            print(f"    Status: {status} ({item_count} items) in {duration:.2f}s")
            
            if not success:
               print(f"    Error Output:\n{result.stderr[:200]}...")

            results.append({
                "spider": spider,
                "status": status,
                "items": item_count,
                "duration": duration,
                "file": output_file
            })
            
        except subprocess.TimeoutExpired:
            print(f"    ⏳ TIMEOUT")
            results.append({
                "spider": spider,
                "status": "TIMEOUT",
                "items": 0,
                "duration": 60,
                "file": output_file
            })
        except Exception as e:
            print(f"    🔥 ERROR: {e}")
            results.append({
                "spider": spider,
                "status": "ERROR",
                "items": 0,
                "duration": 0,
                "file": output_file
            })
            
        print("-" * 60)

    # Print Summary
    print("\n" + "="*60)
    print(f"{'SPIDER':<20} | {'STATUS':<10} | {'ITEMS':<8} | {'TIME':<8}")
    print("-" * 60)
    for r in results:
        print(f"{r['spider']:<20} | {r['status']:<10} | {r['items']:<8} | {r['duration']:.2f}s")

    print("="*60)
    print(f"Full results available in {OUTPUT_DIR}/")

if __name__ == "__main__":
    run_tests()
