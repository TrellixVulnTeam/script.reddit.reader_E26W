# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import sys
import urllib.request, urllib.error, urllib.parse, urllib.request, urllib.parse, urllib.error
import re
import os

from default import addon, subredditsFile, urlMain, itemsPerPage,subredditsPickle,REQUEST_TIMEOUT
from . utils import log, translation,xbmc_notify,clean_str
from default import reddit_clientID, reddit_userAgent, reddit_redirect_uri


reddit_refresh_token =addon.getSetting("reddit_refresh_token")
reddit_access_token  =addon.getSetting("reddit_access_token") #1hour token

def reddit_request( url, data=None ):
    #if there is a refresh_token, we use oauth.reddit.com instead of www.reddit.com
    if reddit_refresh_token:
        url=url.replace('www.reddit.com','oauth.reddit.com' )
        url=url.replace( 'np.reddit.com','oauth.reddit.com' )
        url=url.replace(       'http://',        'https://' )
        #log( "  replaced reqst." + url + " + access token=" + reddit_access_token)
    req = urllib.request.Request(url)

    #req.add_header('User-Agent', 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-GB; rv:1.8.1.14) Gecko/20080404 Firefox/2.0.0.14')
    req.add_header('User-Agent', reddit_userAgent)   #userAgent = "XBMC:"+addonID+":v"+addon.getAddonInfo('version')+" (by /u/gsonide)"
    log( "user agent is " + reddit_userAgent )

    #if there is a refresh_token, add the access token to the header
    if reddit_refresh_token:
        req.add_header('Authorization','bearer '+ reddit_access_token )

    try:
        #log("    requesting from %s" %(url)  )
        page = urllib.request.urlopen(req,data=data, timeout=20)
        response=page.read();page.close()
        return response

    except urllib.error.HTTPError as err:
        if err.code in [403,401]:  #401 Unauthorized, 403 forbidden. access tokens expire in 1 hour. maybe we just need to refresh it
            log("    attempting to get new access token")
            if reddit_get_access_token():
                log("      Success: new access token "+ reddit_access_token)
                req.add_header('Authorization','bearer '+ reddit_access_token )
                try:
                    log("      2nd attempt:"+ url)
                    page = urllib.request.urlopen(req)   #it has to be https:// not http://
                    response=page.read();page.close()
                    return response

                except urllib.error.HTTPError as err:
                    xbmc.executebuiltin('XBMC.Notification("%s %s", "%s" )' %( err.code, err.msg, url)  )
                    log( err.reason )
                except urllib.error.URLError as err:
                    log( err.reason )
            else:
                log( "*** failed to get new access token - don't know what to do " )

        xbmc_notify("%s %s" %( err.code, err.msg), url)
    except urllib.error.URLError as err: # Not an HTTP-specific error (e.g. connection refused)
        xbmc_notify(err.reason, url)
    except :
        pass

def reddit_get_refresh_token(url, name, type_):
    #this function gets a refresh_token from reddit and keep it in our addon. this refresh_token is used to get 1-hour access tokens.
    #  getting a refresh_token is a one-time step

    #1st: use any webbrowser to
    #  https://www.reddit.com/api/v1/authorize?client_id=hXEx62LGqxLj8w&response_type=code&state=RS&redirect_uri=http://localhost:8090/&duration=permanent&scope=read,mysubreddits
    #2nd: click allow and copy the code provided after reddit redirects the user
    #  save this code in add-on settings.  A one-time use code that may be exchanged for a bearer token.
    code = addon.getSetting("reddit_code")
    #log("  user refresh token:"+reddit_refresh_token)
    #log("  user          code:"+code)

    if reddit_refresh_token and code:
        #log("  user already have refresh token:"+reddit_refresh_token)
        dialog = xbmcgui.Dialog()
        if dialog.yesno(translation(32411), translation(32412), translation(32413), translation(32414) ):
            pass
        else:
            return

    try:
        log( "Requesting a reddit permanent token with code=" + code )

        req = urllib.request.Request('https://www.reddit.com/api/v1/access_token')

        #http://stackoverflow.com/questions/6348499/making-a-post-call-instead-of-get-using-urllib2
        data = urllib.parse.urlencode({'grant_type'  : 'authorization_code'
                                ,'code'        : code                     #'woX9CDSuw7XBg1MiDUnTXXQd0e4'
                                ,'redirect_uri': reddit_redirect_uri}).encode("utf-8")    #http://localhost:8090/

        #http://stackoverflow.com/questions/2407126/python-urllib2-basic-auth-problem
        bytes_like_object = bytes('%s:%s' % (reddit_clientID, ''), "utf-8")
        import codecs
        base64string=codecs.encode(bytes_like_object, 'base64') #base64string is now a bytes-like object
        base64string=str(base64string,'utf-8').replace('\n', '')

        req.add_header('Authorization',"Basic %s" % base64string)
        req.add_header('User-Agent', reddit_userAgent)

        log( req.headers )
        page = urllib.request.urlopen(req, data=data)
        response=page.read();page.close()
        log( response )

        status=reddit_set_addon_setting_from_response(response)

        if status=='ok':
            xbmc_notify( 'Success', "Click 'OK' when done" )
        else:
            xbmc_notify( "Error", status )


