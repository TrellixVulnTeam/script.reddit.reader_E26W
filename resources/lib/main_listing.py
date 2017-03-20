# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import xbmcaddon
import urllib
import json
import threading
import re
from Queue import Queue

import os,sys

from default import addon, addon_path, itemsPerPage, urlMain, subredditsFile, int_CommentTreshold
from utils import xbmc_busy, log, translation


default_frontpage    = addon.getSetting("default_frontpage")
no_index_page        = addon.getSetting("no_index_page") == "true"
main_gui_skin        = addon.getSetting("main_gui_skin")


def index(url,name,type_):
    ## this is where the __main screen is created

    from guis import indexGui
    from reddit import assemble_reddit_filter_string, create_default_subreddits

    if not os.path.exists(subredditsFile):
        create_default_subreddits()

    if no_index_page:
        log( "   default_frontpage " +default_frontpage )
        if default_frontpage:
            listSubReddit( assemble_reddit_filter_string("",default_frontpage) , default_frontpage, "")
        else:
            listSubReddit( assemble_reddit_filter_string("","") , "Reddit-Frontpage", "") #https://www.reddit.com/.json?&&limit=10
    else:
        #subredditsFile loaded in gui
        ui = indexGui('view_461_comments.xml' , addon_path, defaultSkin='Default', defaultRes='1080i', subreddits_file=subredditsFile, id=55)
        ui.title_bar_text="Reddit Reader"
        ui.include_parent_directory_entry=False

        ui.doModal()
        del ui

    return

def listSubReddit(url, title_bar_name, type_):
    from utils import post_is_filtered_out, build_script, compose_list_item, xbmc_busy
    from reddit import reddit_request, has_multiple_subreddits, assemble_reddit_filter_string

    #the +'s got removed by url conversion
    title_bar_name=title_bar_name.replace(' ','+')
    #log("  title_bar_name %s " %(title_bar_name) )

    log("listSubReddit r/%s url=%s" %(title_bar_name,url) )

    li=[]

    currentUrl = url
    xbmc_busy()

    dialog_progress = xbmcgui.DialogProgressBG()
    dialog_progress_heading='Loading'
    dialog_progress.create(dialog_progress_heading )
    dialog_progress.update(0,dialog_progress_heading, title_bar_name  )

    content = reddit_request(url)  #content = opener.open(url).read()

    if not content:
        xbmc_busy(False)
        return

    threads = []
    #q_posts = Queue() #input queue for worker(json entry of a single post)
    q_liz = Queue()   #output queue (listitem)

    #7-15-2016  removed the "replace(..." statement below cause it was causing error
    #content = json.loads(content.replace('\\"', '\''))
    content = json.loads(content)

    #log("query returned %d items " % len(content['data']['children']) )
    posts_count=len(content['data']['children'])

    hms = has_multiple_subreddits(content['data']['children'])
    if hms==False:
        #r/random and r/randnsfw returns a random subreddit. we need to use the name of this subreddit for the "next page" link.
        try: g=content['data']['children'][0]['data']['subreddit']
        except ValueError: g=""
        if g:
            title_bar_name=g
            #preserve the &after string so that functions like play slideshow and play all videos can 'play' the correct page
            #  extract the &after string from currentUrl -OR- send it with the 'type' argument when calling this function.
            currentUrl=assemble_reddit_filter_string('',g) + '&after=' + type_

    for idx, entry in enumerate(content['data']['children']):
        try:
            if post_is_filtered_out( entry ):
                continue

            #have threads process each reddit post
            t = threading.Thread(target=reddit_post_worker, args=(idx, entry,q_liz), name='#t%.2d'%idx)
            threads.append(t)
            t.start()

        except Exception as e:
            log(" EXCEPTION:="+ str( sys.exc_info()[0]) + "  " + str(e) )

    #wait for all threads to finish before collecting the list items
    for idx, t in enumerate(threads):
        #log('    joining %s' %t.getName())
        t.join(timeout=20)
        loading_percentage=int((float(idx)/posts_count)*100)
        dialog_progress.update( loading_percentage,dialog_progress_heading  )

    xbmc_busy(False)

    #compare the number of entries to the returned results
    #log( "queue:%d entries:%d" %( q_liz.qsize() , len(content['data']['children'] ) ) )
    if q_liz.qsize() != len(content['data']['children']):
        #some post might be filtered out.
        log('some threads did not return a listitem')

    #for t in threads: log('isAlive %s %s' %(t.getName(), repr(t.isAlive()) )  )

    #liu=[ qi for qi in sorted(q_liz.queue) ]
    li=[ liz for idx,liz in sorted(q_liz.queue) ]
    #log(repr(li))

    #empty the queue.
    with q_liz.mutex:
        q_liz.queue.clear()

    dialog_progress.update( 100,dialog_progress_heading  )
    dialog_progress.close() #it is important to close xbmcgui.DialogProgressBG

    try:
        #this part makes sure that you load the next page instead of just the first
        after=""
        after = content['data']['after']
        if after:
            if "&after=" in currentUrl:
                nextUrl = currentUrl[:currentUrl.find("&after=")]+"&after="+after
            else:
                nextUrl = currentUrl+"&after="+after

            liz = compose_list_item( translation(32004), "", "DefaultFolderNextSquare.png", "script", build_script("listSubReddit",nextUrl,title_bar_name,after), {'plot': translation(32004)} )

            li.append(liz)

    except Exception as e:
        log(" EXCEPTzION:="+ str( sys.exc_info()[0]) + "  " + str(e) )

    xbmc_busy(False)

    title_bar_name=urllib.unquote_plus(title_bar_name)
    ui=skin_launcher('listSubReddit', title_bar_name=title_bar_name, li=li,subreddits_file=subredditsFile, currentUrl=currentUrl)
    #set properties to the window(to be retrieved by gui methods)
    ui.setProperty('actual_url_used_to_generate_these_posts',url)    #used by reload function - specially done for r/random and r/randnsfw (could have used currentUrl)
    ui.doModal()
    del ui
    #ui.show()  #<-- interesting possibilities. you have to handle the actions outside of the gui class.
    #xbmc.sleep(8000)

