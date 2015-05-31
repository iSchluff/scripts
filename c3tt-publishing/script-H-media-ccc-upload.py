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

#TODO This should go into main
def targetFromPropertie():
    global target_youtube
    global target_media

    logging.debug("encoding profile youtube flag: " + ticket['Publishing.YouTube.EnableProfile'] + " project youtube flag: " + ticket['Publishing.YouTube.Enable'])
    if ticket['Publishing.YouTube.EnableProfile'] == "yes" and ticket['Publishing.YouTube.Enable'] == "yes" and not has_youtube_url:
        logging.debug("publishing on youtube")
        target_youtube = True
        youtubeFromTicket()

    logging.debug("encoding profile media flag: " + ticket['Publishing.Media.EnableProfile'] + " project media flag: " + ticket['Publishing.Media.Enable'])
    if ticket['Publishing.Media.EnableProfile'] == "yes" and ticket['Publishing.Media.Enable'] == "yes":
        logging.debug("publishing on media")
        target_media = True
        mediaFromTicket()

def ticketFromTracker():
    """ Get a ticket from the tracker and prepare internal variables based on the ticket
    """
    logging.info("getting ticket from " + url)
    logging.info("=========================================")
    
    #check if we got a new ticket
    global ticket_id
    ticket_id = assignNextUnassignedForState(from_state, to_state, url, group, host, secret)
    if ticket_id != False:
        #copy ticket details to local variables
        logging.info("Ticket ID:" + str(ticket_id))
        global ticket
        ticket = getTicketProperties(str(ticket_id), url, group, host, secret)
        logging.debug("Ticket: " + str(ticket))
        global acronym
        global local_filename
        global local_filename_base
        global profile_extension
        global profile_slug
        global video_base
        global output
        global filename
        global guid
        global slug
        global title
        global subtitle 
        global description
        global download_base_url
        global folder
        
        #todo this shoul only be used if youtube propertie is set
        global has_youtube_url
        
        #TODO add here some try magic to catch missing properties
        guid = ticket['Fahrplan.GUID']
        slug = ticket['Fahrplan.Slug'] if 'Fahrplan.Slug' in ticket else str(ticket['Fahrplan.ID'])
        slug_c = slug.replace(":","_")    
        acronym = ticket['Project.Slug']
        filename = str(ticket['EncodingProfile.Basename']) + "." + str(ticket['EncodingProfile.Extension'])
        title = ticket['Fahrplan.Title']
        local_filename = str(ticket['Fahrplan.ID']) + "-" +ticket['EncodingProfile.Slug'] + "." + ticket['EncodingProfile.Extension']
        local_filename_base =  str(ticket['Fahrplan.ID']) + "-" + ticket['EncodingProfile.Slug']
        video_base = str(ticket['Publishing.Path'])
        output = str(ticket['Publishing.Path']) + "/"+ str(thumb_path)
        download_base_url =  str(ticket['Publishing.Base.Url'])
        profile_extension = ticket['EncodingProfile.Extension']
        profile_slug = ticket['EncodingProfile.Slug']
        
        #todo this shoul only be used if youtube propertie is set
        if 'YouTube.Url0' in ticket and ticket['YouTube.Url0'] != "":
                has_youtube_url = True
        else:
                has_youtube_url = False
        
        title = ticket['Fahrplan.Title']
        folder = ticket['EncodingProfile.MirrorFolder']
        
        if 'Fahrplan.Subtitle' in ticket:
                subtitle = ticket['Fahrplan.Subtitle']
        if 'Fahrplan.Abstract' in ticket:
                description = ticket['Fahrplan.Abstract']
                
        logging.debug("Data for media: guid: " + guid + " slug: " + slug_c + " acronym: " + acronym  + " filename: "+ filename + " title: " + title + " local_filename: " + local_filename + ' video_base: ' + video_base + ' output: ' + output)
        
        if not os.path.isfile(video_base + local_filename):
            cleanup("Source file does not exist (" + video_base + local_filename +")",-1)

        if not os.path.exists(output):
            cleanup("Output path does not exist ("+output+")",-1)
        
        if not os.access(output, os.W_OK):
            cleanup("Output path is not writable ("+output+")",-1)
    else:
        logging.warn("No ticket for this task, exiting")
        cleanup()

