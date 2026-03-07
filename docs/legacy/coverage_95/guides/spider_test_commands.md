# Spider testing commands (legacy)

This page was imported from the historical branch `chore/coverage-95`. It may be outdated relative to the current spider implementations.

---

# Spider Testing Commands & Status

## Quick Test All Spiders

Run the automated test script:
```bash
./test_all_spiders.sh
```

Or use the Python test runner:
```bash
python3 scripts/run_all_spiders_test.py
```

## Individual Spider Test Commands

### 1. Detmir ✅ WORKING
```bash
python3 scripts/test_spider.py detmir https://www.detmir.ru/catalog/index/name/lego/ --limit 5 --output services/test_results/detmir.json
```
**Status:** Fixed - Updated URL structure from `/catalog/lego/` to `/catalog/index/name/lego/`
**Performance:** 36 items in 1.34s (2,160 items/min)

### 2. GoldenApple ❌ NEEDS FIX
```bash
python3 scripts/test_spider.py goldenapple https://goldapple.ru/makijazh --limit 5 --output services/test_results/goldenapple.json
```
**Status:** Failing - Needs selector updates

### 3. GroupPrice ❌ NEEDS FIX
```bash
python3 scripts/test_spider.py group_price https://groupprice.ru/gifts --limit 5 --output services/test_results/group_price.json
```
**Status:** Failing - Needs selector updates

### 4. IntelToys ✅ WORKING
```bash
python3 scripts/test_spider.py inteltoys https://inteltoys.ru/catalog --limit 5 --output services/test_results/inteltoys.json
```
**Status:** Working perfectly
**Performance:** 20 items in 2.45s

### 5. Kassir ❌ NEEDS FIX
```bash
python3 scripts/test_spider.py kassir https://msk.kassir.ru/bilety-na-koncert --limit 5 --output services/test_results/kassir.json
```
**Status:** Failing - Takes 28s and returns 0 items

### 6. Letu ❌ NEEDS FIX
```bash
python3 scripts/test_spider.py letu https://www.letu.ru/browse/makiyazh --limit 5 --output services/test_results/letu.json
```
**Status:** Failing - Needs selector updates

### 7. MrGeek ✅ WORKING
```bash
python3 scripts/test_spider.py mrgeek https://mrgeek.ru/catalog/elektronika/ --limit 5 --output services/test_results/mrgeek.json
```
**Status:** Fixed - Extracts titles, URLs, images (prices need improvement)
**Performance:** 21 items in 37.58s (follows product pages for details)

### 8. MVideo ❌ NEEDS FIX
```bash
python3 scripts/test_spider.py mvideo https://www.mvideo.ru/kompyutery-i-noutbuki-1 --limit 5 --output services/test_results/mvideo.json
```
**Status:** Failing - Needs selector updates

### 9. NashiPodarki ✅ WORKING
```bash
python3 scripts/test_spider.py nashi_podarki https://nashipodarki.ru/catalog/matreshki/ --limit 5 --output services/test_results/nashi_podarki.json
```
**Status:** Fixed - Updated category URL and fixed price extraction
**Performance:** 30 items in 2.26s

### 10. VseIgrushki ✅ WORKING
```bash
python3 scripts/test_spider.py vseigrushki https://vseigrushki.com/konstruktory/ --limit 5 --output services/test_results/vseigrushki.json
```
**Status:** Fixed - Updated URL structure
**Performance:** 30 items in 2.61s (1,350 items/min)