def skin_launcher(mode,**kwargs ):
    #launches the gui using .xml file defined in settings (incomplete)
    from guis import listSubRedditGUI

    #kodi_version = xbmcVersion()
    #log( ' kodi version:%f' % kodi_version )
    #if kodi_version >= 17:  #krypton
    #    pass

    title_bar_text=kwargs.get('title_bar_name')
    li=kwargs.get('li')
    subreddits_file=kwargs.get('subreddits_file')
    currentUrl=kwargs.get('currentUrl')
    #log('********************* ' + repr(currentUrl))
    try:
        ui = listSubRedditGUI(main_gui_skin , addon_path, defaultSkin='Default', defaultRes='1080i', listing=li, subreddits_file=subreddits_file, id=55)
        ui.title_bar_text='[B]'+ title_bar_text + '[/B]'
        ui.reddit_query_of_this_gui=currentUrl
        #ui.include_parent_directory_entry=True
        #ui.doModal()
        #del ui
        return ui
    except Exception as e:
        log('  skin_launcher:%s(%s)' %( str(e), main_gui_skin ) )
        xbmc.executebuiltin('XBMC.Notification("%s","%s[CR](%s)")' %(  translation(32108), str(e), main_gui_skin)  )

def addLink(title, title_line2, iconimage, previewimage,preview_w,preview_h,domain, description, credate, reddit_says_is_video, site, subreddit, link_url, over_18, posted_by="", num_comments=0,post_id='', post_index=1,post_total=1,many_subreddit=False ):
    from utils import ret_info_type_icon, build_script
    from reddit import assemble_reddit_filter_string
    from domains import parse_reddit_link, sitesBase

    DirectoryItem_url=''
    il_description=""

    preview_ar=0.0
    if preview_w==0 or preview_h==0:
        preview_ar=0.0
    else:
        preview_ar=float(preview_w) / preview_h

    if over_18:
        mpaa="R"
        title_line2 = "[COLOR red][NSFW][/COLOR] "+title_line2
    else:
        mpaa=""

    post_title=title
    if len(post_title) > 40:
        il_description='[B]%s[/B][CR][CR]%s' %( post_title, description )
    else:
        il_description='%s' %( description )

    il={ "title": post_title, "plot": il_description, "Aired": credate, "mpaa": mpaa, "Genre": "r/"+subreddit, "studio": domain, "director": posted_by }   #, "duration": 1271}   (duration uses seconds for titan skin

    liz=xbmcgui.ListItem(label=post_title
                         ,label2=title_line2
                         ,iconImage=""
                         ,thumbnailImage=''
                         ,path='')   #path not used by gui.

    if preview_ar>1.25:   #this measurement is related to control id 203's height
        #log('    ar and description criteria met')
        #the gui checks for this: String.IsEmpty(Container(55).ListItem.Property(preview_ar))  to show/hide preview and description
        liz.setProperty('preview_ar', str(preview_ar) ) # -- $INFO[ListItem.property(preview_ar)]
        liz.setInfo(type='video', infoLabels={"plotoutline": il_description, }  )

    #----- assign actions
    if num_comments > 0 or description:
        liz.setProperty('comments_action', build_script('listLinksInComment', site ) )
    liz.setProperty('goto_subreddit_action', build_script("listSubReddit", assemble_reddit_filter_string("",subreddit), subreddit) )
    liz.setProperty('link_url', link_url )
    liz.setProperty('post_id', post_id )

    liz.setInfo(type='video', infoLabels=il)

    #use clearart to indicate if link is video, album or image. here, we default to unsupported.
    clearart=ret_info_type_icon('', '')
    liz.setArt({ "clearart": clearart  })

    #force all links to ytdl to see if they are playable
    #if use_ytdl_for_unknown:
    liz.setProperty('item_type','script')
    liz.setProperty('onClick_action', build_script('playYTDLVideo', link_url,'',previewimage) )

    if previewimage: needs_preview=False
    else:            needs_preview=True  #reddit has no thumbnail for this link. please get one


    ld=parse_reddit_link(link_url,reddit_says_is_video, needs_preview, False, preview_ar  )

    if previewimage=="":
        liz.setArt({"thumb": iconimage, "banner": ld.poster if ld else '' , })
    else:
        liz.setArt({"thumb": iconimage, "banner":previewimage,  })

    #log( '          reddit thumb[%s] ' %(iconimage ))
    #log( '          reddit preview[%s] ar=%f %dx%d' %(previewimage, preview_ar, preview_w,preview_h ))
    #if ld: log( '          new-thumb[%s] poster[%s] ' %( ld.thumb, ld.poster ))

    if ld:
        #log('###' + repr(ld.playable_url) )
        #url_for_DirectoryItem = build_script(ld.link_action, ld.playable_url, post_title , previewimage )
        #log('  ##is supported')

        #use clearart to indicate the type of link(video, album, image etc.)
        clearart=ret_info_type_icon(ld.media_type, ld.link_action, domain )
        liz.setArt({ "clearart": clearart  })

        if iconimage in ["","nsfw", "default"]:
            iconimage=ld.thumb

        #link_action set in domains.py - parse_reddit_link
        if ld.link_action == sitesBase.DI_ACTION_PLAYABLE:
            property_link_type=ld.link_action
            DirectoryItem_url =ld.playable_url
        else:
            property_link_type='script'
            if ld.link_action=='viewTallImage' : #viewTallImage take different args
                DirectoryItem_url = build_script(mode=ld.link_action,
                                                 url=ld.playable_url,
                                                 name=str(preview_w),
                                                 type_=str(preview_h) )
            else:
                #log( '****' + repr( ld.dictlist ))
                DirectoryItem_url = build_script(mode=ld.link_action,
                                                 url=ld.playable_url,
                                                 name=post_title ,
                                                 type_=previewimage )

        #log('    action %s--%s' %( ld.link_action, DirectoryItem_url) )

        liz.setProperty('item_type',property_link_type)
        liz.setProperty('onClick_action',DirectoryItem_url)
        liz.setProperty('album_images', json.dumps(ld.dictlist) ) # dictlist=json.loads(string)
        #log( liz.getProperty('album_images'))
    else:
        #unsupported type here:
        pass

    return liz

