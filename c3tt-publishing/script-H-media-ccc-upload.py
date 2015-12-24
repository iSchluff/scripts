#!/usr/bin/python3
#    Copyright (C) 2015  derpeter
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
    
import argparse
import sys
import os
import urllib.request, urllib.parse, urllib.error
import requests
import subprocess
import xmlrpc.client
import socket
import xml.etree.ElementTree as ET
import json
import configparser
import paramiko
import inspect
import logging

from c3t_rpc_client import * 
from media_ccc_de_api_client import *
from auphonic_client import *
from youtube_client import *
from twitter_client import *
from pyasn1_modules.rfc4210 import ErrorMsgContent

ticket = None;
def ticketFromTracker():
    """ Get a ticket from the tracker and prepare internal variables based on the ticket
    """
    logging.info("getting ticket from " + url)
    logging.info("=========================================")
    
    #check if we got a new ticket
    global ticket_id
    global host
    if host == None:
        host = socket.getfqdn()
    ticket_id = assignNextUnassignedForState(from_state, to_state, url, group, host, secret)
    if ticket_id != False:
        logging.info("Ticket ID:" + str(ticket_id))
        
        global ticket
        ticket = getTicketProperties(str(ticket_id), url, group, host, secret)
        logging.debug("Ticket: " + str(ticket))
        slug = ticket['Fahrplan.Slug'] if 'Fahrplan.Slug' in ticket else str(ticket['Fahrplan.ID'])
        slug_c = slug.replace(":","_")
        local_filename = str(ticket['Fahrplan.ID']) + "-" +ticket['EncodingProfile.Slug'] + "." + ticket['EncodingProfile.Extension']
        video_base = str(ticket['Publishing.Path'])
        output = str(ticket['Publishing.Path']) + "/"+ str(config['C3Tracker']['thumb_path'])

        #title = ticket['Fahrplan.Title']
        #folder = ticket['EncodingProfile.MirrorFolder']
        #guid = ticket['Fahrplan.GUID']  
        #acronym = ticket['Project.Slug']
        #filename = str(ticket['EncodingProfile.Basename']) + "." + str(ticket['EncodingProfile.Extension'])
        #title = ticket['Fahrplan.Title']
        #local_filename_base =  str(ticket['Fahrplan.ID']) + "-" + ticket['EncodingProfile.Slug']
        #download_base_url =  str(ticket['Publishing.Base.Url'])
        #profile_extension = ticket['EncodingProfile.Extension']
        #profile_slug = ticket['EncodingProfile.Slug']
        
        #TODO this should only be used if youtube propertie is set
        if 'YouTube.Url0' in ticket and ticket['YouTube.Url0'] != "":
                has_youtube_url = True
        else:
                has_youtube_url = False
               
#         if 'Fahrplan.Subtitle' in ticket:
#                 subtitle = ticket['Fahrplan.Subtitle']
#         if 'Fahrplan.Abstract' in ticket:
#                 description = ticket['Fahrplan.Abstract']
#                 
        #logging.debug("Data for media: guid: " + ticket['Fahrplan.GUID'] + " slug: " + slug_c + " acronym: " + ticket['Project.Slug']  + " filename: "+ filename + " title: " + title + " local_filename: " + local_filename + ' video_base: ' + video_base + ' output: ' + output)
        
        if not os.path.isfile(video_base + local_filename):
            cleanUp("Source file does not exist (" + video_base + local_filename +")",-1)

        if not os.path.exists(output):
            cleanUp("Output path does not exist ("+output+")",-1)
        
        if not os.access(output, os.W_OK):
            cleanUp("Output path is not writable ("+output+")",-1)
    
    else:
        logging.info("No ticket for this task, exiting")
        cleanUp()

def mediaFromTicket(ticket):
    """ prepare the media.ccc.de API call from Ticket
    """

    #create a event on media API
    #TODO master/slave ticket handling
    if ticket['EncodingProfile.Slug'] != "mp3" and ticket['EncodingProfile.Slug'] != "opus":
        logging.info("creating event on " + config['media.ccc.de']['api_url'])        
        try:
            make_event(ticket, config['media.ccc.de']['api_url'], config['media.ccc.de']['api_key'])
        except RuntimeError as err:
            cleanUp("Creating event on media API failed, in case of audio releases make sure event exists: \n" + str(err), -1)
    
    if 'Publishing.Media.MimeType' in ticket:
        mime_type = ticket['Publishing.Media.MimeType']
    else:
        cleanUp("No mime type set", -1)
        
    #publish the media file on media API
    logging.info("publishing recording on " + config['media.ccc.de']['api_url'])
    try:
        publish(ticket, config['media.ccc.de']['api_url'], config['media.ccc.de']['api_key'])
    except RuntimeError as err:
        cleanUp("Publishing on media API failed" + str(err),-1)
 
def youtubeFromTicket(ticket):
    """ prepare the youtube call to publish on youtube
    """
    
    logging.info("publishing recording on youtube")
    try:
        youtubeUrls = publish_youtube(ticket, config['youtube']['client_id'], config['youtube']['secret'])
        props = {}
        for i, youtubeUrl in enumerate(youtubeUrls):
            props['YouTube.Url'+str(i)] = youtubeUrl
        if config['general']['source'] == 'c3tt':
            setTicketProperties(ticket_id, props, url, group, host, secret)
    except RuntimeError as err:
        cleanUp("Publishing to youtube failed: \n" + str(err),-1)