#    This is a 2nd option reddit oauth. user needs to request access token every hour
#         #user enters this on their webbrowser. note that there is no duration=permanent response_type=token instead of code
#         request_url='https://www.reddit.com/api/v1/authorize?client_id=hXEx62LGqxLj8w&response_type=token&state=RS&redirect_uri=http://localhost:8090/&scope=read,identity'
#         #click on "Allow"
#         #copy the redirect url code    #enters it on settings. e.g.: LVQu8vitbEXfMPcK1sGlVVQZEpM
#
#         #u='https://oauth.reddit.com/new.json'
#         u='https://oauth.reddit.com//api/v1/me.json'
#
#         req = urllib2.Request(u)
#         #req.add_header('User-Agent', 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-GB; rv:1.8.1.14) Gecko/20080404 Firefox/2.0.0.14')
#         req.add_header('User-Agent', reddit_userAgent)
#         req.add_header('Authorization','bearer LVQu8vitbEXfMPcK1sGlVVQZEpM')
#         page = read,identity.urlopen(req)
#         response=page.read();page.close()

    except urllib.error.HTTPError as err:
        xbmc_notify(err.code, err.msg)
    except urllib.error.URLError as err: # Not an HTTP-specific error (e.g. connection refused)
        xbmc_notify('get_refresh_token',err.reason)

def reddit_get_access_token(url="", name="", type_=""):
    try:
        log( "  Requesting a reddit 1-hour token" )
        req = urllib.request.Request('https://www.reddit.com/api/v1/access_token')

        #http://stackoverflow.com/questions/6348499/making-a-post-call-instead-of-get-using-urllib2
        data = urllib.parse.urlencode({'grant_type'    : 'refresh_token'
                                ,'refresh_token' : reddit_refresh_token }).encode("utf-8")

        #http://stackoverflow.com/questions/2407126/python-urllib2-basic-auth-problem
        #import base64
        bytes_like_object = bytes('%s:%s' % (reddit_clientID, ''), "utf-8")
        #base64string = base64.b64encode(bytes('%s:%s' % (reddit_clientID, ''), "utf-8")).replace('\n', '')

        #alternate method. couldn't get the above to work.
        import codecs
        base64string=codecs.encode(bytes_like_object, 'base64') #base64string is now a bytes-like object
        #base64string=base64string.encode('ascii')

        #log( base64string )
        #all strings in python3 are utf-8. 
        #convert the bytes object to utf-8 so that we can use the replace function and then put it back. 
        base64string=str(base64string,'utf-8').replace('\n', '')
        #log( base64string )
        req.add_header('Authorization',"Basic %s" % base64string)
        req.add_header('User-Agent', reddit_userAgent)

        #log( req.headers )


        page = urllib.request.urlopen(req, data=data)
        response=page.read();page.close()

        status=reddit_set_addon_setting_from_response(response)

        if status=='ok':
            return True
        else:
            xbmc_notify( "Requesting 1-hour token", status)

    except urllib.error.HTTPError as err:
        xbmc_notify(err.code, err.msg, 5000)
    except urllib.error.URLError as err: # Not an HTTP-specific error (e.g. connection refused)
        xbmc_notify('get_access_token',err.reason)

    return False