def reddit_post_worker(idx, entry, q_out):
    import datetime
    from utils import strip_emoji, pretty_datediff, clean_str
    from reddit import determine_if_video_media_from_reddit_json
    try:
        credate = ""
        is_a_video=False
        title_line2=""

        thumb_w=0
        thumb_h=0

        t_on = translation(32071)  #"on"
        #t_pts = u"\U0001F4AC"  # translation(30072) #"cmnts"  comment bubble symbol. doesn't work
        t_pts = u"\U00002709"  # translation(30072)   envelope symbol
        t_up = u"\U000025B4"  #u"\U00009650"(up arrow)   #upvote symbol

        data=entry.get('data')
        if data:
            title=clean_str(data,['title'])
            title=strip_emoji(title) #an emoji in the title was causing a KeyError  u'\ud83c'

            is_a_video = determine_if_video_media_from_reddit_json(entry)
            log("  POST%cTITLE%.2d=%s" %( ("v" if is_a_video else " "), idx, title ))

            post_id = entry['kind'] + '_' + data.get('id')  #same as entry['data']['name']
            #log('  %s  %s ' % (post_id, entry['data']['name'] ))

            description=clean_str(data,['media','oembed','description'])
            post_selftext=clean_str(data,['selftext'])

            description=post_selftext+'[CR]'+description if post_selftext else description
            #log('    combined     [%s]' %description)

            commentsUrl = urlMain+clean_str(data,['permalink'])
            #log("commentsUrl"+str(idx)+"="+commentsUrl)

            try:
                aaa = data.get('created_utc')
                credate = datetime.datetime.utcfromtimestamp( aaa )
                now_utc = datetime.datetime.utcnow()
                pretty_date=pretty_datediff(now_utc, credate)
                credate = str(credate)
            except (AttributeError,TypeError,ValueError):
                credate = ""

            subreddit=clean_str(data,['subreddit'])
            author=clean_str(data,['author'])
            domain=clean_str(data,['domain'])
            #log("     DOMAIN%.2d=%s" %(idx,domain))

            ups = data.get('score',0)       #downs not used anymore
            num_comments = data.get('num_comments',0)


            media_url=clean_str(data,['url'])
            if media_url=='':
                media_url=clean_str(data,['media','oembed','url'])
            #log("     MEDIA%.2d=%s" %(idx,media_url))

            thumb=clean_str(data,['thumbnail'])

            if thumb in ['nsfw','default','self']:  #reddit has a "default" thumbnail (alien holding camera with "?")
                thumb=""

            if thumb=="":
                thumb=clean_str(data,['media','oembed','thumbnail_url']).replace('&amp;','&')

            try:
                preview=data.get('preview')['images'][0]['source']['url'].encode('utf-8').replace('&amp;','&')
                try:
                    thumb_h = float( data.get('preview')['images'][0]['source']['height'] )
                    thumb_w = float( data.get('preview')['images'][0]['source']['width'] )
                except (AttributeError,TypeError,ValueError):
                    #log("   thumb_w _h EXCEPTION:="+ str( sys.exc_info()[0]) + "  " + str(e) )
                    thumb_w=0; thumb_h=0

            except (AttributeError,TypeError,ValueError):
                #log("   getting preview image EXCEPTION:="+ str( sys.exc_info()[0]) + "  " + str(e) )
                thumb_w=0; thumb_h=0; preview="" #a blank preview image will be replaced with poster_url from parse_reddit_link() for domains that support it

            #preview images are 'keep' stretched to fit inside 1080x1080.
            #  if preview image is smaller than the box we have for thumbnail, we'll use that as thumbnail and not have a bigger stretched image
            if thumb_w > 0 and thumb_w < 280:
                #log('*******preview is small ')
                thumb=preview
                thumb_w=0; thumb_h=0; preview=""

            over_18=data.get('over_18')

            title_line2=""
            title_line2 = "[I][COLOR dimgrey]%d%c %s %s [B][COLOR cadetblue]r/%s[/COLOR][/B] (%d) %s[/COLOR][/I]" %(ups,t_up,pretty_date,t_on, subreddit,num_comments, t_pts)

            liz=addLink(title=title,
                    title_line2=title_line2,
                    iconimage=thumb,
                    previewimage=preview,
                    preview_w=thumb_w,
                    preview_h=thumb_h,
                    domain=domain,
                    description=description,
                    credate=credate,
                    reddit_says_is_video=is_a_video,
                    site=commentsUrl,
                    subreddit=subreddit,
                    link_url=media_url,
                    over_18=over_18,
                    posted_by=author,
                    num_comments=num_comments,
                    post_id=post_id,
                    #post_index=idx,
                    #post_total=0,
                    #many_subreddit=hms
                    )
            q_out.put( [idx, liz] )  #we put the idx back for easy sorting

    except Exception as e:
        log( '  #reddit_post_worker EXCEPTION:' + repr(sys.exc_info()) +'--'+ str(e) )





