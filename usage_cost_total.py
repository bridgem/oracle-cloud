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
#   	domain_id (cacct-8b4b0c9b4c40173264564750985ff6... select users in services from myservices page)
#
# Output
#		stdout, readable column format
#
# 08-jan-2018   1.0     mbridge     Created
# 25-jan-2018   1.1     mbridge     Handle overage charges in service costs
# 31-oct-2019   1.2	    mbridge	    Simplified output using f-strings (requires python 3.6)
# 10-feb-2020   1.3	    mbridge     Allow choice of CSV or tablular output

import requests
import sys
from datetime import datetime, timedelta
import configparser
import os
import json
import re
from string import Formatter
import csv

# ======================================================================================================================
debug: bool = False
detail: bool = True        # Report detailed breakdown of costs per service
output_format = "CSV"	   # CSV or normal output, set to "CSV" or anything else
configfile = '~/.oci/config.ini'
# ======================================================================================================================

# Dictionary keys and headings
field_names = [
	'Tenancy', 'ServiceName', 'ResourceName', 'SKU', 'Qty',
	'UnitPrc', 'Total', 'Cur', 'OvrFlg', 'ComputeType',
	'BillTotalCost', 'CalcUPrc', 'LineCost', 'CalcTotalCost']

print_format = "{Tenancy:24} {ServiceName:24} {ResourceName:58.58} {SKU:6} {Qty:>10.3f} " \
			   "{UnitPrc:>10.6f} {Total:>7.2f} {Cur:3} {OvrFlg:>6} {ComputeType:11.11} " \
			   "{BillTotalCost:9.2f} {CalcUPrc:>10.6f} {LineCost:>8.2f} {CalcTotalCost:>9.2f}"
# Header format removes the named placeholders
header_format = re.sub('{[A-Z,a-z]*', '{', print_format)
# Change number formats to string for heading output
header_format = re.sub('\.[0-9]*f', 's', header_format)


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
		fieldnames=field_names, delimiter=',',
		dialect='excel',
		quotechar='"', quoting=csv.QUOTE_MINIMAL)

	if detail:
		csv_writer.writeheader()

	return csv_writer

def get_account_charges(tenancy_name, username, password, domain, idcs_guid, start_time, end_time):
	global csv_writer

	if debug:
		print(f'User:Pass      = {username}/{"*" * len(password)}')
		print(f'Domain, IDCSID = {domain} {idcs_guid}')
		print(f'Start/End Time = {start_time} to {end_time}')

	# Oracle API needs the milliseconds explicitly
	# UsageType can be TOTAL, HOURLY or DAILY.
	url_params = {
		'startTime': start_time.isoformat() + '.000',
		'endTime': end_time.isoformat() + '.000',
		'usageType': 'MONTHLY',
		'dcAggEnabled': 'N',
		'computeTypeEnabled': 'Y'
	}

	resp = requests.get(
		'https://itra.oraclecloud.com/metering/api/v1/usagecost/' + domain,
		auth=(username, password),
		headers={'X-ID-TENANT-NAME': idcs_guid},
		params=url_params
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
		if detail:
			# Print Headings
			# Headings
			if output_format == "CSV":
				csv_writer = csv_init()
			else:
				vformat = Formatter().vformat
				print(vformat(header_format, field_names, ''))

		items = resp.json()

		for item in resp.json()['items']:
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

				if detail:
					output_dict = {
						'Tenancy': tenancy_name,
						'ServiceName': item['serviceName'],
						'ResourceName': item['resourceName'],
						'SKU': item['gsiProductId'],
						'Qty': cost['computedQuantity'],
						'UnitPrc': cost['unitPrice'],
						'Total': cost['computedAmount'],
						'Cur': item['currency'],
						'OvrFlg': cost['overagesFlag'],
						'ComputeType': cost['computeType'],
						'BillTotalCost': bill_total_cost,
						'CalcUPrc': calc_unit_price,
						'LineCost': calc_line_item_cost,
						'CalcTotalCost': calc_total_cost}

					format_output(output_dict, output_format)

		return bill_total_cost, calc_total_cost


def tenancy_usage(tenancy_name, start_date, end_date):

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
	bill_total_cost, calc_total_cost = get_account_charges(
		tenancy_name,
		ini_data['username'], ini_data['password'],
		ini_data['domain'], ini_data['idcs_guid'],
		datetime.strptime(start_date, '%d-%m-%Y'),
		datetime.strptime(end_date, '%d-%m-%Y') + timedelta(days=1, seconds=-0.001))

	# Simple output as I use it to feed a report
	print(f'{tenancy_name:24} {bill_total_cost:10.2f} {calc_total_cost:10.2f}')


if __name__ == "__main__":
	# Get profile from command line
	if len(sys.argv) != 4:
		print(f'Usage: {sys.argv[0]} <profile_name> <start_date> <end_date>')
		print('       Where date format = dd-mm-yyyy')
		sys.exit()
	else:
		tenancy_name = sys.argv[1]
		start_date = sys.argv[2]
		end_date = sys.argv[3]

	tenancy_usage(tenancy_name, start_date, end_date)

	if debug:
		print('DONE')