def reddit_set_addon_setting_from_response(response):
    import time, json
    from . utils import convert_date
    global reddit_access_token    #specify "global" if you want to change the value of a global variable
    global reddit_refresh_token
    try:
        #log( response )
        #response is a bytes-like object. Convert it to string so that we can use the replace() 
        response=str(response,'utf-8').replace('\\"', '\'')

        #python3 Object of type bytes is not JSON serializable
        response = json.loads(response)
        log( json.dumps(response, indent=4) )

        if 'error' in response:
            #Error                      Cause                                                                Resolution
            #401 response               Client credentials sent as HTTP Basic Authorization were invalid     Verify that you are properly sending HTTP Basic Authorization headers and that your credentials are correct
            #unsupported_grant_type     grant_type parameter was invalid or Http Content type was not set correctly     Verify that the grant_type sent is supported and make sure the content type of the http message is set to application/x-www-form-urlencoded
            #NO_TEXT for field code     You didn't include the code parameter                                Include the code parameter in the POST data
            #invalid_grant              The code has expired or already been used                            Ensure that you are not attempting to re-use old codes - they are one time use.
            return response['error']
        else:
            if 'refresh_token' in response:  #refresh_token only returned when getting reddit_get_refresh_token. it is a one-time step
                reddit_refresh_token = response['refresh_token']
                addon.setSetting('reddit_refresh_token', reddit_refresh_token)

            reddit_access_token = response['access_token']
            addon.setSetting('reddit_access_token', reddit_access_token)
            #log( '    new access token '+ reddit_access_token )

            addon.setSetting('reddit_access_token_scope', response['scope'])

            unix_time_now = int(time.time())
            unix_time_now += int( response['expires_in'] )
            addon.setSetting('reddit_access_token_expires', convert_date(unix_time_now))

    except Exception as e:
        log("  parsing reddit token response EXCEPTION:="+ str( sys.exc_info()[0]) + "  " + str(e) )
        return str(e)

    return "ok"

def reddit_revoke_refresh_token(url, name, type_):
    global reddit_access_token    #specify "global" if you wanto to change the value of a global variable
    global reddit_refresh_token
    try:
        log( "Revoking refresh token " )

        req = urllib.request.Request('https://www.reddit.com/api/v1/revoke_token')

        data = urllib.parse.urlencode({'token'          : reddit_refresh_token
                          ,'token_type_hint': 'refresh_token'       }).encode("utf-8")

        bytes_like_object = bytes('%s:%s' % (reddit_clientID, ''), "utf-8")
        import codecs
        base64string=codecs.encode(bytes_like_object, 'base64') #base64string is now a bytes-like object
        base64string=str(base64string,'utf-8').replace('\n', '')

        req.add_header('Authorization',"Basic %s" % base64string)
        req.add_header('User-Agent', reddit_userAgent)

        page = urllib.request.urlopen(req, data=data)
        response=page.read();page.close()

        #no response for success.
        log( response )

        #response = json.loads(response.replace('\\"', '\''))
        #log( json.dumps(response, indent=4) )

        addon.setSetting('reddit_refresh_token', "")
        addon.setSetting('reddit_access_token', "")
        addon.setSetting('reddit_access_token_scope', "")
        addon.setSetting('reddit_access_token_expires', "")
        reddit_refresh_token=""
        reddit_access_token=""

        xbmc_notify( 'Token revoked', '')

    except urllib.error.HTTPError as err:
        xbmc_notify(err.code, err.msg)
    #except Exception as e:
    except urllib.error.URLError as err:
        xbmc_notify('Revoking refresh token', err.msg)

def reddit_save(api_method, post_id, type_):
    #api_method either /api/save/  or /api/unsave/
    url=urlMain+api_method
    data = urllib.parse.urlencode({'id'  : post_id })

    response=reddit_request( url,data )
    log(repr(response))
    if response=='{}':
        xbmc_notify(api_method, 'Success')
        if api_method=='/api/unsave/':
            xbmc.executebuiltin('XBMC.Container.Refresh')
    else:
        xbmc_notify(api_method, response)

def create_default_subreddits():
    #create a default file and sites
    with open(subredditsFile, 'a') as fh:

        fh.write('/user/gummywormsyum/m/videoswithsubstance[videos with substance]\n')
        fh.write('/user/sallyyy19/m/video[%s]\n' %(translation(32006)))  # user   http://forum.kodi.tv/member.php?action=profile&uid=134499
        fh.write('Documentaries+ArtisanVideos+lectures+LearnUselessTalents\n')
        fh.write('Stop_Motion+FrameByFrame+Brickfilms+Animation\n')
        #fh.write('randnsfw\n')
        fh.write('animemusic+amv+animetrailers\n')
        fh.write('popular\n')
        fh.write('mealtimevideos/new\n')
        fh.write('music+listentothis+musicvideos\n')
        fh.write('moviemusic+soundtracks+gamemusic\n')
        fh.write('fantrailers+fanedits+gametrailers+trailers\n')
        fh.write('gamereviews+moviecritic\n')
        fh.write('site:youtube.com\n')
        fh.write('videos\n')
        fh.write('woahdude+interestingasfuck+shittyrobots\n')

