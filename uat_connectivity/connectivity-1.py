#!/usr/bin/env python

import logging
from ncclient import manager
import time

def connect(host, user, password):
    logging.basicConfig(level=logging.DEBUG)
    conn = manager.connect(host='192.168.160.1',
            port=830,
            username='root',
            password='S1ngl3M^ltOk',
            timeout=10,
            device_params = {'name':'junos'},
            hostkey_verify=False)
    conn.lock()

    # configuration as a string
    #send_config = conn.load_configuration(action='set', config='set interfaces ge-0/0/0 description test1---testestdtlk')
    #send_config = conn.load_configuration(action='set', config='set interfaces ge-2/0/6 description ---UNUSED---2999')
    # configuration as a list
    location =[]
    location.append('set interfaces ge-2/0/6 description ---UNUSED---99')
    location.append('set interfaces ge-2/0/7 description ---UNUSED---999')
    location.append('set interfaces ge-2/0/8 description ---UNUSED---999')


    send_config = conn.load_configuration(action='set', config=location)
    print send_config.tostring

    #check_config = conn.validate()
    #print check_config.tostring
    #time.sleep(5)
    #compare_config = conn.compare_configuration()
    #print compare_config.tostring

    conn.commit()
    time.sleep(10)
    conn.unlock()
    conn.close_session()

if __name__ == '__main__':
    connect('router', 'netconf', 'juniper!')
