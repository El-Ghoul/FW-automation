


import argparse

from ncclient import manager
import json, urllib2, logging, smtplib, time, sys, os
from email.mime.text import MIMEText
from jnpr.junos.exception import *
from datetime import datetime
from jnpr.junos import jxml as JXML
import traceback
import time
import base64

## Logging configuration

logging.basicConfig(level=logging.DEBUG)

# General Variables
def_username = os.environ["SRX_Hosting"]
password = os.environ["SRX_Hosting_PWS"]
smtp_host = 'localhost'
# req_url = 'http://portal.traiana.com/nagios/connectivityFirewallAPI.jsp?requestType=get&status=Approved%20by%20hosting'
req_url = 'http://portal-prod.traiana.com/api/connectivity/firewall/status/CONNECTIVITY_APPROVED_READY_FOR_CREATION'
# pending_url = 'http://portal.traiana.com/nagios/connectivityFirewallAPI.jsp?requestType=get&status=Pending'
mail_from = "ConnectivityPortal@traiana.com"
mail_to = ['network@traiana.com', 'traianacon@traiana.com']
mail_enable = True

set_config = []
report_status = []


# Concocting and apply configuration
def connect(host, def_username, password, set_config, portal_id, port='830'):
    # logging.basicConfig(level=logging.DEBUG)
    conn = manager.connect(host=host,
                           port=port,
                           username=def_username,
                           password=password,
                           timeout=10,
                           device_params={'name': 'junos'},
                           hostkey_verify=False)
    try:
        conn.lock()
        for line in set_config:
            time.sleep(1)
            print 'set junos command: ' + line
            send_config = conn.load_configuration(action='set', config=line)
        else:
            conn.timeout = None
            conn.commit()
            conn.unlock()
            conn.close_session()
            print 'Connectivity portal id:  %s has been update on FW UAT and close successfully ' % (portal_id)
            close_request(portal_id)
            message = 'Connectivity portal id:  %s has been update on FW UAT and close successfully ' % (portal_id)
            send_email(message)
    except RpcTimeoutError:
        raise
        print 'session close successfully with warning'
    return


# commit check
def commit_check(self):
    """
    Perform a commit check.  If the commit check passes, this function
    will return ``True``.  If the commit-check results in warnings, they
    are reported and available in the Exception errs.

    :returns: ``True`` if commit-check is successful (no errors)
    :raises CommitError: When errors detected in candidate configuration.
                         You can use the Exception errs variable
                         to identify the specific problems
    :raises RpcError: When underlying ncclient has an error
    """
    try:
        self.rpc.commit_configuration(check=True)
    except RpcTimeoutError:
        raise
    except RpcError as err:  # jnpr.junos exception
        if err.rsp is not None and err.rsp.find('ok') is not None:
            # this means there is a warning, but no errors
            return True
        else:
            raise CommitError(cmd=err.cmd, rsp=err.rsp, errs=err.errs)
    except Exception as err:
        # :err: is from ncclient, so extract the XML data
        # and convert into dictionary
        return JXML.rpc_error(err.xml)
    return True


# email
def send_email(message):
    if mail_enable is True:
        msg = MIMEText(message)
        msg['Subject'] = message
        msg['From'] = mail_from
        msg['To'] = ", ".join(mail_to)
        s = smtplib.SMTP(smtp_host)
        s.sendmail(mail_from, mail_to, msg.as_string())
        s.quit()


# closing request Portal ID
def close_request(portal_id):
    time.sleep(5)
    print "%s" % portal_id
    try:
        username = 'apiuser'
        password = 'greatapi'
        url = "http://portal-prod.traiana.com/api/update-connectivity"
        requestBody = {'action': 'setConnectivityStatus',
                       'id': portal_id,
                       'targetStatus': "CONNECTIVITY_COMPLETED"
                       }
        data = json.dumps(requestBody)

        val = "Basic %s" % base64.encodestring('%s:%s' % (username, password)).replace('\n', '')
        print '===================='
        headers = {
            'Content-Type': "application/json",
            'Authorization': val
        }
        r = urllib2.Request(url=url, headers=headers, data=data)
        print '===================='
        print 'url=%s' % url
        print 'headers=%s' % headers
        print 'data=%s' % data
        print 'req=%s' % r
        print '===================='
        response = urllib2.urlopen(r).read()
        print response
    except urllib2.HTTPError as err:
        print "Error closing portal request: %s" % err
        print "err code: %s" % err.code
        print "err reason: %s" % err.reason
    except Exception as e:
        print "Error closing portal request"
        message = "Error closing portal request id %s" % portal_id
        send_email(message)
        pass


