from __future__ import print_function
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import flask
from flask import render_template, jsonify, request
import httplib2
import sys
import json


from apiclient import discovery
from oauth2client import client
from bs4 import BeautifulSoup
import io
import re
import urllib2

app = flask.Flask(__name__)
MAIN_SITE = "http://www.goingout.co.il"
area_dict = {'TLV': '20', 'CENTER': '1', 'JER': '2','NORTH': '5','HAIFA': '6','SOUTH': '10'}
artists_list = []
selectedLocations = []
firstCall = True


@app.route('/callYouTube', methods=['GET', 'POST'])
def call_youtube():
    print('call youtube', file=sys.stderr)
    global firstCall
    global selectedLocations
    if firstCall:
        selectedLocations = request.form.getlist('check')
        firstCall = False
    if 'credentials' not in flask.session:
        return flask.redirect(flask.url_for('oauth2callback'))
    credentials = client.OAuth2Credentials.from_json(flask.session['credentials'])
    if credentials.access_token_expired:
        return flask.redirect(flask.url_for('oauth2callback'))
    else:
        http_auth = credentials.authorize(httplib2.Http())
        youtube_service = discovery.build('youtube', 'v3', http_auth)
        channels_list_response = youtube_service.channels().list(part="contentDetails", mine=True).execute()
        for channel in channels_list_response["items"]:
            likesId = channel["contentDetails"]["relatedPlaylists"]["likes"]
        playlistitems_list_request = youtube_service.playlistItems().list(
            playlistId=likesId,
            part="snippet",
            maxResults=50
        )

        playlistitems_list_response = playlistitems_list_request.execute()

        # extract artist name from each liked video
        for playlist_item in playlistitems_list_response["items"]:
            title = playlist_item["snippet"]["title"].split("-")

            if len(title) >= 2:
                artist = title[0].strip()
                artists_list.append(artist)
        resEvents = searchEvents(selectedLocations, artists_list)
        return render_template('Calendar.html', resultEvents=resEvents)



@app.route('/oauth2callback')
def oauth2callback():
    print('oauth2callback', file=sys.stderr)
    flow = client.flow_from_clientsecrets(
        'client_secret.json',
        # scope='https://www.googleapis.com/auth/youtubepartner-channel-audit',
        scope='https://www.googleapis.com/auth/youtube.readonly',
        redirect_uri=flask.url_for('oauth2callback', _external=True))
    if 'code' not in flask.request.args:
        auth_uri = flow.step1_get_authorize_url()
        return flask.redirect(auth_uri)
    else:
        auth_code = flask.request.args.get('code')
        credentials = flow.step2_exchange(auth_code)
        flask.session['credentials'] = credentials.to_json()
        return flask.redirect(flask.url_for('call_youtube'))


def get_events(html):
    """
    :param html: string representation of html page
    :return: Returns list of dictionaries containing host metadata
    """

    print('get events', file=sys.stderr)
    soup = BeautifulSoup(html, 'html.parser')
    # print soup
    tr_events = soup.findAll("tr", {"itemtype": "http://schema.org/MusicEvent"})
    events = []

    for event in tr_events:

        tr_event = {}
        # tr_soup = BeautifulSoup(event, 'html.parser')
        td_event_date = event.findAll("td",{"class":"with_border nowrap"})
        # for td in td_event:
        for t in td_event_date[0].findAll("time",{"itemprop":"startDate"}):
            if t.has_attr('datetime'):
                tr_event['datetime'] = t['datetime']
                # print tr_event['datetime']
        td_desc = event.findAll("td")
        tr_event['link'] = MAIN_SITE + td_desc[0].findAll("a")[0]['href']
        # print tr_event['link']
        tr_event['artist'] = td_desc[1].find("a").find("b").text.strip()
        # print tr_event['artist']
        # print td_desc[1].find("a").find("span")
        if td_desc[1].find("a").find("span"):
            tr_event['description'] = td_desc[1].find("a").find("span").text.strip()
        else:
            tr_event['description'] = ''
        # print tr_event['description']
        tr_event['area'] = td_desc[3].find("b").text.strip()
        # print tr_event['area']
        tr_event['location'] = td_desc[3].find("span").text.strip()
        # print tr_event['location']
        events.append(tr_event)
    return events


