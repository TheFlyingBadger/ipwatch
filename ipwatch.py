#!//usr/bin/env python3

#USAGE: python3 ipwatch.py [config]
#USAGE: ./ipwatch.py [config]
#
#[config] = path to an IPWatch configuration file
#
#Sean Begley
#2017-10-31
# v0.4
#
#This program gets for your external IP address
#checks it against your "saved" IP address and,
#if a difference is found, emails you the new IP.
#This is useful for servers at residential locations
#whose IP address may change periodically due to actions
#by the ISP.

#REFERENCES
#https://github.com/phoemur/ipgetter

import sys
from pathlib import Path
import re
import smtplib, ssl, os.path, socket, argparse
import ipgetter


################
### CLASSES ####
################

#container for config file information
class ConfigInfo:
    "This class contains all of the information from the config file"
    sender            = ""
    sender_email      = ""
    sender_username   = ""
    sender_password   = ""
    receiver          = []
    receiver_email    = []
    subject_line      = ""
    machine           = ""
    smtp_addr         = ""
    smtp_host         = None
    smtp_port         = None
    smtp_use_ssl      = None
    save_ip_path      = ""
    try_count         = ""
    ip_blacklist      = []

    def __init__(self):
        self.sender          = ""
        self.sender_email    = ""
        self.sender_username = ""
        self.sender_password = ""
        self.receiver        = []
        self.receiver_email  = []
        self.subject_line    = ""
        self.machine         = ""
        self.smtp_addr       = ""
        self.smtp_host       = None
        self.smtp_port       = None
        self.smtp_use_ssl    = None
        self.save_ip_path    = ""
        self.try_count       = ""
        self.ip_blacklist    = []

    def __str__(self):
        # this handles "print(obj)" for us
        output = []
        def write (tag, val):
            if (val is not None):
                if type(val) in [int,bool]:
                    val = str(val)
                if len(val) > 0:
                    line = tag.ljust(16)+" : "
                    if type(val) == list:
                        line += ','.join(val)
                    else:
                        line += val
                    output.append (line)
                    line = None
        for attr, value in (self.__dict__).items():
            write (attr, value)
        if len(output) == 0:
            output.append ("No attributes set")
        stringVal = '\n'.join(output)
        output    = None
        return stringVal

    def validateConfig(self):

        def ensureNotNull (val, text):
            if val is None or len(val) == 0:
                raise ValueError ("\'%s\' value not present in config file" % text)
        def nvl (val, valueIfNull):
            if val is None or len(val) == 0:
                val = valueIfNull
            return val

        ensureNotNull(self.sender_email   ,'sender_email')
        ensureNotNull(self.sender_username,'sender_username')
        ensureNotNull(self.sender_password,'sender_password')
        ensureNotNull(self.receiver_email ,'receiver_email')
        ensureNotNull(self.smtp_addr      ,'smtp_addr')
        ensureNotNull(self.save_ip_path   ,'save_ip_path')
        ensureNotNull(str(self.try_count) ,'try_count')

        # Assign some default values if there's not been any supplied
        self.sender       = nvl(self.sender,self.sender_email)
        self.machine      = nvl(self.machine,socket.gethostname())
        self.subject_line = nvl(self.subject_line,"My IP Has Changed!")
        self.ip_blacklist = nvl(self.ip_blacklist,[])

        # if the list of receiver names is not the same length as the list of emails, then default the lot
        if len(self.receiver) is None or len(self.receiver) != len(self.receiver_email):
            self.receiver = self.receiver_email

        # split up SMTP
        smtp = self.smtp_addr.split(":")
        if len(smtp) == 2 and smtp[1].isdigit():
            self.smtp_port = int(smtp[1])
        elif len(smtp) == 1: # no Port, assume port 25
            self.smtp_port = 25
        else:
            raise ReferenceError ("SMTP_ADDR not set correctly in config")
        self.smtp_host     = smtp[0]
        self.smtp_use_ssl  = not (self.smtp_port == 25)
        smtp = None

        # make sure value_error is a positive integer
        try:
            dummy = int(self.try_count)
            if dummy <= 0:
                raise ValueError
        except ValueError:
            raise ValueError("TRY_COUNT must be a positive integer")

        # make sure the entries in the IP blacklists are valid
        for thisIP in self.ip_blacklist:
            if not is_valid_ip(thisIP):
                raise ValueError("Invalid IP_BLACKLIST entry \'%s\'" % thisIP)


################
## FUNCTIONS ###
################

def is_valid_ip(ip):
    """Validates IP addresses.
    """
    return is_valid_ipv4_address(ip) or is_valid_ipv6_address(ip)

def is_valid_ipv4_address(address):
    try:
        socket.inet_pton(socket.AF_INET, address)
    except AttributeError:  # no inet_pton here, sorry
        try:
            socket.inet_aton(address)
        except socket.error:
            return False
        return address.count('.') == 3
    except socket.error:  # not a valid address
        return False

    return True