if __name__ == '__main__':

    json_req = json.load(urllib2.urlopen(req_url))
    for req in json_req:
        print json.dumps(req, sort_keys=True, indent=4, separators=(',', ': '))
        print "debug req: " + str(req)
        portal_id = req['id']
        # UAT and Approved by hosting condition match
        if req['environment'] == 'UAT' and req['status'] == 'CONNECTIVITY_APPROVED_READY_FOR_CREATION':
            print req['environment'] + " is " + req['status']
            connect_method = argparse.ArgumentParser(req['connectionMethod'])
            bloomberg_parse = argparse.ArgumentParser(req['clientName'])
            # ---------------Over Internet----------------
            # FIX (SSL Port 443) Incoming & Outgoing
           # if (connect_method.prog) in req['connectionMethod'] == 'FIX (SSL port 443)' and req['overRadianz'] == 'No':
            if (connect_method.prog) in req['connectionMethod'] == 'FIX (SSL port 443)':
                set_config[:] = []
                if "Incoming" in req['direction']:
                    print req['environment'] + " is " + req[
                        'status'] + " and need to open " + connect_method.prog + " Connecionn Method is " + req[
                              'direction']
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_name = 'FIX_UAT_1'
                        print client_name, single_IP, policy_group_name, req['status'], req['id']
                        set_config.append('set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_name, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
                elif "Outgoing" in req['direction']:
                    set_config[:] = []
                    for Client_Port in ''.join(req['Other (specify port)']).split(','):
                        SingleClient_Port = Client_Port.strip()
                        client_name = '_'.join(req['clientName'].split()).upper()
                        TCP_port_name = 'TCP' + '_' + ''.join(SingleClient_Port)
                        policy_group_name = 'CONNECTIVITY_SERVICES_GROUP_1'
                        set_config.append('set  applications  application  %s  protocol  tcp destination-port %s' % (
                        TCP_port_name, SingleClient_Port))
                        set_config.append(
                            'set  applications  application-set %s application %s' % (policy_group_name, TCP_port_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # FIX / Other (specify port) -  Outgoing to CME only
            elif (connect_method.prog) in req['connectionMethod'] == 'Other (specify port)' and req[
                'clientName'] == 'CME' and req['overRadianz'] == 'No':
                print req['clientName']
                if "Outgoing" in req['direction']:
                    set_config[:] = []
                    for Client_Port in ''.join(req['mqAndOtherPort']).split(','):
                        SingleClient_Port = Client_Port.strip()
                        client_name = '_'.join(req['clientName'].split()).upper()
                        TCP_port_name = 'TCP' + '_' + ''.join(SingleClient_Port)
                        print TCP_port_name
                        policy_group_name = 'CME_SERVICES'
                        print req['id']
                        set_config.append('set applications application %s protocol tcp destination-port %s' % (
                        TCP_port_name, SingleClient_Port))
                        set_config.append(
                            'set applications  application-set %s application %s' % (policy_group_name, TCP_port_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # FIX / Other (specify port) - Outgoing to none  Radianz or Bloomberg customers
            elif (connect_method.prog) in req['connectionMethod'] == 'Other (specify port)' and (
            bloomberg_parse.prog) in req['clientName'] != 'Bloomberg' and req['overRadianz'] == 'No':
                if "Outgoing" in req['direction']:
                    set_config[:] = []
                    for Client_Port in ''.join(req['mqAndOtherPort']).split(','):
                        SingleClient_Port = Client_Port.strip()
                        client_name = '_'.join(req['clientName'].split()).upper()
                        TCP_port_name = 'TCP' + '_' + ''.join(SingleClient_Port)
                        print TCP_port_name
                        print "FIX Outgoing- Other (specify port) to none  Radianz customer"
                        policy_group_name = 'CONNECTIVITY_SERVICES_GROUP_1'
                        print req['id']
                        set_config.append('set applications application %s protocol tcp destination-port %s' % (
                        TCP_port_name, SingleClient_Port))
                        set_config.append(
                            'set applications  application-set %s application %s' % (policy_group_name, TCP_port_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # FIX / Other (specify port) -  Outgoing to Bloomberg only
            elif (connect_method.prog) in req['connectionMethod'] == 'Other (specify port)' and (
            bloomberg_parse.prog) in req['clientName'] == 'Bloomberg' and req['overRadianz'] == 'No':
                print req['clientName']
                if "Outgoing" in req['direction']:
                    set_config[:] = []
                    for Client_Port in ''.join(req['mqAndOtherPort']).split(','):
                        SingleClient_Port = Client_Port.strip()
                        client_name = '_'.join(req['clientName'].split()).upper()
                        TCP_port_name = 'TCP' + '_' + ''.join(SingleClient_Port)
                        print TCP_port_name
                        print "FIX Outgoing- Other (specify port) Bloomberg"
                        policy_group_name = 'BLOOMBERG_SERVICES_1'
                        print req['id']
                        set_config.append('set applications application %s protocol tcp destination-port %s' % (
                        TCP_port_name, SingleClient_Port))
                        set_config.append(
                            'set applications  application-set %s application %s' % (policy_group_name, TCP_port_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # FIX (NON SSL Port 3400)
            elif (connect_method.prog) in req['connectionMethod'] == 'FIX (NON SSL Port 443)' and req[
                'overRadianz'] == 'No':
                if "Incoming" in req['direction']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_name = 'FIX_UAT_NO_SSL_1'
                        set_config.append('set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_name, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # HTTPS_UPLOAD
            elif (connect_method.prog) in req['connectionMethod'] == 'HTTPS_UPLOAD' and req['overRadianz'] == 'No':
                if "Incoming" in req['direction']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_name = 'HTTP_UPLOAD_UAT'
                        set_config.append('set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_name, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # HTTPS (SSL port 443)
            elif (connect_method.prog) in req['connectionMethod'] == 'HTTPS (SSL port 443)' and req['overRadianz'] == 'No':
                if "Incoming" in req['direction']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_name = 'HTTP_UPLOAD_UAT'
                        set_config.append('set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_name, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # sFTP
            elif (connect_method.prog) in req['connectionMethod'] == 'sFTP' and req['overRadianz'] == 'No':
                if "Incoming" in req['direction']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_name = 'SFTP_UAT_1'
                        set_config.append(
                            'set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                            policy_group_name, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # FTP
            elif (connect_method.prog) in req['connectionMethod'] == 'FTP' and req['overRadianz'] == 'No':
                if "Incoming" in req['direction']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_name = ' FTP_UAT_1'
                        set_config.append(
                            'set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_name, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # TOF (TCP port 5003)
            elif (connect_method.prog) in req['connectionMethod'] == 'TOF (TCP port 5003)' and req[
                'overRadianz'] == 'No':
                if "Incoming" in req['direction']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_name = 'TOF_UAT_1'
                        set_config.append('set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_name, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # TOF-DF (SSL)
            elif (connect_method.prog) in req['connectionMethod'] == 'TOF-DF (SSL)' and req['overRadianz'] == 'No':
                if "Incoming" in req['direction']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_name = 'DF_TOF_UAT_INTERNET_1'
                        set_config.append('set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_name, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # KillSwitch
            elif (connect_method.prog) in req['connectionMethod'] == 'KillSwitch' and req['overRadianz'] == 'No':
                if "Incoming" in req['direction']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_name = 'KILLSWITCH_UAT_1'
                        print client_name, single_IP, policy_group_name
                        set_config.append('set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_name, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # FIX LHUB_TO_EXTERNAL (SSL Port 443/3400) -  Incoming & Both
            elif (connect_method.prog) in req['connectionMethod'] == 'FIX LimitHub (SSL Port 443)' or req[
                'connectionMethod'] == 'FIX LimitHub (NON-SSL Port 3400 - Radianz)' and req['overRadianz'] == 'No':
                if "Incoming" in req['direction']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_LHub_In = 'LHUB_CUSTOMERS_IN_1'
                        set_config.append('set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_LHub_In, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
                elif 'Both' in req['direction']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_LHub_Out = 'LHUB_CUSTOMERS_OUT_1'
                        policy_group_LHub_In = 'LHUB_CUSTOMERS_IN_1'
                        print client_name, single_IP, policy_group_LHub_Out, policy_group_LHub_In
                        set_config.append('set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_LHub_In, client_name))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_LHub_Out, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # sFTP LHUB_From_EXTERNAL
            elif (connect_method.prog) in req['connectionMethod'] == 'sFTP LimitHub' and req['overRadianz'] == 'No':
                if "Incoming" in req['direction']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_name = 'LHUB_CUSTOMERS_IN_1'
                        set_config.append('set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_name, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # FTP LHUB_From_EXTERNAL
            elif (connect_method.prog) in req['connectionMethod'] == 'FTP LimitHub' and req['overRadianz'] == 'No':
                if "Incoming" in req['direction']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_name = 'LHUB_CUSTOMERS_IN_1'
                        set_config.append('set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_name, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # Over--Radianz-Outgoing_MQ(specify port)-/Incoming_MQ(port 1414/1421/5415)/1415/MQ_JP-1418
            elif (connect_method.prog) in req['connectionMethod'] == 'MQ (specify port)' and req[
                'overRadianz'] == 'Yes':
                if "Outgoing" in req['direction']:
                    set_config[:] = []
                    for Client_Port in ''.join(req['mqAndOtherPort']).split(','):
                        SingleClient_Port = Client_Port.strip()
                        client_name = '_'.join(req['clientName'].split()).upper()
                        TCP_port_name = 'TCP' + '_' + ''.join(SingleClient_Port)
                        print TCP_port_name
                        policy_group_name = 'MQ_SERVICES_1'
                        set_config.append('set  applications  application  %s  protocol  tcp destination-port %s' % (
                        TCP_port_name, SingleClient_Port))
                        set_config.append(
                            'set  applications  application-set %s application %s' % (policy_group_name, TCP_port_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
                # Over  Radianz- MQ(port 1414/1421/5415)
                elif 'Incoming' in req['direction'] and '1414' in req['mqAndOtherPort'] or '1421' in req[
                    'mqAndOtherPort'] or '5415' in req['mqAndOtherPort']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_name = 'MQ_UAT_1414_1'
                        set_config.append('set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_name, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
                # Over  Radianz- MQ(port 1415)
                elif '1415' in req['mqAndOtherPort']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_name = 'MQ_UAT_1415_1'
                        set_config.append('set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_name, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
                # Over  Radianz- MQ JP(port 1418)
                elif '1418' in req['mqAndOtherPort']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_name = 'MQ_UAT_1418_JP_1'
                        set_config.append(
                            'set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_name, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # over Radianz - ADAPTERS Outgoing
            elif (connect_method.prog) in req['connectionMethod'] == 'Other (specify port)' and req[
                'overRadianz'] == 'Yes':
                if "Outgoing" in req['direction']:
                    set_config[:] = []
                    for Client_Port in ''.join(req['mqAndOtherPort']).split(','):
                        SingleClient_Port = Client_Port.strip()
                        client_name = '_'.join(req['clientName'].split()).upper()
                        TCP_port_name = 'TCP' + '_' + ''.join(SingleClient_Port)
                        print TCP_port_name
                        policy_group_name = 'CONNECTIVITY_SERVICES_GROUP_1'
                        print req['id']
                        set_config.append('set applications application %s protocol tcp destination-port %s' % (
                        TCP_port_name, SingleClient_Port))
                        set_config.append(
                            'set applications  application-set %s application %s' % (policy_group_name, TCP_port_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # RADIANZ_TO_LHUB (SSL Port 443 or 3400) -  Incoming & Both
            elif (connect_method.prog) in req['connectionMethod'] == 'FIX LimitHub (SSL Port 443)' or req[
                'connectionMethod'] == 'FIX LimitHub (NON-SSL Port 3400 - Radianz)' and req['overRadianz'] == 'Yes':
                if "Incoming" in req['direction']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_LHub_In = 'LHUB_CUSTOMERS_IN_1'
                        set_config.append('set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_LHub_In, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
                elif 'Both' in req['direction']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_LHub_Out = 'LHUB_CUSTOMERS_OUT_1'
                        policy_group_LHub_In = 'LHUB_CUSTOMERS_IN_1'
                        set_config.append('set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_LHub_In, client_name))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_LHub_Out, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # sFTP LHUB_From_EXTERNAL
            elif (connect_method.prog) in req['connectionMethod'] == 'sFTP LimitHub' and req['overRadianz'] == 'Yes':
                if "Incoming" in req['direction']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_name = 'LHUB_CUSTOMERS_IN_1'
                        set_config.append('set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_name, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # FTP LHUB_From_EXTERNAL
            elif (connect_method.prog) in req['connectionMethod'] == 'FTP LimitHub' and req['overRadianz'] == 'Yes':
                if "Incoming" in req['direction']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_name = 'LHUB_CUSTOMERS_IN_1'
                        set_config.append('set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_name, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # FIX (SSL Port 443) Incoming & Outgoing
            elif (connect_method.prog) in req['connectionMethod'] == 'FIX (SSL port 443)' and req[
                'overRadianz'] == 'Yes':
                if "Incoming" in req['direction']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        print "FIX(SSL  Port 443) - Incoming"
                        policy_group_name = 'FIX_UAT_1'
                        set_config.append('set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_name, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
                elif "Outgoing" in req['direction']:
                    set_config[:] = []
                    for Client_Port in ''.join(req['Other (specify port)']).split(','):
                        SingleClient_Port = Client_Port.strip()
                        client_name = '_'.join(req['clientName'].split()).upper()
                        TCP_port_name = 'TCP' + '_' + ''.join(SingleClient_Port)
                        print "FIX specify port Outgoing"
                        policy_group_name = 'CONNECTIVITY_SERVICES_GROUP_1'
                        set_config.append('set applications application  %s  protocol  tcp destination-port %s' % (
                        TCP_port_name, SingleClient_Port))
                        set_config.append(
                            'set applications application-set %s application %s' % (policy_group_name, TCP_port_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # FIX (NON-SSL Port 3400 - Radianz)
            #            elif (connect_method.prog) in req[ 'connectionMethod' ] == 'FIX (NON-SSL Port 3400 - Radianz)' and req['overRadianz'] == 'Yes':
            elif (connect_method.prog) in req['connectionMethod'] == 'FIX (NON-SSL port 3400 - Radianz)':
                if "Incoming" in req['direction']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        print 'FIX (NON-SSL port 3400 - Radianz)'
                        policy_group_name = 'FIX_UAT_NO_SSL_1'
                        set_config.append('set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_name, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # TOF (TCP port 5003) - Radianz
            elif (connect_method.prog) in req['connectionMethod'] == 'TOF (TCP port 5003)' and req[
                'overRadianz'] == 'Yes':
                if "Incoming" in req['direction']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_name = 'TOF_UAT_1'
                        set_config.append('set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_name, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # TOF-DF - Radianz
            elif (connect_method.prog) in req['connectionMethod'] == 'TOF-DF (SSL )' and req['overRadianz'] == 'Yes':
                if "Incoming" in req['direction']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_name = 'DF_TOF_UAT_RADIANZ_1'
                        set_config.append('set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_name, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # FTP - Radianz
            elif (connect_method.prog) in req['connectionMethod'] == 'FTP' and req['overRadianz'] == 'Yes':
                if "Incoming" in req['direction']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_name = ' FTP_UAT_1'
                        set_config.append('set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_name, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)
            # sFTP  Radianz
            elif (connect_method.prog) in req['connectionMethod'] == 'sFTP' and req['overRadianz'] == 'Yes':
                if "Incoming" in req['direction']:
                    set_config[:] = []
                    for client_IP in ''.join(req['clientSourceIpAddress()']).split(','):
                        single_IP = client_IP.strip()
                        client_name = '_'.join(req['clientName'].split()).upper() + '_' + ''.join(single_IP)
                        policy_group_name = 'SFTP_UAT_1'
                        set_config.append('set security address-book global address %s %s' % (client_name, single_IP))
                        set_config.append('set security address-book global address-set %s address %s' % (
                        policy_group_name, client_name))
                    else:
                        portal_id = req['id']
                        connect('192.168.160.1', 'root', password, set_config, portal_id)

            else:
                print "Could not find any connectionMethod match"

        #              message = "Connectivity Portal - Portal ID %s not match to any of the options , Please check with Network Team" % (portal_id)
        #              send_email(message)
        else:
            print 'Could not find any UAT portal id with status: Approved by hosting'
    print 'End of the Program'
    logging.shutdown()

# TODO add report of ID to be close
# TODO send email to ID status