def populate_subreddits_pickle():
    from .guis import progressBG
    loading_indicator=progressBG(translation(32023))   #Gathering icons..

    with open(subredditsFile, 'r') as fh:
        subreddit_settings = fh.readlines()

    #xbmc_notify("initializing", "Building icons cache", 5000)
    loading_indicator.set_tick_total(len(subreddit_settings))
    for entry in subreddit_settings:
        entry=entry.strip()
        loading_indicator.tick(1,entry)
        s=convert_settings_entry_into_subreddits_list_or_domain(entry)
        if s:
            #t = threading.Thread(target=get_subreddit_entry_info_thread, args=(s,) )
            log('processing saved entry:'+repr(entry))
            get_subreddit_entry_info_thread(s)

    xbmc.sleep(2000)
    loading_indicator.end()

def format_multihub(multihub):
#properly format a multihub string
#make sure input is a valid multihub
    t = multihub
    #t='User/sallyyy19/M/video'
    ls = t.split('/')

    for idx, word in enumerate(ls):
        if word.lower()=='user':ls[idx]='user'
        if word.lower()=='m'   :ls[idx]='m'
    #xbmc.log ("/".join(ls))
    return "/".join(ls)

def this_is_a_multireddit(subreddit):
    #subreddits and multihub are stored in the same file
    #i think we can get away with just testing for user/ to determine multihub
    subreddit=subreddit.lower()
    return subreddit.startswith(('user/','/user/')) #user can enter multihub with or without the / in the beginning

def this_is_a_user_saved_list(subreddit):
    #user saved list looks like this "https://www.reddit.com/user/XXXXXXX/saved"  and saved as "/user/XXXXXXX/saved"  in out subreddits file
    subreddit=subreddit.lower()
    return (subreddit.startswith(('user/','/user/')) and subreddit.endswith('/saved') )

def parse_subreddit_entry(subreddit_entry_from_file):
    #returns subreddit, [alias] and description. also populates WINDOW mailbox for custom view id of subreddit
    #  description= a friendly description of the 'subreddit shortcut' on the first page of addon
    #    used for skins that display them

    subreddit, alias, viewid = subreddit_alias( subreddit_entry_from_file )

    entry_type='subreddit'

    description=subreddit
    #check for domain filter
    a=[':','/domain/']
    if any(x in subreddit for x in a):  #search for ':' or '/domain/'
        entry_type='domain'
        #log("domain "+ subreddit)
        domain=re.findall(r'(?::|\/domain\/)(.+)',subreddit)[0]
        description=translation(32008) + domain            #"Show posts from"

    #describe combined subreddits
    if '+' in subreddit:
        entry_type='combined'
        description=subreddit.replace('+','[CR]')

    #describe multireddit or multihub
    if this_is_a_multireddit(subreddit):
        entry_type='multireddit'
        description=translation(32007)  #"Custom Multireddit"

    if subreddit.startswith('?'):
        entry_type='search'
        description=translation(32016)  #"Custom Search"
    #save that view id in our global mailbox (retrieved by listSubReddit)
    #WINDOW.setProperty('viewid-'+subreddit, viewid)

    if subreddit.startswith('https://'):
        entry_type='link'
        description=translation(32027)  #"Saved Link"

    return entry_type, subreddit, alias, description

def ret_settings_type_default_icon(entry_type):
    icon="type_unsupp.png"
    if entry_type=='subreddit':
        icon="icon_generic_subreddit.png"
    elif entry_type=='domain':
        icon="icon_domain.png"
    elif entry_type=='combined':
        icon="icon_multireddit.png"
    elif entry_type=='multireddit':
        icon="icon_multireddit.png"
    elif entry_type=='search':
        icon="icon_search_subreddit.png"

    return icon

def subreddit_alias( subreddit_entry_from_file ):
    #users can specify an alias for the subredit and it is stored in the file as a regular string  e.g. diy[do it yourself]
    #this function returns the subreddit without the alias identifier and alias if any or alias=subreddit if none
    ## in addition, users can specify custom viewID for a subreddit by encapsulating the viewid in ()'s

    a=re.compile(r"(\[[^\]]*\])") #this regex only catches the []
    #a=re.compile(r"(\[[^\]]*\])?(\(\d+\))?") #this regex catches the [] and ()'s
    alias=""
    viewid=""
    #return the subreddit without the alias. but (viewid), if present, is still there
    subreddit = a.sub("",subreddit_entry_from_file).strip()
    #log( "  re:" +  subreddit )

    #get the viewID
    try:viewid= subreddit[subreddit.index("(") + 1:subreddit.rindex(")")]
    except (ValueError,TypeError):viewid=""
    #log( "viewID=%s for r/%s" %( viewid, subreddit ) )

    if viewid:
        #remove the (viewID) string from subreddit
        subreddit=subreddit.replace( "(%s)"%viewid, "" )

    #get the [alias]
    a= a.findall(subreddit_entry_from_file)
    if a:
        alias=a[0]
        #log( "      alias:" + alias )
    else:
        alias = subreddit

    return subreddit, alias, viewid