def listLinksInComment(url, name, type_):
    from domains import parse_reddit_link, sitesBase
    from reddit import reddit_request
    from utils import markdown_to_bbcode, unescape, ret_info_type_icon, build_script

    log('listLinksInComment:%s:%s' %(type_,url) )

    directory_items=[]
    author=""
    post_title=''
    ShowOnlyCommentsWithlink=False

    if type_=='linksOnly':
        ShowOnlyCommentsWithlink=True

    #sometimes the url has a query string. we discard it coz we add .json at the end
    #url=url.split('?', 1)[0]+'.json'

    #url='https://www.reddit.com/r/Music/comments/4k02t1/bonnie_tyler_total_eclipse_of_the_heart_80s_pop/' + '.json'
    #only get up to "https://www.reddit.com/r/Music/comments/4k02t1".
    #   do not include                                            "/bonnie_tyler_total_eclipse_of_the_heart_80s_pop/"
    #   because we'll have problem when it looks like this: "https://www.reddit.com/r/Overwatch/comments/4nx91h/ever_get_that_feeling_dÃ©jÃ _vu/"
    #url=re.findall(r'(.*/comments/[A-Za-z0-9]+)',url)[0]
    #UPDATE you need to convert this: https://www.reddit.com/r/redditviewertesting/comments/4x8v1k/test_test_what_is_déjà_vu/
    #                        to this: https://www.reddit.com/r/redditviewertesting/comments/4x8v1k/test_test_what_is_d%C3%A9j%C3%A0_vu/
    #
    #use safe='' argument in quoteplus to encode only the weird chars part

    url=  urllib.quote_plus(url,safe=':/')
    url+= '.json'
    xbmc_busy()

    dialog_progress = xbmcgui.DialogProgressBG()
    dialog_progress_heading='Loading'
    dialog_progress.create(dialog_progress_heading )
    dialog_progress.update(0,dialog_progress_heading, 'Comments'  )

    content = reddit_request(url)
    if not content: return
    #content = r''

    #log(content)
    #content = json.loads(content.replace('\\"', '\''))  #some error here ?      TypeError: 'NoneType' object is not callable
    try:
        xbmc_busy()
        content = json.loads(content)

        del harvest[:]
        #harvest links in the post text (just 1)
        r_linkHunter(content[0]['data']['children'])

        try:
            submitter=content[0]['data']['children'][0]['data']['author']
        except (AttributeError,TypeError,ValueError):
            submitter=''

        #the post title is provided in json, we'll just use that instead of messages from addLink()
        try:
            post_title=content[0]['data']['children'][0]['data']['title']
        except (AttributeError,TypeError,ValueError):
            post_title=''

        #harvest links in the post itself
        r_linkHunter(content[1]['data']['children'])

        #for i, h in enumerate(harvest):
        #    log( '  %d %s %d -%s   link[%s]' % ( i, h[7].ljust(8)[:8], h[0], h[3].ljust(20)[:20],h[2] ) )

