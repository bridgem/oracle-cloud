# get_balance.py
#   martin.bridge@oracle.com
#
#   Simple listing of account balance using the Oracle Cloud Account Metering API
#   See: https://docs.oracle.com/en/cloud/get-started/subscriptions-cloud/meter
#
#   Cloud credentials are read from a config file in which multiple tenancies can be stored
#   Note:   This script assumes there is only one purchase to create the tenancy (multiple purchase entries
#           may do strange things!)
#
# Output format
# Time                             Tenant               Currency  Purchased    Balance      Running     Consumed
# 17/12/2018 17:16:17              mytenant1            GBP         1800.00    1132.44      1132.44       667.56
# 17/12/2018 17:16:17              tenant2              GBP        12000.00   11709.24     11709.24       290.76
#
# 17-dec-2018   1.0     mbridge     Created
#

import requests
import os
import sys
import datetime
import configparser

debug: bool = False
configfile = '~/.oci/config.ini'


# Use the Oracle REST API to get the account balance for the given tenancy
def get_account_balance(report_time, tenant, username, password, domain, idcs_guid):

	resp = requests.get(
		'https://itra.oraclecloud.com/metering/api/v1/cloudbucks/' + domain,
		auth=(username, password),
		headers={'X-ID-TENANT-NAME': idcs_guid}
	)

	if resp.status_code != 200:
		# This means something went wrong.
		print('Error in GET: {}'.format(resp.status_code), file=sys.stderr)
		raise Exception

	for item in resp.json()['items']:

		# Calculate amt consumed so far
		consumed = item['purchase'][0]['purchasedResources'][0]['value'] - \
			item['balance'][0]['purchasedResources'][0]['value']

		print("{:24s}{:30s}{:10s}{:>11.2f}{:>11.2f}{:12.2f}".format(
			report_time.strftime('%d/%m/%Y %H:%M:%S'),
			tenant,
			item['purchase'][0]['purchasedResources'][0]['unit'],
			item['purchase'][0]['purchasedResources'][0]['value'],
			item['balance'][0]['purchasedResources'][0]['value'],
			consumed
		)
		)


if __name__ == "__main__":

	# In case we use the tilde (~) home directory character
	configfile = os.path.expanduser(configfile)

	if not os.path.isfile(configfile):
		print('Error: Config file not found ({})'.format(configfile), file=sys.stderr)
		sys.exit(0)

	config = configparser.ConfigParser()
	config.read(configfile)

	# Print Header
	print("{:24s}{:30s}{:10s}{:>11s}{:>11s}{:>12s}".format(
		'Time', 'Tenant', 'Currency', 'Purchased', 'Balance', 'Consumed'))

	# Timestamp
	report_time = datetime.datetime.now()

	# For each tenant in the config file
	for tenant in config.sections():

		ini_data = config[tenant]

		username = ini_data['username']
		password = ini_data['password']
		domain = ini_data['domain']
		idcs_guid = ini_data['idcs_guid']

		if debug:
			print('User:Pass = {}:{}   Domain, IDCSID = {}:{}'.format(username, password, domain, idcs_guid))

		get_account_balance(report_time, tenant, username, password, domain, idcs_guid)