def mediaFromTicket():
    """ prepare the media.ccc.de API call from Ticket
    """
    
    logging.info("creating event on " + api_url)

    #create a event on media API
    #TODO master/slave ticket handling
    if profile_slug != "mp3" and profile_slug != "opus":        
        try:
            make_event(api_url, download_base_url, local_filename, local_filename_base, api_key, acronym, guid, video_base, output, slug, title, subtitle, description)
        except RuntimeError as err:
            cleanup("Creating event on media API failed, in case of audio releases make sure event exists: \n" + str(err), -1)
    
    #publish the media file on media API
    if not 'Publishing.Media.MimeType' in ticket:
        cleanup("No mime type set",-1)
    else:
        mime_type = ticket['Publishing.Media.MimeType']

    try:
        publish(local_filename, filename, api_url, download_base_url, api_key, guid, filesize, length, mime_type, folder, video_base)
    except RuntimeError as err:
        cleanup("Publishing on media API failed" + str(err),-1)
 
def youtubeFromTicket():
    """ prepare the youtube call to publish on youtube
    """
    try:
        youtubeUrls = publish_youtube(ticket, config['youtube']['client_id'], config['youtube']['secret'])
        props = {}
        for i, youtubeUrl in enumerate(youtubeUrls):
            props['YouTube.Url'+str(i)] = youtubeUrl

        setTicketProperties(ticket_id, props, url, group, host, secret)
    except RuntimeError as err:
        cleanup("Publishing to youtube failed: \n" + str(err),-1)

def cleanUp(msg=None,exit_code=None):
    """This should be called in case of an error / exception or at the end of all functions to bring the tracker 
    and twitter up to date. Arguments are optional an should only be set in error case.
    """
    
    if exit_code < 0: #something went wrong
        if ticket: #check if we already have a ticket id, if not we don't need to talk to the tracker
            if msg:
                setTicketFailed(ticket_id, "Publishing failed: \n" + str(msg), url, group, host, secret)
                logging.error(msg)
            else:
                setTicketFailed(ticket_id, "Publishing failed: \n" + " unknown reason", url, group, host, secret)
                logging.error(msg)
            sys.exit(exit_code)
    else:
        if ticket: #check if we already have a ticket id, if not we don't need to talk to the tracker 
            send_tweet(ticket, token, token_secret, consumer_key, consumer_secret)
            setTicketDone(ticket_id, url, group, host, secret)
            
    logging.info("cleanup down, exiting normal")
    sys.exit(0)

def main():
    """init and control flow a done here
    """
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
    
    logging.info("C3TT publishing")
    logging.debug("reading config")
    
    ### handle config
    #make sure we have a config file
    if not os.path.exists('client.conf'):
        logging.error("Error: config file not found")
        sys.exit(1)
        
    config = configparser.ConfigParser()
    config.read('client.conf')
    source = config['general']['source']
    dest = config['general']['dest']
    
    source = "c3tt" #TODO quickfix for strange parser behavior
    
    if source == "c3tt":
        ################### C3 Tracker ###################
        #project = "projectslug"
        group = config['C3Tracker']['group']
        secret =  config['C3Tracker']['secret']
    
        if config['C3Tracker']['host'] == "None":
                cleanUp('no tracker URL defined', -1)
        else:
            host = config['C3Tracker']['host']
    
        url = config['C3Tracker']['url']
        from_state = config['C3Tracker']['from_state']
        to_state = config['C3Tracker']['to_state']
        token = config['twitter']['token'] 
        token_secret = config['twitter']['token_secret']
        consumer_key = config['twitter']['consumer_key']
        consumer_secret = config['twitter']['consumer_secret']
    
    if True:
        ################### media.ccc.de #################
        #API informations
        api_url =  config['media.ccc.de']['api_url']
        api_key =  config['media.ccc.de']['api_key']
        
    #if we dont use the tracker we need to get the informations from the config
    #TODO add also target check for youtube only
    if source != 'c3tt':
        #################### conference information ######################
        rec_path = config['conference']['rec_path']
        image_path = config['conference']['image_path']
        webgen_loc = config['conference']['webgen_loc']
    
        ################### script environment ########################
        # base dir for video input files (local)
        video_base = config['env']['video_base']
        # base dir for video output files (local)
        output = config['env']['output']
    
    #path to the thumb export.
    #this is also used as postfix for the publishing dir
    if config['env']['thumb_path'] == None:
        thumb_path = 'thumbnails'
    else:
        thumb_path = config['env']['thumb_path']
    
    
    #internal vars
    ticket = None
    ticket_failed = True
    error_msg = None
    exit_code = 0 
    filesize = 0
    length = 0
    sftp = None
    ssh = None
    title = None
    frab_data = None
    acronyms = None
    guid = None
    filename = None
    debug = 0
    slug = None
    slug_c = None #slug without :
    rpc_client = None
    title = None
    subtitle = None 
    description = None
    profile_slug = None
    folder = None
    mime_type = None
    
    #TODO das sollte ne liste werden
    target_youtube = None
    target_media = None
    
    
    ticketFromTracker()()
    targetFromPropertie()

    # set ticket done
    logging.info("set ticket done")

if __name__ == "__main__": main()