#         h[0]=score,
#         h[1]=link_desc,
#         h[2]=link_http,
#         h[3]=post_text,
#         h[4]=post_html,
#         h[5]=d,
#         h[6]="t1",
#         h[7]=author,
#         h[8]=created_utc,

        comment_score=0
        for i, h in enumerate(harvest):

            loading_percentage=int((float(i)/len(harvest))*100)
            dialog_progress.update( loading_percentage,dialog_progress_heading  )

            #log(str(i)+"  score:"+ str(h[0]).zfill(5)+" "+ h[1] +'|'+ h[3] )
            comment_score=h[0]
            #log("score %d < %d (%s)" %(comment_score,int_CommentTreshold, CommentTreshold) )
            link_url=h[2]
            desc100=h[3].replace('\n',' ')[0:100] #first 100 characters of description

            kind=h[6] #reddit uses t1 for user comments and t3 for OP text of the post. like a poster describing the post.
            d=h[5]   #depth of the comment

            tab=" "*d if d>0 else "-"

            author=h[7]

            if link_url.startswith('/r/'):
                domain='subreddit'
            else:
                from urlparse import urlparse
                domain = '{uri.netloc}'.format( uri=urlparse( link_url ) )

            #log( '  %s TITLE:%s... link[%s]' % ( str(comment_score).zfill(4), desc100.ljust(20)[:20],link_url ) )
            if comment_score < int_CommentTreshold:
                #log('    comment score %d < %d, skipped' %(comment_score,int_CommentTreshold) )
                continue

            #hoster, DirectoryItem_url, videoID, mode_type, thumb_url,poster_url, isFolder,setInfo_type, property_link_type =make_addon_url_from(link_url, False, True)

            if link_url:
                log( '  comment %s TITLE:%s... link[%s]' % ( str(d).zfill(3), desc100.ljust(20)[:20],link_url ) )

            ld=parse_reddit_link(link_url=link_url, assume_is_video=False, needs_preview=True, get_playable_url=True )

            if author==submitter:#add a submitter tag
                author="[COLOR cadetblue][B]%s[/B][/COLOR][S]" %author
            else:
                author="[COLOR cadetblue]%s[/COLOR]" %author

            if kind=='t1':
                t_prepend=r"%s" %( tab )
            elif kind=='t3':
                t_prepend=r"[B]Post text:[/B]"

            #helps the the textbox control treat [url description] and (url) as separate words. so that they can be separated into 2 lines
            plot=h[3].replace('](', '] (')
            plot= markdown_to_bbcode(plot)
            plot=unescape(plot)  #convert html entities e.g.:(&#39;)

            liz=xbmcgui.ListItem(label=t_prepend + author + ': '+ desc100 ,
                                 label2="",
                                 iconImage="",
                                 thumbnailImage="")

            liz.setInfo( type="Video", infoLabels={ "Title": h[1], "plot": plot, "studio": domain, "votes": str(comment_score), "director": author } )


            #force all links to ytdl to see if it can be played
            if link_url:
                #log('      there is a link from %s' %domain)
                if not ld:
                    #log('      link is not supported ')
                    liz.setProperty('item_type','script')
                    liz.setProperty('onClick_action', build_script('playYTDLVideo', link_url) )
                    plot= "[COLOR greenyellow][%s] %s"%('?', plot )  + "[/COLOR]"
                    liz.setLabel(tab+plot)
                    liz.setProperty('link_url', link_url )  #just used as text at bottom of the screen

                    clearart=ret_info_type_icon('', '')
                    liz.setArt({ "clearart": clearart  })
            if ld:
                #use clearart to indicate if link is video, album or image. here, we default to unsupported.
                #clearart=ret_info_type_icon(setInfo_type, mode_type)
                clearart=ret_info_type_icon(ld.media_type, ld.link_action, domain )
                liz.setArt({ "clearart": clearart  })

                if ld.link_action == sitesBase.DI_ACTION_PLAYABLE:
                    property_link_type=ld.link_action
                    DirectoryItem_url =ld.playable_url
                else:
                    property_link_type='script'
                    DirectoryItem_url = build_script(mode=ld.link_action,
                                                     url=ld.playable_url,
                                                     name='' ,
                                                     type_='' )

                #(score, link_desc, link_http, post_text, post_html, d, )
                #list_item_name=str(h[0]).zfill(3)

                #log(str(i)+"  score:"+ str(h[0]).zfill(5)+" desc["+ h[1] +']|text:['+ h[3]+']' +link_url + '  videoID['+videoID+']' + 'playable:'+ setProperty_IsPlayable )
                #log( h[4] + ' -- videoID['+videoID+']' )
                #log("sss:"+ supportedPluginUrl )

                #fl= re.compile('\[(.*?)\]\(.*?\)',re.IGNORECASE) #match '[...](...)' with a capture group inside the []'s as capturegroup1
                #result = fl.sub(r"[B]\1[/B]", h[3])              #replace the match with [B] [/B] with capturegroup1 in the middle of the [B]'s

                #turn link green
                if DirectoryItem_url:
                    plot= "[COLOR greenyellow][%s] %s"%(domain, plot )  + "[/COLOR]"
                    liz.setLabel(tab+plot)

                    #liz.setArt({"thumb": thumb_url, "poster":thumb_url, "banner":thumb_url, "fanart":thumb_url, "landscape":thumb_url   })
                    liz.setArt({"thumb": ld.poster })

                    liz.setProperty('item_type',property_link_type)   #script or playable
                    liz.setProperty('onClick_action', DirectoryItem_url)  #<-- needed by the xml gui skin
                    liz.setProperty('link_url', link_url )  #just used as text at bottom of the screen
                    #liz.setPath(DirectoryItem_url)

                    directory_items.append( (DirectoryItem_url, liz,) )

                #xbmcplugin.addDirectoryItem(handle=pluginhandle,url=DirectoryItem_url,listitem=liz,isFolder=isFolder)
            else:
                #this section are for comments that have no links or unsupported links
                if not ShowOnlyCommentsWithlink:
                    directory_items.append( ("", liz, ) )

                #END section are for comments that have no links or unsupported links

    except Exception as e:
        log('  ' + str(e) )

    dialog_progress.update( 100,dialog_progress_heading  )
    dialog_progress.close()

    xbmc_busy(False)
    #for di in directory_items:
    #    log( str(di) )

    from guis import commentsGUI

    li=[]
    for di in directory_items:
        #log( '   %s-%s'  %(di[1].getLabel(), di[1].getProperty('onClick_action') ) )
        li.append( di[1] )

