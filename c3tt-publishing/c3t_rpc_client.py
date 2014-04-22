#!/usr/bin/python3
#    Copyright (C) 2014  derpeter
#    derpeter@berlin.ccc.de
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import xmlrpc.client
import hashlib
import hmac
import socket
import urllib
import xml

## client constructor #####
# group: worker group
# secret: client secret
# host: client hostname (will be taken from local host if set to None)
# url: tracker url (without the rpc)
# method: method to access
############################
def C3TClient(url, method, group, host, secret, args):
    if host == None:
        host = socket.getfqdn()
        
    #####################
    # generate signature
    #####################
    # assemble static part of signature arguments
    # 1. URL  2. method name  3. worker group token  4. hostname
    sig_args = url + "&" + method + "&" + group + "&" + host + "&"
    
    #### add method args
    if len(args) > 0:
        i = 0
        while i < len(args):
            sig_args = str(sig_args) + str(args[i])
            if i < (len(args) -1):
                sig_args = sig_args + "&" 
            i = i + 1
    
    ##### quote URL and generate the hash     
    #hash signature
    sig_args_enc = urllib.parse.quote_plus(sig_args)
        
    #### generate the hmac hash with key
    hash =  hmac.new(bytes(secret, 'utf-8'), bytes(sig_args_enc, 'utf-8'), hashlib.sha256)
    
    #### add signature as last parameter to the arg list
    args.append(hash.hexdigest())
    
    #### create xmlrpc client

    try:
        proxy = xmlrpc.client.ServerProxy(url + "?group=" + group + "&hostname=" + host);
    except xmlrpc.client.Fault as err:
        print("A fault occurred")
        print("Fault code: %d" % err.faultCode)
        print("Fault string: %s" % err.faultString)
    except xmlrpc.client.ProtocolError as err:
        print("A protocol error occurred")
        print("URL: %s" % err.url)
        print("HTTP/HTTPS headers: %s" % err.headers)
        print("Error code: %d" % err.errcode)
        print("Error message: %s" % err.errmsg)
    except socket.gaierror as err:
        print("A socket error occurred")
        print(err)
    except xmlrpc.client.ProtocolError as err:
        print("A Protocol occurred")
        print(err)
    
    #### call the given method with args
    try:
        result = getattr(proxy,method)(*args)
    except xml.parsers.expat.ExpatError as err:
        print("A expat err occured")
        print(err)
    except xmlrpc.client.Fault as err:
        print("A fault occurred")
        print("Fault code: %d" % err.faultCode)
        print("Fault string: %s" % err.faultString)

    #### return the result
    return result

def open_rpc(method, args):
    result = C3TClient(url, method, group, host, secret, args)
    return result

### get Tracker Version
def getVersion():
    tmp_args = ["1"];
    return str(open_rpc("C3TT.getVersion",tmp_args))

### check for new ticket on tracker an get assignement 
def assignNextUnassignedForState():
    tmp_args = [from_state, to_state]
    xml = open_rpc("C3TT.assignNextUnassignedForState",tmp_args)
    # if get no xml there seems to be no ticket for this job
    if xml == False:
        return False
    else:
        print(xml)
        return xml['id']

### get ticket properties 
def getTicketProperties(id):
    tmp_args = [id]
    xml = open_rpc("C3TT.getTicketProperties",tmp_args)
    if xml == False:
        print("no xml in answer")
        return None
    else:
        print(xml)
        return xml

### set Ticket status on done
def setTicketDone(id):
    tmp_args = [id]
    xml = open_rpc("C3TT.setTicketDone", tmp_args)
    print(xml)
    
### set ticket status on failed an supply a error text
def setTicketFailed(id,error):
    tmp_args = [id, error]
    xml = open_rpc("C3TT.setTicketFailed", tmp_args)