def assemble_reddit_filter_string(search_string, subreddit, skip_site_filters="", domain="" ):
    #skip_site_filters -not adding a search query makes your results more like the reddit website
    #search_string will not be used anymore, replaced by domain. leaving it here for now.
    #    using search string to filter by domain returns the same result everyday

    url = urlMain      # global variable urlMain = "http://www.reddit.com"

    if subreddit.startswith('?'):
        #special dev option
        url+='/search.json'+subreddit
        return url

    a=[':','/domain/']
    if any(x in subreddit for x in a):  #search for ':' or '/domain/'
        #log("domain "+ subreddit)
        domain=re.findall(r'(?::|\/domain\/)(.+)',subreddit)[0]
        #log("domain "+ str(domain))

    if domain:
        # put '/?' at the end. looks ugly but works fine.
        #https://www.reddit.com/domain/vimeo.com/?&limit=5
        url+= "/domain/%s/.json?" %(domain)   #/domain doesn't work with /search?q=
    else:
        if this_is_a_multireddit(subreddit):
            #e.g: https://www.reddit.com/user/sallyyy19/m/video/search?q=multihub&restrict_sr=on&sort=relevance&t=all
            #https://www.reddit.com/user/sallyyy19/m/video
            #url+='/user/sallyyy19/m/video'
            #format_multihub(subreddit)
            if subreddit.startswith('/'):
                #log("startswith/")
                url+=subreddit  #user can enter multihub with or without the / in the beginning
            else: url+='/'+subreddit
        else:
            if subreddit:
                url+= "/r/"+subreddit
            #else:
                #default to front page instead of r/all
                #url+= "/r/all"

        if search_string:
            if 'http' in search_string:
                url+="/submit.json?url="+ urllib.parse.quote_plus(search_string)
            else:
                #search_string = urllib.unquote_plus(search_string)
                url+= "/search.json?q=" + urllib.parse.quote_plus(search_string)

        elif skip_site_filters:
            url+= "/.json?"
        else:
            #no more supported_sites filter OR... OR... OR...
            url+= "/.json?"

    url += "&limit="+str(itemsPerPage)
    #url += "&limit=12"
    #log("assemble_reddit_filter_string="+url)
    return url

def has_multiple(tag, content_data_children):
    #combined has_multiple_domains, has_multiple_subreddit, has_multiple_author
    #used to check if a returned .json from reddit is from a single subreddit, domain or author
    s=""
    for entry in content_data_children:
        try:
            if s:
                if s!=entry['data'][tag]:
                    return True
            else:
                s=entry['data'][tag]
        except KeyError:
            continue
    return False

def collect_thumbs( entry ):
    #collect the thumbs from reddit json (not used)
    dictList = []
    keys=['thumb','width','height']
    e=[]

    try:
        e=[ entry['data']['media']['oembed']['thumbnail_url'].encode('utf-8')
           ,entry['data']['media']['oembed']['thumbnail_width']
           ,entry['data']['media']['oembed']['thumbnail_height']
           ]
        #log('  got 1')
        dictList.append(dict(list(zip(keys, e))))
    except (ValueError,TypeError,AttributeError):
        #log( "zz   " + str(e) )
        pass

    try:
        e=[ entry['data']['preview']['images'][0]['source']['url'].encode('utf-8')
           ,entry['data']['preview']['images'][0]['source']['width']
           ,entry['data']['preview']['images'][0]['source']['height']
           ]
        #log('  got 2')
        dictList.append(dict(list(zip(keys, e))))
    except(ValueError,TypeError,AttributeError):
        pass

    try:
        e=[ entry['data']['thumbnail'].encode('utf-8')        #thumbnail is always in 140px wide (?)
           ,140
           ,0
           ]
        #log('  got 3')
        dictList.append(dict(list(zip(keys, e))))
    except (ValueError,TypeError,AttributeError):
        pass
    #log( json.dumps(dictList, indent=4)  )
    #log( str(dictList)  )
    return