#     li.sort( key=getKey )
#     log("  sorted")
#
#     for l in li:
#         log( '   %s-%s'  %(l.getLabel(), l.getProperty('onClick_action') ) )


    ui = commentsGUI('view_461_comments.xml' , addon_path, defaultSkin='Default', defaultRes='1080i', listing=li, id=55)
    #NOTE: the subreddit selection screen and comments screen use the same gui. there is a button that is only for the comments screen
    ui.setProperty('comments', 'yes')   #i cannot get the links button to show/hide in the gui class. I resort to setting a property and having the button xml check for this property to show/hide

    #ui = commentsGUI('view_463_comments.xml' , addon_path, defaultSkin='Default', defaultRes='1080i', listing=li, id=55)
    ui.title_bar_text=post_title
    ui.include_parent_directory_entry=False

    ui.doModal()
    del ui

harvest=[]
def r_linkHunter(json_node,d=0):
    from utils import clean_str
    #recursive function to harvest stuff from the reddit comments json reply
    prog = re.compile('<a href=[\'"]?([^\'" >]+)[\'"]>(.*?)</a>')
    for e in json_node:
        link_desc=""
        link_http=""
        author=""
        created_utc=""
        e_data=e.get('data')
        score=e_data.get('score',0)
        if e['kind']=='t1':     #'t1' for comments   'more' for more comments (not supported)
            #log("replyid:"+str(d)+" "+e['data']['id'])
            #body=e['data']['body'].encode('utf-8')

            #log("reply:"+str(d)+" "+body.replace('\n','')[0:80])
            try: replies=e_data.get('replies')['data']['children']
            except (AttributeError,TypeError): replies=""

            post_text=clean_str(e_data,['body'])
            post_text=post_text.replace("\n\n","\n")

            post_html=clean_str(e_data,['body_html'])

            created_utc=e_data.get('created_utc','')

            author=clean_str(e_data,['author'])

            #i initially tried to search for [link description](https:www.yhotuve.com/...) in the post_text but some posts do not follow this convention
            #prog = re.compile('\[(.*?)\]\((https?:\/\/.*?)\)')
            #result = prog.findall(post_text)

            result = prog.findall(post_html)
            if result:
                #store the post by itself and then a separate one for each link.
                harvest.append((score, link_desc, link_http, post_text, post_html, d, "t1",author,created_utc,)   )

                for link_http,link_desc in result:
                    harvest.append((score, link_desc, link_http, link_desc, post_html, d, "t1",author,created_utc,)   )
            else:
                harvest.append((score, link_desc, link_http, post_text, post_html, d, "t1",author,created_utc,)   )

            d+=1 #d tells us how deep is the comment in
            r_linkHunter(replies,d)
            d-=1

        if e['kind']=='t3':     #'t3' for post text (a description of the post)
            self_text=clean_str(e_data,['selftext'])
            self_text_html=clean_str(e_data,['selftext_html'])

            result = prog.findall(self_text_html)
            if len(result) > 0 :
                harvest.append((score, link_desc, link_http, self_text, self_text_html, d, "t3",author,created_utc, )   )

                for link_http,link_desc in result:
                    harvest.append((score, link_desc, link_http, link_desc, self_text_html, d, "t3",author,created_utc, )   )
            else:
                if len(self_text) > 0: #don't post an empty titles
                    harvest.append((score, link_desc, link_http, self_text, self_text_html, d, "t3",author,created_utc,)   )



if __name__ == '__main__':
    pass