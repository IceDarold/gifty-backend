#!/bin/bash

# Test all spiders individually
# Run from the project root directory

echo "Testing all spiders..."
echo "====================="

# Create output directory
mkdir -p services/test_results

# Test each spider
echo ""
echo "1. Testing detmir..."
python3 scripts/test_spider.py detmir https://www.detmir.ru/catalog/index/name/lego/ --limit 5 --output services/test_results/detmir.json

echo ""
echo "2. Testing goldenapple..."
python3 scripts/test_spider.py goldenapple https://goldapple.ru/makijazh --limit 5 --output services/test_results/goldenapple.json

echo ""
echo "3. Testing group_price..."
python3 scripts/test_spider.py group_price https://groupprice.ru/gifts --limit 5 --output services/test_results/group_price.json

echo ""
echo "4. Testing inteltoys..."
python3 scripts/test_spider.py inteltoys https://inteltoys.ru/catalog --limit 5 --output services/test_results/inteltoys.json

echo ""
echo "5. Testing kassir..."
python3 scripts/test_spider.py kassir https://msk.kassir.ru/bilety-na-koncert --limit 5 --output services/test_results/kassir.json

echo ""
echo "6. Testing letu..."
python3 scripts/test_spider.py letu https://www.letu.ru/browse/makiyazh --limit 5 --output services/test_results/letu.json

echo ""
echo "7. Testing mrgeek..."
python3 scripts/test_spider.py mrgeek https://mrgeek.ru/catalog/elektronika/ --limit 5 --output services/test_results/mrgeek.json

echo ""
echo "8. Testing mvideo..."
python3 scripts/test_spider.py mvideo https://www.mvideo.ru/smartfony-i-svyaz-10 --limit 5 --output services/test_results/mvideo.json

echo ""
echo "9. Testing nashi_podarki..."
python3 scripts/test_spider.py nashi_podarki https://nashipodarki.ru/catalog/originalnye-podarki/ --limit 5 --output services/test_results/nashi_podarki.json

echo ""
echo "10. Testing vseigrushki..."
python3 scripts/test_spider.py vseigrushki https://vseigrushki.com/konstruktory/ --limit 5 --output services/test_results/vseigrushki.json

echo ""
echo "====================="
echo "All tests complete!"
echo "Results saved in services/test_results/"
