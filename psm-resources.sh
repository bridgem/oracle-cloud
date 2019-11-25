#!/bin/bash
# psm-resources.sh
#
# Report on Oracle OCI PSM services using the psm cli, formatting the json output using 
# jq into a simple CSV report
#
# Command used is of the form
#    psm <service type> services -o json
# e.g.:
#    psm autoanalyticsinst services -o json
#
# The list of services used in this script excludes all classic services no longer 
# available through psm in OCI. If the output of "psm <service> services" says: 
# "Error: Forbidden. ..." then that service is not available in the tenancy.
#
# Dependencies:
#	jq		https://stedolan.github.io/jq/download/
#	profiles
#           Files containing the credentials of each tenancy to be reported on.
#			profile_core.json where core is the tenancy name used in this script, 
#           contents are of the form:
#			{
#			    "username":"martin.bridge@oracle.com",
#			    "password":"MyPassword",
#			    "identityDomain":"idcs-9c8feddae937562fde416deadbeef831",
#			    "region":"emea"
#			}
#
# 18-nov-2019	Martin Bridge	Initial version

# Separator for output
SEP=","

# Temp files for psm output and the jq formatting stream
PSM_OUT=$(mktemp /tmp/psm.XXX)
JQ_STREAM=$(mktemp /tmp/jq.XXX)

# jq formatting commands
echo '
.services |
.[] | 
select(.serviceName) | 
$TENANT + $SEP
+ $SERVICETYPE + $SEP
+ .serviceName + $SEP 
+ .creator + $SEP 
+ .state + $SEP 
+ .region + $SEP 
+ .creationDate
' >$JQ_STREAM 


# Reporting on multiple cloud accounts.  
# Each one initialises psm using a profile json file, e.g. profile_finsvc.json
for tenant in \
    analytics \
	appdev \
	cloudsystems \
	commercial \
	core \
	finsvc \
	innovation \
	pubsec \
	il \
	ie 
do
	# Output the setup to stderr (don't want to capture this)
	psm setup -c profile_${tenant}.json >/dev/null 2>&1 

	# Listing of supported PSM types - there may be more valid ones in your account
	for service in \
        ADBC \
        ANDC \
        APICSAUTO \
        AUTOANALYTICS \
        AUTOANALYTICSINST \
        AUTOBLOCKCHAIN \
        BCSMGR \
        BDCSCE \
        BotSaaSAuto \
        CECSAUTO \
        dbcs \
        DevServiceAppAUTO \
        DIPCAUTO \
        DIPCINST \
        INTEGRATIONCAUTO \
        jcs \
        OABCSINST \
        OEHCS \
        OEHPCS \
        OICINST \
        OMCEXTERNAL \
        SEARCHCLOUDAPP \
        SOA \
        SSI \
        VBINST \
        VISUALBUILDERAUTO \
        wtss 
	do
		# echo "Tenant: ${tenant}    Service: ${service}" 

		# Pass in tenant and service for clarity in the report output
		psm $service services -of json  >$PSM_OUT
        
        # Format json output only on success of psm command, otherwise ignore
        if [ ${?} -eq 0 ]
        then
            jq 	--raw-output \
                -f $JQ_STREAM \
                --arg SEP "$SEP" \
                --arg TENANT "$tenant" \
                --arg SERVICETYPE "$service" \
                $PSM_OUT
        fi
	done
done

rm $JQ_STREAM
rm $PSM_OUT
