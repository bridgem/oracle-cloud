# List all PSM Resources
#
# Parameters:
#	 	profile_name
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
# 27-nov-2019   1.0     mbridge     Created

import requests
import sys
import configparser
import os
import json

# ======================================================================================================================
debug: bool = False
configfile = '~/.oci/config.ini'
# ======================================================================================================================


def list_psm_services(tenancy_name, username, password, idcs_guid):

	if debug:
		print(f'User:Pass = {username}/{"*" * len(password)}')
		print(f'IDCSID    = {idcs_guid}')

	# Print Headings
	print(
		f"{'Tenancy':22} "
		f"{'Service Type':18} "
		f"{'Service Name':20.20} "
		f"{'Creator':28.28} "
		f"{'State':10} "
		f"{'Region':15} "
		f"{'CreationDate':32} ")

	service_type_list = ["adbc", "andc", "apicsauto", "autoanalytics", "autoanalyticsinst", "autoblockchain", "bcsmgr",
						 "bdcsce", "botsaasauto", "cecsauto", "dbcs", "devserviceappauto", "dipcauto", "dipcinst",
						 "integrationcauto", "jcs", "oabcsinst", "oehcs", "oehpcs", "oicinst", "omcexternal",
						 "searchcloudapp", "soa", "ssi", "vbinst", "visualbuilderauto", "wtss"]

	# service_type_list = ["autoanalytics", "autoanalyticsinst",]

	for service_type in service_type_list:
		resp = requests.get(
			"https://psm.europe.oraclecloud.com/paas/api/v1.1/instancemgmt/"
			+ idcs_guid + "/services/" + service_type + "/instances?limit=500",
			auth=(username, password),
			headers={'X-ID-TENANT-NAME': idcs_guid}
		)

		if resp.status_code != 200:
			# This means something went wrong.
			print(f'Error in GET: {resp.status_code} ({resp.reason}) '
				  f'on tenancy {tenancy_name}, service type {service_type}', file=sys.stderr)
			# msg = json.loads(resp.text)['errorMessage']
			# print(f'  {msg}', file=sys.stderr)
			# return -1
		else:
			svc_list = resp.json()
			for services in resp.json()['services'].items():
				svc = services[1]
				print(
					f"{tenancy_name:22} "
					f"{svc['serviceType']:18} "
					f"{svc['serviceName']:20.20} "
					f"{svc['creator']:28.28} "
					f"{svc['state']:10} "
					f"{svc['region']:15} "
					f"{svc['creationDate']:32} ")

				# TODO: Handle isBYOL flag
	return


def tenancy_usage(tenancy_name):

	# Just in case we use the tilde (~) home directory character
	configfilepath = os.path.expanduser(configfile)

	if not os.path.isfile(configfilepath):
		print(f'Error: Config file not found ({configfilepath})', file=sys.stderr)
		sys.exit(0)

	config = configparser.ConfigParser()
	config.read(configfilepath)

	ini_data = config[tenancy_name]
	ppp = ini_data['password']

	# Get all service details
	list_psm_services(tenancy_name, ini_data['username'], ini_data['password'], ini_data['idcs_guid'])


if __name__ == "__main__":
	# Get profile from command line
	if len(sys.argv) != 2:
		print(f'Usage: {sys.argv[0]} <profile_name>')
		sys.exit()
	else:
		tenancy_name = sys.argv[1]

	tenancy_usage(tenancy_name)

	if debug:
		print('DONE')
