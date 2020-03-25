# oci-prices.py
#
# List all OCI Universal Credit service prices
#
# API only returns current SKUs - if a product SKU has been retired it will not be returned by the API,
# so if using this API in conjunction with older metering/billing data, you may find some that do not match.
#
# See: https://oc-blog.com/2020/01/22/undocumented-oci-pricelist-api/
#
# 20-jan-2020	Martin Bridge	Created

import requests

# Example requests
# https://itra.oraclecloud.com/itas/.anon/myservices/api/v1/products/10089
# https://itra.oraclecloud.com/itas/.anon/myservices/api/v1/products?parentProductPartNumber=B88206&limit=500
# https://itra.oraclecloud.com/itas/.anon/myservices/api/v1/products?partNumber=B88514

url = "https://itra.oraclecloud.com/itas/.anon/myservices/api/v1/products?limit=500"
http_header = {'X-Oracle-Accept-CurrencyCode': 'GBP'}
resp = requests.get(url, headers=http_header)

# Columns headings
print("PartNum|Category|Name|Metric|PAYG_price|Month_price}")

nitems = 0
for item in resp.json()['items']:
	nitems += 1
	# print(f"{item['displayName']:160} - {item['prices']}")

	# Some items do not have serviceCategoryDisplayName
	partNum = item['partNumber']
	name = item['shortDisplayName']
	try:
		category = item['serviceCategoryDisplayName']
	except KeyError:
		category = "None"
	try:
		metric = item['metricDisplayName']
	except KeyError:
		metric = "None"

	payg_price = 1000000
	month_price = 1000000
	# Some items have a banded price, free up to a limit, then a charge beyond
	# Fro simplicity, use the lowest price
	for price in item['prices']:
		if price['model'] == 'PAY_AS_YOU_GO':
			if float(price['value']) < payg_price:
				payg_price = float(price['value'])
		elif price['model'] == 'MONTHLY_COMMIT':
			if float(price['value']) < month_price:
				month_price = float(price['value'])

	print(f"{partNum}|{category}|{name}|{metric}|{payg_price}|{month_price}")

print(f"{nitems} SKUs found")
