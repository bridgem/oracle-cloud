# OCI Usage Cost
# Get Oracle cloud usage costs for given data range
#
# Parameters:
#	 	profile_name
# 		start_date
# 		end_date
#
# Other parameters picked up from config file using profile name
#   	username
#   	password
#   	idcs_id (idcs-4656dbcafeb47777d3efabcdef12...) from idcs url
#   	domain_id (cacct-8b4b0c9b4c40173264564750985ff6... select idcs_users in services from myservices page)
#
# Output
#		stdout, readable column format
#
# 08-jan-2018   1.0     mbridge     Created
# 25-jan-2018   1.1     mbridge     Handle overage charges in service costs
# 31-oct-2019   1.2	    mbridge	    Simplified output using f-strings (requires python 3.6)
# 10-feb-2020   1.3	    mbridge     Allow choice of CSV or tablular output
# 29-may-2020	1.4		mbridge		Make end-date non-inclusive (i.e. start_date <= d < end_date)
# 13-apr-2021	1.5		mbridge		Improved command line parameters using argparse
# 06-jul-2021	1.6		mbridge		Added list price lookup

import requests
import argparse
import sys
from datetime import datetime, timedelta
import configparser
import os
import json
import re
from string import Formatter
import csv

# ======================================================================================================================
output_format = "CSV"	   # CSV or normal output, set to "CSV" or anything else
configfile = '~/.oci/config.ini'
# ======================================================================================================================

# Dictionary keys and headings
field_names = [
	'Tenancy', 'ServiceName', 'ResourceName', 'SKU', 'Qty',
	'UnitPrc', 'Total', 'Cur', 'OvrFlg', 'ComputeType',
	'CalcUnitPrc', 'CalcLineCost', 'ListUnitPrc', 'ListLineCost']

print_format = "{Tenancy:24} {ServiceName:24} {ResourceName:58.58} {SKU:6} {Qty:>10.3f} " \
			   "{UnitPrc:>10.6f} {Total:>7.2f} {Cur:3} {OvrFlg:>6} {ComputeType:11.11} " \
			   "{CalcUnitPrc:>10.6f} {CalcLineCost:>8.2f} " \
			   "{ListUnitPrc:>10.6f} {ListLineCost:>7.2f}"

header_format = re.sub('{[A-Z,a-z]*', '{', print_format)    # Header format removes the named placeholders
header_format = re.sub('\.[0-9]*f', 's', header_format)     # Change number formats to string for heading output


# Output a line for each cloud resource (output_dict should be a dictionary)
def format_output(output_dict, format):
	global csv_writer

	if format == "CSV":
	# CSV to file
		csv_writer.writerow(output_dict)
	else:
		# Readable format to stdout
		print(print_format.format(**output_dict))


def csv_init():
	csv_writer = csv.DictWriter(
		sys.stdout,
		lineterminator='\n',
		fieldnames=field_names, delimiter=',',
		dialect='excel',
		quotechar='"', quoting=csv.QUOTE_MINIMAL)

	if detail:
		csv_writer.writeheader()

	return csv_writer


# Get simplified price list (SKU + prices)
def get_price_list(currency_code):
	url = "https://itra.oraclecloud.com/itas/.anon/myservices/api/v1/products?limit=500"
	http_header = {'X-Oracle-Accept-CurrencyCode': currency_code}
	resp = requests.get(url, headers=http_header)
	items = resp.json()['items']

	price_list = {}

	for item in items:
		partNum = item['partNumber']
		payg_price = 0
		month_price = 0

		# Only look at first 2 pricing elements
		# Some items, such as B88327 (Outbound Data Transfer) have a free amount before charging kicks in
		# So for easy approximation, we will ignore charged amount
		# TODO: Fix this horrible hack!
		for price in item['prices'][:2]:

			if price['model'] == 'PAY_AS_YOU_GO':
				payg_price = float(price['value'])
			elif price['model'] == 'MONTHLY_COMMIT':
				month_price = float(price['value'])
			else:
				print(f"Unknown price type: {price['model']}")

		price_list[partNum] = {"payg_price": payg_price, "month_price": month_price}

	return price_list