def searchEvents(areas, artists):
    print('serach events', file=sys.stderr)
    # areas - list of areas -
    # TLV --> 20
    # http://www.goingout.co.il/search_results.php?dates=month&region=20&p=1#search&dates=month&date=13/02/2017&to=13/03/2017&region=20&p=1
    # CENTER --> 1
    # http://www.goingout.co.il/search_results.php?dates=month&region=20&p=1#search&dates=month&date=13/02/2017&to=13/03/2017&region=1&p=1
    # JER --> 2
    # http://www.goingout.co.il/search_results.php?dates=month&region=20&p=1#search&dates=month&date=13/02/2017&to=13/03/2017&region=2&p=1
    # NORTH --> 5
    # http://www.goingout.co.il/search_results.php?dates=month&region=20&p=1#search&dates=month&date=13/02/2017&to=13/03/2017&region=5&p=1
    # HAIFA --> 6
    # http://www.goingout.co.il/search_results.php?dates=month&region=20&p=1#search&dates=month&date=13/02/2017&to=13/03/2017&region=6&p=1
    # SOUTH --> 10
    # http://www.goingout.co.il/search_results.php?dates=month&region=20&p=1#search&dates=month&date=13/02/2017&to=13/03/2017&region=10&p=1
    # TODO: build case
    # artist - list of artists

    def div_pages(href):
        # print('div pages', file=sys.stderr)
        return href and re.compile("pages").search(href)
    content = []
    for area in areas:
        area = area.decode('utf-8')
        "http: // www.goingout.co.il / search_results.php?dates = month & region = 2 & p = 1  # search&dates=month&region=2&p=1"
        CONCERT_LIST = "http://www.goingout.co.il/search_results.php?dates=month&region="+area_dict[area]+"&p=1#search&dates=month&region=" + area_dict[area] + "&p=1"
        # "http://www.goingout.co.il/search_results.php?free_text=&type=&dates=month&region=20&price=&text=&divider=date&sort=date&favs=0&p=1&archive=0&ajax=0&date=&to=#search&dates=month&region=2&p=1
        # CONCERT_LIST_NO_PAGE_P1 = "http://www.goingout.co.il/search_results.php?free_text=&type=&dates=month&region=20&price" \
        #                           "=&text=&divider=date&sort=date&favs=0&p="
        CONCERT_LIST_NO_PAGE_P1 = "http://www.goingout.co.il/search_results.php?dates=month&region="+area_dict[area]+"&p="
        CONCERT_LIST_NO_PAGE_P2 = "#search&dates=month&region=" + area_dict[area] + "&p="
        # CONCERT_LIST_NO_PAGE_P2 = "& archive = 0 & ajax = 0 & date = & to =  # search&dates=month&region=" + area_dict[area] + "&p="
        html_page = urllib2.urlopen(CONCERT_LIST)
        mainSoup = BeautifulSoup(html_page, "html.parser", from_encoding="utf-8")
        pages = mainSoup.find_all(id=div_pages)
        p = mainSoup.find(id=div_pages).text.split()
        p = p[:len(p) - 2]
        last_page = max(p)
        print (area_dict[area], last_page)
        for i in range(1, int(last_page)):
            html_page = urllib2.urlopen(CONCERT_LIST_NO_PAGE_P1 + str(i) + CONCERT_LIST_NO_PAGE_P2 + str(i))
            content.extend(get_events(html_page))
        # print json.dumps(events, indent=4)
        # print content
        # with io.open('events.json', 'w', encoding='utf8') as jsonFile:
    match_events = []
    for event in content:
        for artist in artists:
            artist_utf = artist.decode('utf-8')
            # if artist.lower() in event['artist'].lower() or artist.lower() in event['description'].lower():
            if artist_utf in event['artist'] or artist_utf in event['description']:
                match_events.append(event)

    # events_dumped = json.dumps(match_events, indent=4, ensure_ascii=False)
    events_dumped = json.dumps(match_events, ensure_ascii=False)
    if events_dumped:
        print(type(events_dumped))
        return events_dumped
        # return match_events
        # return unicode(events_dumped)
    return '{}'

@app.route("/")
def index():
    """
    uploads the sign in page
    :return: GoogleSignIn.html
    """
    print('Index function', file=sys.stderr)
    return render_template('FirstPage.html')

if __name__ == '__main__':
    import uuid
    app.secret_key = str(uuid.uuid4())
    app.debug = False
    app.run('127.0.0.1', 8888)







