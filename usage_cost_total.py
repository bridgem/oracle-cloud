# OCI Usage Cost
# Get Oracle cloud usage costs for given data range
# Parameters (picked up from config file)
#   start_date (format 2018-03-03T23:00:00.000)
#   end_date
#   username
#   password
#   idcs_id (idcs-4656dbcafeb47777d3efabcdef12345)
#   domain_id (cacct-8b4b0c9b4c40173264564750985ff6b34
#
# 08-jan-2018   1.0     mbridge     Created
# 25-jan-2018   1.1     mbridge     Handle overage charges in service costs

#
import requests
import sys
from datetime import datetime, timedelta
import configparser
import os


# ======================================================================================================================
debug: bool = True
configfile = '~/.oci/config.ini'
# ======================================================================================================================


def get_account_charges(username, password, domain, idcs_guid, start_time, end_time):

	if debug:
		print('User:Pass      = {}/{}'.format(username, "*" * len(password)))
		print('Domain, IDCSID = {} {}'.format(domain, idcs_guid))
		print('Start/End Time = {} to {}'.format(start_time, end_time))

	# Oracle API needs the milliseconds explicitly
	url_params = {
		'startTime': start_time.isoformat() + '.000',
		'endTime': end_time.isoformat() + '.000',
		'usageType': 'TOTAL',
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
		print('Error in GET: {}'.format(resp.status_code), file=sys.stderr)
		raise Exception

	# Add the cost of all items returned
	total_cost = 0
	if debug:
		print('{:24s} {:56s} {:>5s} {:>10s} {:>7s} {:3s} {:6s} {:10s}'.format(
			'ServiceName',
			'ResourceName',
			'Qty',
			'UnitPrc',
			'Total',
			'Cur',
			'OvrFlg',
			'Compute Type'))

	for item in resp.json()['items']:

		# Each service could have multiple costs (e.g. in overage)
		for cost in item['costs']:

			if debug:
				print('{:24s} {:56s} {:5.0f} {:10.5f} {:7.2f} {:3s} {:>6s} {:10s}'.format(
					item['serviceName'],
					item['resourceName'],
					cost['computedQuantity'], cost['unitPrice'],
					cost['computedAmount'], item['currency'],
					cost['overagesFlag'],
					cost['computeType']))

			if cost['computeType'] == 'Usage':
				total_cost += cost['computedAmount']

	return total_cost


if __name__ == "__main__":
	# Get profile from command line
	if len(sys.argv) != 4:
		print('Usage: ' + sys.argv[0] + ' <profile_name> <start_date> <end_date>')
		print('       Where date format = dd-mm-yyyy')
		sys.exit()
	else:
		profile_name = sys.argv[1]
		start_date = sys.argv[2]
		end_date = sys.argv[3]

	# In case we use the tilde (~) home directory character
	configfile = os.path.expanduser(configfile)

	if not os.path.isfile(configfile):
		print('Error: Config file not found ({})'.format(configfile), file=sys.stderr)
		sys.exit(0)

	config = configparser.ConfigParser()
	config.read(configfile)

	ini_data = config[profile_name]

	# Show usage details
	# Set time component of end date to 23:59:59 to match the behaviour of the Oracle my-services dashboard
	usage = get_account_charges(
		ini_data['username'], ini_data['password'],
		ini_data['domain'], ini_data['idcs_guid'],
		datetime.strptime(start_date, '%d-%m-%Y'),
		datetime.strptime(end_date, '%d-%m-%Y') + timedelta(days=1, seconds=-0.001))

	# Simple output as I use it to feed a report
	print('{:24s} {:6.2f}'.format(profile_name, usage))