def get_account_charges(tenancy_name, username, password, domain, idcs_guid, start_time, end_time):
	global csv_writer

	price_list = get_price_list("GBP")

	if debug:
		print(f'User:Pass      = {username}/{"*" * len(password)}')
		print(f'Domain, IDCSID = {domain} {idcs_guid}')
		print(f'Start/End Time = {start_time} to {end_time}')

	# Oracle API needs the milliseconds explicitly
	# UsageType can be TOTAL, HOURLY or DAILY.
	url_params = {
		'startTime': start_time.isoformat() + '.000',
		'endTime': end_time.isoformat() + '.000',
		'usageType': 'TOTAL',
		'dcAggEnabled': 'N',
		'computeTypeEnabled': 'Y'
	}

	resp = requests.get(
		'https://itra.oraclecloud.com/metering/api/v1/usagecost/' + domain,
		auth=(username, password),
		headers={'X-ID-TENANT-NAME': idcs_guid, 'accept-encoding': '*'},
		params=url_params,
		timeout=600
	)

	if resp.status_code != 200:
		# This means something went wrong.
		msg = json.loads(resp.text)['errorMessage']
		print(f'Error in GET: {resp.status_code} ({resp.reason}) on tenancy {tenancy_name}', file=sys.stderr)
		print(f'  {msg}', file=sys.stderr)
		return -1
	else:
		# Add the cost of all items returned
		bill_total_cost = 0		# Ignores 'Do Not Bill' costs
		calc_total_cost = 0		# Uses all quantities, but uses 'Usage' costs where available
		list_total_cost = 0     # Total cost at list price
		if detail:
			# Print Headings
			if output_format == "CSV":
				csv_writer = csv_init()
			else:
				vformat = Formatter().vformat
				print(vformat(header_format, field_names, ''))

		items = resp.json()

		for item in items['items']:
			# Each service could have multiple costs (e.g. in overage)
			# Because of an anomoly in billing, overage amounts use the wrong unitPrice
			# so take the unit price from the non-overage entry

			costs = item['costs']
			calc_unit_price = 0
			std_unit_price = 0

			# TESTING
			# Find the pricing record for the non-overage amount
			# This only works if there are records for overage and non-overage in the same report range!!
			# This code is pretty ugly, but it's a quick (temporary!) test
			for cost in costs:
				if cost['overagesFlag'] == "N":
					std_unit_price = cost['unitPrice']

			for cost in costs:

				if std_unit_price == 0:
					# Std price not found for non-overage, so just use the (probabl) overages one
					calc_unit_price = cost['unitPrice']
				else:
					calc_unit_price = std_unit_price

				calc_line_item_cost = calc_unit_price * cost['computedQuantity']
				calc_total_cost += calc_line_item_cost

				if cost['computeType'] == 'Usage':
					bill_total_cost += cost['computedAmount']

				# Get list price of current item
				partNum = item['gsiProductId']
				try:
					list_unit_price = price_list[partNum]['month_price']
				except KeyError:
					list_unit_price = 0.0

				list_line_cost = cost['computedQuantity'] * list_unit_price
				list_total_cost += list_line_cost

				if detail:
					output_dict = {
						'Tenancy': tenancy_name,
						'ServiceName': item['serviceName'],
						'ResourceName': item['resourceName'],
						'SKU': partNum,
						'Qty': cost['computedQuantity'],
						'UnitPrc': cost['unitPrice'],
						'Total': cost['computedAmount'],
						'Cur': item['currency'],
						'OvrFlg': cost['overagesFlag'],
						'ComputeType': cost['computeType'],
						'CalcUnitPrc': calc_unit_price,
						'CalcLineCost': calc_line_item_cost,
						'ListUnitPrc': list_unit_price,
						'ListLineCost': list_line_cost
					}

					format_output(output_dict, output_format)

		return bill_total_cost, calc_total_cost, list_total_cost


def tenancy_usage(tenancy_name, start_date, end_date, grand_total):

	# Just in case we use the tilde (~) home directory character
	configfilepath = os.path.expanduser(configfile)

	if not os.path.isfile(configfilepath):
		print(f'Error: Config file not found ({configfilepath})', file=sys.stderr)
		sys.exit(0)

	config = configparser.ConfigParser()
	config.read(configfilepath)

	ini_data = config[tenancy_name]

	# Show usage details
	# Set time component of end date to 23:59:59.999 to match the behaviour of the Oracle my-services dashboard
	bill_total_cost, calc_total_cost, list_total_cost = get_account_charges(
		tenancy_name,
		ini_data['username'], ini_data['password'],
		ini_data['domain'], ini_data['idcs_guid'],
		datetime.strptime(start_date, '%d-%m-%Y'),
		datetime.strptime(end_date, '%d-%m-%Y')  # + timedelta(days=1, seconds=-0.001)
	)

	if grand_total:
		# Simple output as I use it to feed a report
		print(f'{tenancy_name:24} {bill_total_cost:10.2f} (Billed) {calc_total_cost:10.2f} (Corrected) {list_total_cost:10.2f} (List)')


if __name__ == "__main__":
	# Get profile from command line
	parser = argparse.ArgumentParser(description='OCI usage costs from a tenancy')

	# Positional
	parser.add_argument('tenancy', help="Name of OCI tenancy (config profile name)")
	parser.add_argument('start_date', help="Start date (dd-mm-yyyy')")
	parser.add_argument('end_date', help="End date, inclusive (dd-mm-yyyy')")
	parser.add_argument('--no-total', dest='total', action='store_false', default=True, help="Print summary costs")
	parser.add_argument('--debug', action='store_true', help="Print debug info")
	parser.add_argument('--detail', action='store_true', help="Show detailed breakdown of costs per service ")

	args = parser.parse_args()

	tenancy_name = args.tenancy
	start_date = args.start_date
	end_date = args.end_date
	grand_total = args.total
	debug = args.debug
	detail = args.detail

	tenancy_usage(tenancy_name, start_date, end_date, grand_total)