def determine_if_video_media_from_reddit_json( data ):
    #reads the reddit json and determines if link is a video
    is_a_video=False

    media_url=clean_str(data,['media','oembed','url'],'')
    if media_url=='':
        media_url=clean_str(data,['url'])

    # also check  "post_hint" : "rich:video"

    media_url=media_url.split('?')[0] #get rid of the query string
    try:
        zzz = data['media']['oembed']['type']
        #log("    zzz"+str(idx)+"="+str(zzz))
        if zzz == None:   #usually, entry['data']['media'] is null for not videos but it is also null for gifv especially nsfw
            if ".gifv" in media_url.lower():  #special case for imgur
                is_a_video=True
            else:
                is_a_video=False
        elif zzz == 'video':
            is_a_video=True
        else:
            is_a_video=False
    except (KeyError,TypeError,AttributeError):
        is_a_video=False

    return is_a_video

def get_subreddit_info( subreddit ):
    import requests
    #import pprint
    subs_dict={}
    #log('get_subreddit_info(%s)' %subreddit)
    headers = {'User-Agent': reddit_userAgent}
    req='https://www.reddit.com/r/%s/about.json' %subreddit
    #log('headers:' + repr(headers))
    r = requests.get( req, headers=headers, timeout=REQUEST_TIMEOUT )
    if r.status_code == requests.codes.ok:
        try:
            j=r.json()
            #log( pprint.pformat(j, indent=1) )
            j=j.get('data')
            if 'display_name' in j:
                subs_dict.update( {'entry_name':subreddit.lower(),
                                   'display_name':j.get('display_name'),
                                   'banner_img': j.get('banner_img'),
                                   'icon_img': j.get('icon_img'),
                                   'header_img': j.get('header_img'), #not used? usually similar to with icon_img
                                   'title':j.get('title'),
                                   'header_title':j.get('header_title'),
                                   'public_description':j.get('public_description'),
                                   'subreddit_type':j.get('subreddit_type'),
                                   'subscribers':j.get('subscribers'),
                                   'created':j.get('created'),        #public, private
                                   'over18':j.get('over18'),
                                   'icon_size':j.get('icon_size'),
                                   'banner_size':j.get('banner_size'),
                                   'header_size':j.get('header_size'),
                                   } )
                #import pprint
                #log( pprint.pformat(subs_dict, indent=1) )
                return subs_dict
        except ValueError:
            log('    ERROR:No data for (%s)'%subreddit)
        else:
            log('    ERROR:No data for (%s)'%subreddit)
    else:
        log( '    ERROR:getting subreddit (%s) info:%s' %(subreddit, r.status_code) )

subreddits_dlist=[]
def ret_sub_info( subreddit_entry ):
    #search subreddits_dlist for subreddit_entry and return info about it
    #randomly pick one if there are multiple subreddits e.g.: gifs+funny
    import random
    from . utils import load_dict
    global subreddits_dlist #we make sure we only load the subredditsPickle file once for this instance
    try:
        if not subreddits_dlist:
            if os.path.exists(subredditsPickle):
                subreddits_dlist=load_dict(subredditsPickle)

        subreddit_search=subreddit_entry.lower()  #<--note everything being lcase'd

        if subreddit_entry.startswith('http'): #differentiate link shortcuts(http://youtube...) from (diy/new)
            #subreddit_search=subreddit_search
            pass
        else:
            if '/' in subreddit_search: #search only for "diy" in "diy/new"
                subreddit_search=subreddit_search.split('/')[0]

        if '+' in subreddit_search: #for combined subredits, randomly search for one of them.
            subreddit_search=random.choice(subreddit_search.split('+'))

        for sd in subreddits_dlist:
            #if subreddit_entry.startswith('http'):log('comapring entry: '+repr(sd.get('entry_name') + '     '+ repr(subreddit_search)  ))
            if sd.get('entry_name','').lower()==subreddit_search:
                return sd
    except Exception as e:
        #sometimes we get a race condition when the save thread is saving and the index function is listing
        #hopefully the 'global' line up above minimizes this
        log('**error parsing subredditsPickle (ret_sub_info):'+str(e))

def ret_sub_icon(subreddit):
    sub_info=ret_sub_info(subreddit)

    if sub_info:
        #return the first item that isn't blank.
        return next((item for item in [sub_info.get('icon_img'),sub_info.get('banner_img'),sub_info.get('header_img')] if item ), '')

