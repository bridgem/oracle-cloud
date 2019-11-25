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
# 31-oct-2019	1.2		mbridge		Simplified output using f-strings (requires python 3.6)

import requests
import sys
from datetime import datetime, timedelta
import configparser
import os
import json

# ======================================================================================================================
debug: bool = False
detail: bool = True        # Report detailed breakdown of costs per service
configfile = '~/.oci/config.ini'
# ======================================================================================================================


def get_account_charges(tenancy_name, username, password, domain, idcs_guid, start_time, end_time):

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
		total_cost = 0
		if detail:
			# Print Headings
			print(
				f"{'Tenancy':24} "
				# f"{'Data Centre':15} "
				f"{'ServiceName':24} "
				f"{'ResourceName':58} "
				f"{'SKU':6} "
				f"{'Qty':>7} "
				f"{'UnitPrc':>10} "
				f"{'Total':>7} "
				f"{'Cur':3} "
				f"{'OvrFlg':6} "
				f"{'Compute Type':10}")

		for item in resp.json()['items']:
			# Each service could have multiple costs (e.g. in overage)
			# Because of an anomoly in billing, overage amounts use the wrong unitPrice
			# so take the unit price from the non-overage entry

			costs = item['costs']
			unit_price = 0
			std_unit_price = 0
			for cost in costs:
				# TESTING
				# Find the pricing record for the non-overage amount
				# This only works if there are records for overage and non-overage in the same data range!!
				#
				# This code is pretty ugly, but it's a quick (temporary!) test
				#
				if cost['overagesFlag'] == "N":
					std_unit_price = cost['unitPrice']

			for cost in costs:

				if std_unit_price == 0:
					# Std price not found
					unit_price = cost['unitPrice']
				else:
					unit_price = std_unit_price

				unit_cost = unit_price * cost['computedQuantity']
				total_cost += unit_price * cost['computedQuantity']

				if detail:
					print(
						f"{tenancy_name:24} "
						# f"{item['dataCenterId']:15.15} "
						f"{item['serviceName']:24} "
						f"{item['resourceName']:58.58} "
						f"{item['gsiProductId']:6} "
						f"{cost['computedQuantity']:7.0f} "
						f"{cost['unitPrice']:10.5f} "
						f"{cost['computedAmount']:7.2f} "
						f"{item['currency']:3} "
						f"{cost['overagesFlag']:>6} "
						f"{cost['computeType']:11}"
						f"{cost['computedQuantity']:10.3f} @ {unit_price:8.5f} = {unit_cost:8.2f}"
					)

				# if cost['computeType'] == 'Usage':
				# total_cost += cost['computedAmount']

		return total_cost


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
	usage = get_account_charges(
		tenancy_name,
		ini_data['username'], ini_data['password'],
		ini_data['domain'], ini_data['idcs_guid'],
		datetime.strptime(start_date, '%d-%m-%Y'),
		datetime.strptime(end_date, '%d-%m-%Y') + timedelta(days=1, seconds=-0.001))

	# Simple output as I use it to feed a report
	print(f'{tenancy_name:24} {usage:6.2f}')


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