def is_valid_ipv6_address(address):
    try:
        socket.inet_pton(socket.AF_INET6, address)
    except socket.error:  # not a valid address
        return False
    return True

# #help message print
# def printhelp():
#     "Function to print out the help message"
#     print("""\r\nIPWatch v0.4 by Sean Begley (begleysm@gmail.com)

# IPWatch is a tool to check your current external IP address against a saved, previous, external IP address.  It should be run as a scheduled task/cronjob periodically.  If a difference in the new vs old IP address is found it will dispatch an email describing the change.

# USAGE: python3 ipwatch.py [config]
# USAGE: ./ipwatch.py [config]

# [config] = path to an IPWatch configuration file

# EXAMPLE USAGE: ./ipwatch.py /home/bob/ipwatch/config.txt
# """)
#     return

#read config file
def readconfig(filepath,  configObj):
    "Function to read a config file with email information"
    #check if the configfile exists
    if not Path(filepath).is_file(): # should never happen
        raise FileNotFoundError(filepath)

    #open configfile
    with open(filepath, "r") as configfile:
        lines = configfile.readlines()

    #parse the contents
    for line in lines:
        #ignore comments and blank lines
        if (line[:1] != "#" and line.strip()):
            #remove trailing whitespace and newline chars
            line = line.rstrip()
            param = line.rpartition('=')[0].lower()
            value = line.rpartition('=')[2]
            #print ("param = %s\t\tvalue = %s" % (param, value))

            #save parameters in configObj
            if (param == "sender"):
                configObj.sender = value
            elif (param == "sender_email"):
                configObj.sender_email = value
            elif (param == "sender_username"):
                configObj.sender_username = value
            elif (param == "sender_password"):
                configObj.sender_password = value
            elif (param == "receiver"):
                configObj.receiver = value.split(',')
            elif (param == "receiver_email"):
                configObj.receiver_email = value.split(',')
            elif (param == "subject_line"):
                configObj.subject_line = value
            elif (param == "machine"):
                configObj.machine = value
            elif (param == "smtp_addr"):
                configObj.smtp_addr = value
            elif (param == "save_ip_path"):
                configObj.save_ip_path = value
            elif (param == "try_count"):
                configObj.try_count = value
            elif (param == "ip_blacklist"):
                configObj.ip_blacklist = value.split(',')
            else:
                print ("ERROR: unexpected line found in config file: %s" % line)

    # validate the config
    configObj.validateConfig()

    print (configObj)

#return the current external IP address
def getip(try_count, blacklist):
    "Function to return the current, external, IP address"
    return (getipAndSource(try_count, blacklist))["ip"]

#return the current external IP address
def getipAndSource(try_count, blacklist):
    "Function to return the current, external, IP address and the site from which that info was retrieved"
    
    #try up to config.try_count servers for an IP
    for counter in range(try_count):
        #get an IP
        theIP  = ipgetter.myipAndSource()
        
        #check to see that it has a ###.###.###.### format
        if  not (is_valid_ip(theIP["ip"])):
            print ("GetIP: Try %d:  Bad IP    (malformed): %s" % (counter+1, theIP["ip"]))
        elif theIP["ip"] in blacklist:
            print ("GetIP: Try %d:  Bad IP (in Blacklist): %s" % (counter+1, theIP["ip"]))
        else:
            print ("GetIP: Try %d: Good IP               : %s" % (counter+1, theIP["ip"]))
            break
    
    return theIP

#get old IP address
def getoldip(filepath):
    "Function to get the old ip address from savefile"
    oldip = dict (ip     = None
                 ,server = None
                 )
    # check if the savefile exists
    if Path(filepath).is_file():
        #open savefile
        fileContent = []
        with open(filepath, "r") as savefile:
            fileContent = savefile.read().strip().split(',')
            
        #check if the content of savefile makes sense
        if len(fileContent) == 0:
            oldip["ip"] = "Mangled File"
        else:
            oldip["ip"] = fileContent[0]
            if len(fileContent) > 1:
                # take the IP address out, then join the of the entries together (in case of any "comma in URL" stupidity)
                del fileContent[0]
                oldip["server"] = ','.join(fileContent)
            if not is_valid_ip(oldip["ip"]):
                oldip["ip"] = "malformed (\'%s\')" % oldip["ip"]
    else:
        oldip["ip"] = "File \'%s\' not found" % filepath
        
    return oldip

#write the new IP address to file
def updateoldip(filepath,  newip):
    "Function to update the old ip address from savefile"
    #open savefile
    dictList = [newip["ip"],newip["server"]]
    with open(filepath, "w") as savefile:
        #write new ip
        savefile.write(','.join(dictList))
    dictList = None