def cleanUp(msg=None,exit_code=0):
    """This should be called in case of an error / exception or at the end of all functions to bring the tracker 
    and twitter up to date. Arguments are optional an should only be set in error case.
    """
    
    if exit_code < 0: #something went wrong
        if ticket: #check if we already have a ticket id, if not we don't need to talk to the tracker
            if msg: #check if we have a error message 
                setTicketFailed(ticket_id, "Publishing failed: \n" + str(msg), url, group, host, secret)
                logging.error(msg)
            else:
                setTicketFailed(ticket_id, "Publishing failed: \n" + " unknown reason", url, group, host, secret)
                logging.error(msg)
            sys.exit(exit_code)
    else: #either publishing succeeded or the tracker has no job for us
        if ticket: #check if we already have a ticket id, if not we don't need to talk to the tracker 
            send_tweet(ticket, config['twitter']['token'] , config['twitter']['token_secret'], config['twitter']['consumer_key'], config['twitter']['consumer_secret'])
            setTicketDone(ticket_id, url, group, host, secret)
            
    logging.info("cleanUp down, exiting normal")
    sys.exit(0)

def main():
    """init and control flow a done here
    """
    ### setup logging
    global logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    logging.addLevelName( logging.WARNING, "\033[1;33m%s\033[1;0m" % logging.getLevelName(logging.WARNING))
    logging.addLevelName( logging.ERROR, "\033[1;41m%s\033[1;0m" % logging.getLevelName(logging.ERROR))
    logging.addLevelName( logging.INFO, "\033[1;32m%s\033[1;0m" % logging.getLevelName(logging.INFO))
    logging.addLevelName( logging.DEBUG, "\033[1;85m%s\033[1;0m" % logging.getLevelName(logging.DEBUG))
    
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    logger.info("C3TT publishing")
    logger.debug("reading config")
    
    ### handle config
    #make sure we have a config file
    if not os.path.exists('client.conf'):
        cleanUp("Error: config file not found", -1)
    
    global config
    config = configparser.ConfigParser()
    config.read('client.conf')
    source = config['general']['source']
    dest = config['general']['dest']
    
    if source == 'c3tt': # The c3tt is the source, init tracker related variables
        global group
        if config['C3Tracker']['group']:
            group = config['C3Tracker']['group']
        else:
            cleanUp("tracker group is missing", -1)
        
        global secret
        if config['C3Tracker']['secret']:
            secret = config['C3Tracker']['secret']
        else:
            cleanUp("tracker secret is missing", -1)
        
        global host
        if config['C3Tracker']['host']:
            host = config['C3Tracker']['host']
        else:
            host = socket.getfqdn()
            logging.debug("no hostname defined, using localhosts fqdn")
            
        global url    
        if config['C3Tracker']['url']:
            url = config['C3Tracker']['url']
        else:
            cleanUp("tracker url is missing", -1)
        
        global from_state
        if config['C3Tracker']['from_state']:
            from_state = config['C3Tracker']['from_state']
        else:
            cleanUp("from_state is missing",-1)
        
        global to_state
        if config['C3Tracker']['to_state']:
            to_state = config['C3Tracker']['to_state']
        else:
            cleanUp("to_state is missing", -1)
        

        
    #if we don't use the tracker we need to get the informations from the config
    ## TODO make this usefull currently only c3tt is supported
    if source != 'c3tt':
        cleanUp("only c3tt is currently supported as source", -1)
#         #################### conference information ######################
#         rec_path = config['conference']['rec_path']
#         image_path = config['conference']['image_path']
#         webgen_loc = config['conference']['webgen_loc']
#     
#         ################### script environment ########################
#         # base dir for video input files (local)
#         video_base = config['env']['video_base']
#         # base dir for video output files (local)
#         output = config['env']['output']
            # try to get a ticket from tracker
    try:
        ticketFromTracker()
    except Exception as e:
            #cleanUp(e.msg, -1)
            #cleanUp(ticket,"exception caught", -1)
        print("exception happend during ticketFromTracker\n"+str(e))
        sys.exit()
    
    ##### AT THIS POINT THE TICKET NEEDS TO BE FILLD WITH ALL PROPERTIES !!!1!11 #######

    if ticket['Publishing.Media.EnableProfile'] == "yes" and ticket['Publishing.Media.Enable'] == "yes":
        logging.info("publishing on media")
        try:
            logging.debug("encoding profile media flag: " + ticket['Publishing.Media.EnableProfile'] + " project media flag: " + ticket['Publishing.Media.Enable'])
            mediaFromTicket()
        except Exception as e:
            #cleanUp(e.msg, -1)
            cleanUp("exception",-1)
    
    if ticket['Publishing.YouTube.EnableProfile'] == "yes" and ticket['Publishing.YouTube.Enable'] == "yes" and not has_youtube_url:
        logging.info("publishing on youtube")
        try:
            logging.debug("encoding profile youtube flag: " + ticket['Publishing.YouTube.EnableProfile'] + " project youtube flag: " + ticket['Publishing.YouTube.Enable'])
            youtubeFromTicket()
        except Exception as e:
            #cleanUp(e.msg, -1)
            cleanUp("exception",-1)
  
    if ticket['Publishing.Twitter.Enable'] ==  "yes":
        logging.info("tweeting on twitter")
        try:
            logging.debug("encoding profile twitter flag: " + ticket['Publishing.Twitter.EnableProfile'] + " project twitter flag: " + ticket['Publishing.Twitter.Enable'])
            send_tweet(ticket, config['twitter']['token'] , config['twitter']['token_secret'], config['twitter']['consumer_key'], config['twitter']['consumer_secret'])
        except Exception as e:
            #cleanUp(e.msg, -1)
            cleanUp("exception",-1)
        
    cleanUp()

if __name__ == "__main__": main()
