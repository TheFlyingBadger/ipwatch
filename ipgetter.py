#!/usr/bin/env python
"""
This module is designed to fetch your external IP address from the internet.
It is used mostly when behind a NAT.
It picks your IP randomly from a serverlist to minimize request
overhead on a single server

If you want to add or remove your server from the list contact me on github


API Usage
=========

    >>> import ipgetter
    >>> myip = ipgetter.myip()
    >>> myip
    '8.8.8.8'

    >>> ipgetter.IPgetter().test()

    Number of servers: 47
    IP's :
    8.8.8.8 = 47 ocurrencies


Copyright 2014 phoemur@gmail.com
This work is free. You can redistribute it and/or modify it under the
terms of the Do What The Fuck You Want To Public License, Version 2,
as published by Sam Hocevar. See http://www.wtfpl.net/ for more details.
"""

import re
import random
import ssl
import json
import os 
import six

from datetime import datetime, timedelta
from sys      import exc_info

if six.PY3:
    import urllib.request   as urllib
    import http.cookiejar   as cjar
else:
    import urllib2          as urllib
    import cookielib        as cjar

__version__ = "0.7"


def myip():
    return IPgetter().get_externalip()

def myipAndSource():
    return IPgetter().get_externalip_and_source()


class IPgetter(object):

    '''
    This class is designed to fetch your external IP address from the internet.
    It is used mostly when behind a NAT.
    It picks your IP randomly from a serverlist to minimize request overhead
    on a single server
    '''

    def __init__(self):
        
        JSON_LIST_URL = "https://raw.githubusercontent.com/begleysm/ipwatch/master/servers.json"
        JSON_FILENAME = 'serverCache.json'
        JSON_ERRFILE  = os.path.basename(JSON_LIST_URL)
        now           = datetime.now()
        currentTS     = datetime.timestamp(now)
        theList       = None

        def writeJSONCache (theContent, theFilename = JSON_FILENAME):
            if six.PY3:
                with open(theFilename, 'w',encoding="utf-8") as outfile:
                    outfile.write(theContent)
            else:
                with open(theFilename, 'w') as outfile:
                    outfile.write(theContent)

        if os.path.isfile(JSON_FILENAME):
            try:
                with open(JSON_FILENAME, 'r') as infile:
                    theList   = json.load (infile)
            except:
                pass

        #
        # remove any dumped copy of servers.json that we've got (this is only created by an exception in conversion to JSON)
        #
        try:
            os.remove(JSON_ERRFILE)
        except FileNotFoundError:
            pass
        except PermissionError:
            t, v, tb = exc_info()
            print (v)
                
        if (theList is None
         or "expiry"         not in theList
         or "expiryDisplay"  not in theList
         or "servers"        not in theList
         or theList["expiry"]         is None
         or theList["expiryDisplay"]  is None
         or theList["servers"]        is None
         or not isinstance(theList["expiry"],float)
         or len(str(theList["expiry"])) == 0
         or not isinstance(theList["servers"],list)
         or len(theList["servers"])     == 0
         or theList["expiry"] < currentTS
           ): # we will go off and get the list again
            expiryDate = (now +  timedelta(days=90))
            theList = dict (expiry         = datetime.timestamp(expiryDate)
                           ,expiryDisplay  = expiryDate.strftime('%Y-%m-%dT%H:%M:%S')
                           ,servers        = []
                           )
            operUrl = urllib.urlopen(JSON_LIST_URL)
            if(operUrl.getcode()==200):
                data               = operUrl.read()
                try:
                    theList["servers"] = json.loads(data)
                    writeJSONCache (json.dumps(theList, indent=4))
                except:
                    t, v, tb = exc_info()
                    writeJSONCache (data, theFilename=JSON_ERRFILE)
                    six.reraise(t, v, tb)
            else:
                print("Error receiving data", operUrl.getcode())
        self.server_list = theList["servers"]
        theList = None

    def get_externalip(self):
        '''
        This function gets your IP from a random server
        '''
        return (self.get_externalip_and_source())["ip"]

    def get_externalip_and_source(self):
        '''
        This function gets your IP from a random server, it also returns which server that was
        '''
        myip = dict (ip     = None
                    ,server = None
                    )
        #myip = ''
        for i in range(7):
            myip["server"] = random.choice(self.server_list)
            myip["ip"]     = self.fetch(myip["server"])
            if myip["ip"] is not None and len(myip["ip"]) > 0:
                break
        return myip

    def fetch(self, server):
        '''
        This function gets your IP from a specific server.
        '''
        url = None
        cj = cjar.CookieJar()
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        opener = urllib.build_opener(urllib.HTTPCookieProcessor(cj), urllib.HTTPSHandler(context=ctx))
        opener.addheaders = [('User-agent', "Mozilla/5.0 (X11; Linux x86_64; rv:57.0) Gecko/20100101 Firefox/57.0"),
                             ('Accept', "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
                             ('Accept-Language', "en-US,en;q=0.5")]

        try:
            url = opener.open(server, timeout=4)
            content = url.read()

            # Didn't want to import chardet. Prefered to stick to stdlib
            if six.PY3:
                try:
                    content = content.decode('UTF-8')
                except UnicodeDecodeError:
                    content = content.decode('ISO-8859-1')

            m = re.search(
                '(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)',
                content)
            myip = m.group(0)
            return myip if len(myip) > 0 else ''
        except Exception:
            return ''
        finally:
            if url:
                url.close()

    def test(self):
        '''
        This functions tests the consistency of the servers
        on the list when retrieving your IP.
        All results should be the same.
        '''

        resultdict = {}
        for server in self.server_list:
            resultdict.update(**{server: self.fetch(server)})

        ips = sorted(resultdict.values())
        ips_set = set(ips)
        print('\nNumber of servers: {}'.format(len(self.server_list)))
        print("IP's :")
        for ip, ocorrencia in zip(ips_set, map(lambda x: ips.count(x), ips_set)):
            print('{0} = {1} ocurrenc{2}'.format(ip if len(ip) > 0 else 'broken server', ocorrencia, 'y' if ocorrencia == 1 else 'ies'))
        print('\n')
        print(resultdict)

if __name__ == '__main__':
    print(myip())
    print(myipAndSource())