def connect_smtp_server(server_domain, server_port, use_ssl=False):
    smtp_server = None
    if use_ssl == True:
        ctx = ssl.create_default_context('smtp server use ssl encryption', cafile=None, capath=None, cadata=None)
        # start ssl encryption from very beginning.
        smtp_server = smtplib.SMTP_SSL(server_domain, server_port, context=ctx)
        # or you can start tls after smtp server object is created as below.
        # smtp_server = smtplib.SMTP(server_domain, server_port)
        # smtp_server.starttls(context=ctx)
    else:
        smtp_server = smtplib.SMTP(server_domain, server_port)
        
    return smtp_server

def send_plain_text_email(smtp_server, from_addr, to_addrs, email_subject, email_content):
    from email                import encoders
    from email.header         import Header
    from email.mime.base      import MIMEBase
    from email.mime.text      import MIMEText
    from email.mime.image     import MIMEImage
    from email.mime.multipart import MIMEMultipart
    from email                import charset
    msg = MIMEText(email_content, 'plain', 'utf-8')
    msg['From'] = from_addr
    '''Because to_addrs is a tuple, so you need to join the tuple element to a string with comma separated,
       otherwise it will throw  AttributeError: 'tuple' object has no attribute 'encode' '''
    msg['To'] = ','.join(to_addrs)
    msg['Subject'] = Header(email_subject, 'utf-8').encode()
    smtp_server.send_message(msg, from_addr, to_addrs)
    print('Send plain text email complete.')

#send mail with new IP address
def sendmail(oldip,  newip,  config):
    "Function to send an email with the new IP address"

    def nameAddrPair (_name, _addr):
        return '\"%s\" <\"%s\">' % (_name, _addr)

    to       = []
    for ix, addr in enumerate(config.receiver_email):
        to.append (nameAddrPair (config.receiver[ix], addr))

    messageBody = []

    def appendInfo (ip):
        messageBody.append ("  IP Address  : %s" % ip["ip"])
        messageBody.append ("  Info Source : %s" % ip["server"])

    messageBody.append ("The IP address of \"%s\" has changed:" % config.machine)
    messageBody.append ("")
    messageBody.append ("Old IP")
    appendInfo (oldip)
    messageBody.append ("New IP")
    appendInfo (newip)
    print ('\r\n'.join(messageBody))
    return
    smtpObj = None
    try:
        smtpObj = connect_smtp_server (server_domain  = config.smtp_host
                                      ,server_port    = config.smtp_port
                                      ,use_ssl        = config.smtp_use_ssl
                                      )
        send_plain_text_email (smtp_server   = smtpObj
                              ,from_addr     = nameAddrPair(config.sender, config.sender_email)
                              ,to_addrs      = to
                              ,email_subject = config.subject_line
                              ,email_content = '\r\n'.join(messageBody)
                              )
        messageBody = None
        to          = None
        print ("Successfully sent email")
    except:
        print ("ERROR: unable to send email")
    finally:
        if smtpObj is not None:
            try:
                smtpObj.quit()
            except:
                pass
            smtpObj = None


def doTheWork(config):
    #parse config file
    # config = ConfigInfo()
    # readconfig(config_path, config)

    #get the old ip address
    oldip = getoldip(config.save_ip_path)
    #print ("Old IP = %s" % oldip)

    #get current, external, IP address
    currip = getipAndSource(int(config.try_count), config.ip_blacklist)
    #print ("Curr IP = %s" % currip["ip"])

    #check to see if the IP address has changed
    if (currip["ip"] != oldip["ip"]):
        #send email
        print ("Current IP differs from old IP.")
        sendmail(oldip,  currip,  config)

        #update file
        updateoldip(config.save_ip_path,  currip)

    else:
        print ("Current IP = Old IP.  No need to send email.")

def runFromCLI():

    def checkFile (filePath):
        if os.path.isfile(filePath):
            return filePath
        else:
            raise FileNotFoundError(filePath)

    parser = argparse.ArgumentParser (description = 'IPWatch is a tool to check your current external IP address against a saved, previous, external IP address.'
                                     ,epilog      = 'It should be run as a scheduled task/cronjob periodically. If a difference in the new vs old IP address is found it will dispatch an email describing the change.'
                                     ,add_help    = True
                                     )
    parser.add_argument('filePath', type=checkFile, metavar='filePath', help=f"full path and filename to an IPWatch configuration file")
    parser.add_argument('--version','-v', action='version', version='%(prog)s v0.5')

    try:
        theArgs = parser.parse_args()
        config = ConfigInfo()
        readconfig(theArgs.filePath, config)
    except Exception as e:
        parser.error (str(e))
    
    print ("got to here")
    doTheWork (config)


if __name__ == '__main__':
    runFromCLI()