subredditsFile_entries=[]
def load_subredditsFile():
    global subredditsFile_entries
    if not subredditsFile_entries:
        if os.path.exists(subredditsFile):  #....\Kodi\userdata\addon_data\plugin.video.reddit_viewer\subreddits
            with open(subredditsFile, 'r') as fh:
                content = fh.read()
            spl = content.split('\n')

            for i in range(0, len(spl), 1):
                if spl[i]:
                    subreddit = spl[i].strip()

                    subredditsFile_entries.append(subreddit )
    return subredditsFile_entries

def subreddit_in_favorites( subreddit ):
    sub_favorites=load_subredditsFile()
    for entry in sub_favorites:
        if subreddit.lower() == entry.lower():
            return True
        if '+' in entry:
            spl=entry.split('+')
            for s in spl:
                if subreddit.lower() == s.lower():
                    return True

def get_subreddit_entry_info(subreddit):
    import threading

    s=convert_settings_entry_into_subreddits_list_or_domain(subreddit)
    if s:
        t = threading.Thread(target=get_subreddit_entry_info_thread, args=(s,) )
        #log('****starting... '+repr(t))
        t.start()

def convert_settings_entry_into_subreddits_list_or_domain(settings_entry):
    #settings_entry=settings_entry.lower().strip()
    settings_entry=settings_entry.strip()
    if settings_entry in ['all','random','randnsfw','popular']:
        return

    if settings_entry.startswith('/user'):#no icon for multireddit or saved posts
        return

    if settings_entry.startswith('?'):  #no icon for searches
        return

    s=[]

    if settings_entry.startswith('http'):
        s.append(settings_entry)
        return s

    if '/' in settings_entry:  #only get "diy" from "diy/top" or "diy/new"
        settings_entry=settings_entry.split('/')[0]

    if '+' in settings_entry:
        s.extend(settings_entry.split('+'))
    else:
        s.append(settings_entry)

    return s

def get_subreddit_entry_info_thread(sub_list):
    from . utils import load_dict, save_dict, get_domain_icon, setting_entry_is_domain
    from . domains import ClassYoutube

    global subreddits_dlist #subreddits_dlist=[]
    #log('**** thread running:'+repr(sub_list))
    if not subreddits_dlist:
        if os.path.exists(subredditsPickle):
            #log('****file exists ' + repr( subredditsPickle ))
            subreddits_dlist=load_dict(subredditsPickle)
            #for e in subreddits_dlist: log(e.get('entry_name'))
            #log( pprint.pformat(subreddits_dlist, indent=1) )
    #log('****------before for -------- ' + repr(sub_list ))
    for subreddit in sub_list:
        #handle link shortcuts
        if subreddit.startswith('https://'):
            entry_in_file=subreddit
            without_alias=re.sub(r"[\(\[].*?[\)\]]", "", entry_in_file)
            yt=ClassYoutube(without_alias)
            url_type,id_=yt.get_video_channel_user_or_playlist_id_from_url(without_alias)
            if url_type=='channel':
                sub_info=yt.get_channel_info(id_, entry_name=entry_in_file)
            else:
                #this part not used, right now only youtube channels are supported.
                log('  getting link info:entry_in_file=%s  without_alias=%s'%(repr(entry_in_file),repr(without_alias))  )
                sub_info=get_domain_icon(entry_in_file,None,without_alias )
        else:
            subreddit=subreddit.lower().strip()
            #remove old instance of subreddit
            #log('****processing ' + repr( subreddit ))
            subreddits_dlist=[x for x in subreddits_dlist if x.get('entry_name','') != subreddit ]

            domain=setting_entry_is_domain(subreddit)
            if domain:
                log('  getting domain info '+domain)
                sub_info=get_domain_icon(subreddit,domain)
                #icon="http://%s/favicon.ico"%domain
            else:
                log('  getting sub info '+subreddit)
                sub_info=get_subreddit_info(subreddit)

        log('    retrieved subreddit info ' + repr( sub_info ))
        if sub_info:
            subreddits_dlist.append(sub_info)
            save_dict(subreddits_dlist, subredditsPickle)
            #log('****saved ')
