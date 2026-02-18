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
python3 scripts/test_spider.py mvideo https://www.mvideo.ru/smartfony-i-svyaz-10 --limit 5 --output services/test_results/mvideo.json
```
**Status:** Failing - Takes 17s and returns 0 items

### 9. NashiPodarki ❌ SERVER ERROR
```bash
python3 scripts/test_spider.py nashi_podarki https://nashipodarki.ru/catalog/originalnye-podarki/ --limit 5 --output services/test_results/nashi_podarki.json
```
**Status:** Server returning 500 errors - May be temporary or requires different approach

### 10. VseIgrushki ✅ WORKING PERFECTLY
```bash
python3 scripts/test_spider.py vseigrushki https://vseigrushki.com/konstruktory/ --limit 5 --output services/test_results/vseigrushki.json
```
**Status:** Fixed - Perfect extraction of all fields
**Performance:** 30 items in 2.61s (1,350 items/min)
**Pagination:** Working (90 items from 3 pages)

## Summary

### Working Spiders (4/10)
- ✅ Detmir - 36 items
- ✅ IntelToys - 20 items  
- ✅ MrGeek - 21 items (needs price improvement)
- ✅ VseIgrushki - 30 items (perfect)

### Need Fixing (5/10)
- ❌ GoldenApple - Selector updates needed
- ❌ GroupPrice - Selector updates needed
- ❌ Kassir - Slow, returns 0 items
- ❌ Letu - Selector updates needed
- ❌ MVideo - Returns 0 items

### Server Issues (1/10)
- ⚠️ NashiPodarki - 500 Internal Server Error

## Next Steps

1. Fix selector issues for: GoldenApple, GroupPrice, Letu
2. Debug API/dynamic content for: Kassir, MVideo
3. Improve MrGeek price extraction
4. Monitor NashiPodarki server status
