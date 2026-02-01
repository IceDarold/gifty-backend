import json
import re

with open("/Users/taronseynyan/Projects/gifty-backend/scrapy_debug.html", "r") as f:
    content = f.read()

# Look for detmirUtilityData
match = re.search(r'window\.detmirUtilityData\s*=\s*(\{.*?\})\s*</script>', content)
if match:
    data_str = match.group(1)
    # The JSON is escaped in some ways (e.g. \" instead of ")
    
    # Try to find a product ID in the raw string
    id_to_find = "6232846"
    pos = data_str.find(id_to_find)
    if pos != -1:
        print(f"Found ID {id_to_find} at position {pos}")
        # Print a large chunk to see the structure
        print("Surrounding text:", data_str[pos-100:pos+1000])
else:
    print("Could not find detmirUtilityData")