def subreddit_icoheader_banner(subreddit):
    #from reddit import get_subreddit_entry_info, ret_sub_info
    addtl_subr_info=ret_sub_info(subreddit)
    #log('addtl_subr_info'+repr(addtl_subr_info))
    try: #if addtl_subr_info:
        icon=addtl_subr_info.get('icon_img')
        banner=addtl_subr_info.get('banner_img')
        header=addtl_subr_info.get('header_img',None)  #usually the small icon on upper left side on subreddit screen // also sometimes a very wide banner

        #icon_ar=img_ar(addtl_subr_info.get('icon_size'))
        #banner_ar=img_ar(addtl_subr_info.get('banner_size'))
        header_ar=img_ar(addtl_subr_info.get('header_size'))

        #some subreddits have a very long header image(r/mealtimevideos)
        #we'll use that as banner (shows at top of gui)
        if header_ar > 8 and not banner:
            #log( 'replacing banner with header')
            banner=header
            header=None

        #log('\nicon:'+repr(icon)+'\nheader:'+repr(header)+'\nbanner:'+repr(banner))
        #icoheader=(icon if icon else header)
    except AttributeError:
        icon=banner=header=None
        #get subreddit info and store it in out subreddits pickle for next time
        get_subreddit_entry_info(subreddit)
    return icon,banner,header

def img_ar(img_size_array):
    #img_size_array is from from reddit's about.json
    ar=0
    try:
        w,h=img_size_array
        ar=float(w)/h
        #log("{0} = {1},{2}".format(ar,w,h) )
    except (TypeError,ZeroDivisionError):  #,ValueError):
        ar=0
    return ar

def subreddit_entry_to_listitem(subreddit_entry):
    from . utils import compose_list_item, build_script, xstr, prettify_reddit_query
    addtl_subr_info={}
    nsfw=False
    icon=banner=header=public_description=display_name=override_header_image=None
    header_ar=0
    addtl_subr_info=ret_sub_info(subreddit_entry)

    #strip out the alias identifier from the subreddit string retrieved from the file so we can process it.
    entry_type, subreddit, alias, shortcut_description=parse_subreddit_entry(subreddit_entry)
    icon=default_icon=ret_settings_type_default_icon(entry_type)

    pretty_label=prettify_reddit_query(alias)
    pretty_label=pretty_label.replace('+',' + ')

    if addtl_subr_info:
        icon=addtl_subr_info.get('icon_img')
        banner=addtl_subr_info.get('banner_img')  #rectangular shape
        header=addtl_subr_info.get('header_img')  #square shape  from  bannerTvImageUrl
        header_ar=img_ar(addtl_subr_info.get('header_size'))
        if (header_ar > 8) and (not icon): #some header_img are very wide. this is to check and override the icon display in the gui
            override_header_image=header
            banner=header
        public_description=xstr( addtl_subr_info.get('public_description',''))
        display_name=xstr(addtl_subr_info.get('display_name',''))

    #log('{0} icon={1} header={2} banner={3}'.format( subreddit, repr(icon), repr(header), repr(banner) ))

    if entry_type=='link':  #<-- added new ability to have youtube channels as a shortcut on the main screen
        #here, the subreddit variable contains a url. we made sure that it points to a youtube channel(ContextMenus.py). that way, there is no need to specify 'channel' when calling listRelatedVideo
        liz = compose_list_item( pretty_label, entry_type, "", "script", build_script("listRelatedVideo",subreddit,alias) )
    else: #domain, subreddit, combined, search, multireddit
        reddit_url=assemble_reddit_filter_string("",subreddit, "yes")

        if entry_type=='domain':
            #remove the identifier that this setting is a domain
            pretty_label=re.findall(r'(?::|\/domain\/)(.+)',subreddit)[0]

        if subreddit.lower() in ["all","popular"]:
            liz = compose_list_item( pretty_label, entry_type, "", "script", build_script("listSubReddit",reddit_url,alias) )
        else:
            if addtl_subr_info: #if we have additional info about this subreddit
                #log(repr(addtl_subr_info))
                #title=addtl_subr_info.get('title','')+'\n'
                #display_name=xstr(addtl_subr_info.get('display_name',''))
                #if samealphabetic( title, display_name): title=''

                #header_title=xstr(addtl_subr_info.get('header_title',''))
                #in reddit_viewer,  title, header_title and public_description is shown as plot
                nsfw=addtl_subr_info.get('over18')

                icon=next((item for item in [icon,banner,header] if item ), '') or default_icon #picks the first item that is not None
                #icon=icon or default_icon
                #log( pretty_label + ' icon=' + icon + ' nsfw='+repr(nsfw))
                liz = compose_list_item( pretty_label, entry_type, "", "script", build_script("listSubReddit",reddit_url,alias) )
            else:
                liz = compose_list_item( pretty_label, entry_type, "", "script", build_script("listSubReddit",reddit_url,alias) )

    liz.setArt({ "thumb": icon, "banner":banner, "fanart":override_header_image })
    liz.setInfo('video', {"Title":display_name, "plot":public_description} )

    if nsfw:
        liz.setProperty('nsfw', 'true' )

    return liz

if __name__ == '__main__':
    pass
