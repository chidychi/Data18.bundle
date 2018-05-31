# Data18
import re, types, traceback
import Queue

# URLS
VERSION_NO = '1.2016.06.30.1'
D18_BASE_URL = 'http://www.data18.com/'
D18_MOVIE_INFO = D18_BASE_URL + 'movies/%s'
D18_SEARCH_URL = D18_BASE_URL + 'search/?k=%s&t=0'
D18_STAR_PHOTO = D18_BASE_URL + 'img/stars/120/%s.jpg'

REQUEST_DELAY = 0       # Delay used when requesting HTML, may be good to have to prevent being banned from the site

INITIAL_SCORE = 100     # Starting value for score before deductions are taken.
GOOD_SCORE = 98         # Score required to short-circuit matching and stop searching.
IGNORE_SCORE = 45       # Any score lower than this will be ignored.

THREAD_MAX = 20

def Start():
    #HTTP.ClearCache()
    HTTP.CacheTime = CACHE_1WEEK
    HTTP.Headers['User-agent'] = 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.2; Trident/4.0; SLCC2; .NET CLR 2.0.50727; .NET CLR 3.5.30729; .NET CLR 3.0.30729; Media Center PC 6.0)'
    HTTP.Headers['Accept-Encoding'] = 'gzip'

class Data18(Agent.Movies):
    name = 'Data18'
    languages = [Locale.Language.NoLanguage]
    primary_provider = True
    accepts_from = ['com.plexapp.agents.localmedia']

    prev_search_provider = 0

    def Log(self, message, *args):
        if Prefs['debug']:
            Log(message, *args)

    def getDateFromString(self, string):
        try:
            return Datetime.ParseDate(string).date()
        except:
            return None

    def getStringContentFromXPath(self, source, query):
        return source.xpath('string(' + query + ')')

    def getAnchorUrlFromXPath(self, source, query):
        anchor = source.xpath(query)

        if len(anchor) == 0:
            return None

        return anchor[0].get('href')

    def getImageUrlFromXPath(self, source, query):
        img = source.xpath(query)

        if len(img) == 0:
            return None

        return img[0].get('src')

    def findDateInTitle(self, title):
        result = re.search(r'(\d+-\d+-\d+)', title)
        if result is not None:
            return Datetime.ParseDate(result.group(0)).date()
        return None

    def doSearch(self, url):
        html = HTML.ElementFromURL(url, sleep=REQUEST_DELAY)

        found = []
        for r in html.xpath('//div[a/img[@class="yborder"]]'):
            date = self.getDateFromString(self.getStringContentFromXPath(r, 'text()[1]'))
            title = self.getStringContentFromXPath(r, 'a[2]')
            murl = self.getAnchorUrlFromXPath(r, 'a[2]')
            thumb = self.getImageUrlFromXPath(r, 'a/img')

            found.append({'url': murl, 'title': title, 'date': date, 'thumb': thumb})

        return found

    def search(self, results, media, lang, manual=False):
        if media.name.isdigit():

            self.Log('Media.name is numeric')
            # Make url
            url = D18_MOVIE_INFO % media.name
            # Fetch HTML
            html = HTML.ElementFromURL(url, sleep=REQUEST_DELAY)
            # Set the result
            results.Append(MetadataSearchResult(id = media.name, name  = self.getStringContentFromXPath(html, '//h1'), score = '100', lang = lang))

        yearFromNamePattern = r'\(\d{4}\)'
        yearFromName = re.search(yearFromNamePattern, media.name)
        if not media.year and yearFromName is not None:
            media.year = yearFromName.group(0)[1:-1]
            media.name = re.sub(yearFromNamePattern, '', media.name).strip()
            self.Log('Found the year %s in the name "%s". Using it to narrow search.', media.year, media.name)

        # Clean up year.
        if media.year:
            searchYear = u' (' + safe_unicode(media.year) + u')'
        else:
            searchYear = u''

        # Normalize the name
        normalizedName = String.StripDiacritics(media.name)
        if len(normalizedName) == 0:
            normalizedName = media.name

        self.Log('***** SEARCHING FOR "%s"%s - DATA18 v.%s *****', normalizedName, searchYear, VERSION_NO)

        # Make the URL
        searchUrl = D18_SEARCH_URL % (String.Quote((normalizedName).encode('utf-8'), usePlus=True))
        found = self.doSearch(searchUrl)
        found2 = media.name.lstrip('0123456789')
        if normalizedName != found2:
            searchUrl = D18_SEARCH_URL % (String.Quote((found2).encode('utf-8'), usePlus=True))
            found.extend(self.doSearch(searchUrl))

        # Write search result status to log
        if len(found) == 0:
            self.Log('No results found for query "%s"%s', normalizedName, searchYear)
            return
        else:
            self.Log('Found %s result(s) for query "%s"%s', len(found), normalizedName, searchYear)
            i = 1
            for f in found:
                self.Log('    %s. %s [%s] (%s) {%s}', i, f['title'], f['url'], str(f['date']), f['thumb'])
                i += 1

        self.Log('-----------------------------------------------------------------------')
        # Walk the found items and gather extended information
        info = []
        i = 1
        for f in found:
            url = f['url']

            if re.search(r'http://www\.data18\.com/movies/.+', url) is None:
                continue

            # Get the id
            itemId = url.split('/', 4)[4]

            if len(itemId) == 0:
                continue

            self.Log('* ID is                 %s', itemId)

            title = f['title']
            thumb = f['thumb']
            date = f['date']
            year = ''

            if date is not None:
                year = date.year

            # Evaluate the score
            scorebase1 = media.name
            scorebase2 = title.encode('utf-8')

            if media.year:
                scorebase1 += ' (' + media.year + ')'
                scorebase2 += ' (' + str(year) + ')'

            score = INITIAL_SCORE - Util.LevenshteinDistance(scorebase1, scorebase2)

            self.Log('* Title is              %s', title)
            self.Log('* Date is               %s', str(date))
            self.Log('* Score is              %s', str(score))

            if score >= IGNORE_SCORE:
                info.append({'id': itemId, 'title': title, 'year': year, 'date': date, 'score': score, 'thumb': thumb})
            else:
                self.Log('# Score is below ignore boundary (%s)... Skipping!', IGNORE_SCORE)

            if i != len(found):
                self.Log('-----------------------------------------------------------------------')

            i += 1

        info = sorted(info, key=lambda inf: inf['score'], reverse=True)

        # Output the final results.
        self.Log('***********************************************************************')
        self.Log('Final result:')
        i = 1
        for r in info:
            self.Log('    [%s]    %s. %s (%s) {%s} [%s]', r['score'], i, r['title'], r['year'], r['id'], r['thumb'])
            results.Append(MetadataSearchResult(id = r['id'], name  = r['title'] + ' [' + str(r['date']) + ']', score = r['score'], thumb = r['thumb'], lang = lang))

            # If there are more than one result, and this one has a score that is >= GOOD SCORE, then ignore the rest of the results
            if not manual and len(info) > 1 and r['score'] >= GOOD_SCORE:
                self.Log('            *** The score for these results are great, so we will use them, and ignore the rest. ***')
                break
            i += 1

    def update(self, metadata, media, lang, force=False):
        self.Log('***** UPDATING "%s" ID: %s - DATA18 v.%s *****', media.title, metadata.id, VERSION_NO)

        # Make url
        url = D18_MOVIE_INFO % metadata.id

        try:
            # Fetch HTML
            html = HTML.ElementFromURL(url, sleep=REQUEST_DELAY)

            # Set tagline to URL
            metadata.tagline = url

            # Get the date
            date = self.findDateInTitle(media.title)

            # Set the date and year if found.
            if date is not None:
                metadata.originally_available_at = date
                metadata.year = date.year

            # Get the title
            metadata.title = self.getStringContentFromXPath(html, '//h1')

            # Set the summary
            paragraph = html.xpath('//div/p[b[contains(text(),"Description:")]]/.')
            if len(paragraph) > 0:
                summary = paragraph[0].text_content().strip('\n').strip()
                summary = re.sub(r'Description:', '', summary.strip())
                metadata.summary = summary

            # def getStringContentFromXPath(self, source, query):
            #     return source.xpath('string(' + query + ')')

            # Set the studio, and director
            studio_and_director = html.xpath('//p[b[contains(text(),"Studio:")]]')
            if len(studio_and_director) > 0:
                try:
                    metadata.studio = self.getStringContentFromXPath(studio_and_director[0], 'a[1]')
                    metadata.directors.clear()
                    metadata.directors.add(self.getStringContentFromXPath(studio_and_director[0], 'a[2]'))
                except:
                    Log.Error('Error obtaining data for item with id %s (%s) [%s] ', metadata.id, url, e.message)
            else:
                studio_and_director = html.xpath('//p/text()[contains(.,"Director")]/..')
                if len(studio_and_director) > 0:
                    metadata.studio = self.getStringContentFromXPath(studio_and_director[0], 'a[1]')
                    metadata.directors.clear()
                    metadata.directors.add(self.getStringContentFromXPath(studio_and_director[0], 'a[2]'))

            # Set series and add to collections
            metadata.collections.clear()
            series = html.xpath('//p[b[contains(text(),"Serie:")]]')
            if len(series) > 0:
                try:
                    metadata.collections.add(self.getStringContentFromXPath(series[0], 'a[1]'))
                except:
                    pass

            # Add the genres
            metadata.genres.clear()
            genres = html.xpath('//p[b[contains(text(),"Categories:")]]/a/text()')
            for genre in genres:
                genre = genre.strip()
                if len(genre) > 0 and re.match(r'View Complete List', genre) is None:
                    metadata.genres.add(genre)

            # Add the performers
            metadata.roles.clear()
            for performer in html.xpath('//p[@class="line1"]/a/img[@class="yborder"]'):
                role = metadata.roles.new()
                role.name = performer.get('alt').strip()

                # Get the url for performer photo
                role.photo = re.sub(r'/stars/60/', '/stars/120/', performer.get('src'))

            # Get posters and fan art.
            self.getImages(url, html, metadata, force)
        except Exception, e:
            Log.Error('Error obtaining data for item with id %s (%s) [%s] ', metadata.id, url, e.message)

        self.writeInfo('New data', url, metadata)

    def hasProxy(self):
        return Prefs['imageproxyurl'] is not None

    def makeProxyUrl(self, url, referer):
        return Prefs['imageproxyurl'] + ('?url=%s&referer=%s' % (url, referer))

    def worker(self, queue, stoprequest):
        while not stoprequest.isSet():
            try:
                func, args, kargs = queue.get(True, 0.05)
                try: func(*args, **kargs)
                except Exception, e: self.Log(e)
                queue.task_done()
            except Queue.Empty:
                continue

    def addTask(self, queue, func, *args, **kargs):
        queue.put((func, args, kargs))

    def getImages(self, url, mainHtml, metadata, force):
        queue = Queue.Queue(THREAD_MAX)
        stoprequest = Thread.Event()
        for _ in range(THREAD_MAX): Thread.Create(self.worker, self, queue, stoprequest)

        results = []

        self.addTask(queue, self.getPosters, url, mainHtml, metadata, results, force, queue)

        scene_image_max = 20
        try:
            scene_image_max = int(Prefs['sceneimg'])
        except:
            Log.Error('Unable to parse the Scene image count setting as an integer.')

        if scene_image_max >= 0:
            for i, scene in enumerate(mainHtml.xpath('//div[p//b[contains(text(),"Scene ")]]')):
                sceneName = self.getStringContentFromXPath(scene, 'p//b[contains(text(),"Scene ")]')
                sceneUrl = self.getAnchorUrlFromXPath(scene, './/a[contains(@href, "go.data18.com") and img]')
                if sceneUrl is not None:
                    #download all the images directly when they are referenced offsite
                    self.Log('Found scene (%s) - Getting art directly', sceneName)
                    self.addTask(queue, self.getSceneImagesFromAlternate, i, scene, url, metadata, scene_image_max, results, force, queue)
                    continue

                sceneUrl = self.getAnchorUrlFromXPath(scene, './/a[not(contains(@href, "download") ) and img]')
                if sceneUrl is None:
                    continue

                self.Log('Found scene (%s) - Trying to get fan art from [%s]', sceneName, sceneUrl)

                self.addTask(queue, self.getSceneImages, i, sceneUrl, metadata, scene_image_max, results, force, queue)

        queue.join()
        stoprequest.set()

        from operator import itemgetter
        for i, r in enumerate(sorted(results, key=itemgetter('scene', 'index'))):
            if r['isPreview']:
                proxy = Proxy.Preview(r['image'], sort_order=i+1)
            else:
                proxy = Proxy.Media(r['image'], sort_order=i+1)

            if r['scene'] > -1:
                metadata.art[r['url']] = proxy
            else:
                #self.Log('added poster %s (%s)', r['url'], i)
                metadata.posters[r['url']] = proxy

    def getPosters(self, url, mainHtml, metadata, results, force, queue):
        get_poster_alt = Prefs['posteralt']
        i = 0

        #get full size posters
        for poster in mainHtml.xpath('//a[substring(@title,string-length(@title) -string-length(" Cover") +1) = " Cover"]/@href'):
            #self.Log('found %s', poster)
            if 'frontback' in poster:
                continue
            if poster in metadata.posters.keys() and not force:
                continue
            self.addTask(queue, self.downloadImage, poster, poster, url, False, i, -1, results)
            i += 1
        #Check for combined poster image and use alternates if available
        if get_poster_alt and i == 0:
            self.getPosterFromAlternate(url, mainHtml, metadata, results, force, queue)
            i = len(metadata.posters)

        #Always get the lower-res poster from the main page that tends to be just the front cover.  This is close to 100% reliable
        imageUrl = self.getImageUrlFromXPath(mainHtml, '//img[@alt="Cover"]')
        self.addTask(queue, self.downloadImage, imageUrl, imageUrl, url, False, i, -1, results)


    def getSceneImages(self, sceneIndex, sceneUrl, metadata, sceneImgMax, result, force, queue):
        sceneHtml = HTML.ElementFromURL(sceneUrl, sleep=REQUEST_DELAY)
        sceneTitle = self.getStringContentFromXPath(sceneHtml, '//h1[@class="h1big"]')

        imgCount = 0
        images = sceneHtml.xpath('//a[img[contains(@alt,"image")]]/img')
        if images is not None and len(images) > 0:
            firstImage = images[0].get('src')
            thumbPatternSearch = re.search(r'(th\w*)/', firstImage)
            thumbPattern = None
            if thumbPatternSearch is not None:
                thumbPattern = thumbPatternSearch.group(1)
            #get viewer page
            firstViewerPageUrl = images[0].xpath('..')[0].get('href')
            html = HTML.ElementFromURL(firstViewerPageUrl, sleep=REQUEST_DELAY)

            imageCount = None
            imageCountSearch = re.search(r'Image \d+ of (\d+)', html.text_content())
            if imageCountSearch is not None:
                imageCount = int(imageCountSearch.group(1))
            else:
                # No thumbs were found on the page, which seems to be the case for some scenes where there are only 4 images
                # so let's just pretend we found thumbs
                imageCount = 4

            # plex silently dies or kills this off if it downloads too much stuff, especially if there are errors. have to manually limit numbers of images for now
            # workaround!!!
            if imageCount > 3:
                imageCount = 3

            # Find the actual first image on the viewer page
            imageUrl = self.getImageUrlFromXPath(html, '//div[@id="post_view"]//img')

            # Go through the thumbnails replacing the id of the previous image in the imageUrl on each iteration.
            for i in range(1,imageCount+1):
                imgId = '%02d' % i
                imageUrl = re.sub(r'\d{1,3}.jpg', imgId + '.jpg', imageUrl)
                thumbUrl = None
                if thumbPattern is not None:
                    thumbUrl = re.sub(r'\d{1,3}.jpg', imgId + '.jpg', firstImage)

                if imgCount > sceneImgMax:
                    #self.Log('Maximum background art downloaded')
                    break
                imgCount += 1

                if self.hasProxy():
                    imgUrl = self.makeProxyUrl(imageUrl, firstViewerPageUrl)
                    thumbUrl = None
                else:
                    imgUrl = imageUrl
                    thumbUrl = None

                if not imgUrl in metadata.art.keys() or force:
                    if thumbUrl is not None:
                        self.addTask(queue, self.downloadImage, thumbUrl, imgUrl, firstViewerPageUrl, True, i, sceneIndex, result)
                    else:
                        self.addTask(queue, self.downloadImage, imgUrl, imgUrl, firstViewerPageUrl, False, i, sceneIndex, result)

        if imgCount == 0:
            # Use the player image from the main page as a backup
            playerImg = self.getImageUrlFromXPath(sceneHtml, '//img[@alt="Play this Video" or contains(@src,"/hor.jpg")]')
            if playerImg is not None and len(playerImg) > 0:
                if self.hasProxy():
                    img = self.makeProxyUrl(playerImg, sceneUrl)
                else:
                    img = playerImg

                if not img in metadata.art.keys() or force:
                    self.addTask(queue, self.downloadImage, img, img, sceneUrl, False, 0, sceneIndex, result)



    #download the images directly from the main page
    def getSceneImagesFromAlternate(self, sceneIndex, sceneHtml, url, metadata, sceneImgMax, result, force, queue):
        self.Log('Attempting to get art from main page')
        i = 0
        for imageUrl in sceneHtml.xpath('.//a[not(contains(@href, "download") ) and img]/img/@src'):
            if sceneImgMax > 0 and i + 1 > sceneImgMax:
                break

            if self.hasProxy():
                imgUrl = self.makeProxyUrl(imageUrl, url)
            else:
                imgUrl = imageUrl

            if not imgUrl in metadata.art.keys() or force:
                #self.Log('Downloading %s', imageUrl)
                self.addTask(queue, self.downloadImage, imgUrl, imgUrl, url, False, i, sceneIndex, result)
                i += 1


    def getPosterFromAlternate(self, url, mainHtml, metadata, results, force, queue):
        provider = ''

        # Prefer AEBN, since the poster seems to be better quality there.
        altUrl = self.getAnchorUrlFromXPath(mainHtml, '//a[b[contains(text(),"AEBN")]]')
        if altUrl is not None:
            provider = 'AEBN'
        else:
            provider = 'Data18Store'
            altUrl = self.getAnchorUrlFromXPath(mainHtml, '//a[contains(text(),"Available for")]')


        if altUrl is not None:
            self.Log('Attempting to get poster from alternative location (%s) [%s]', provider, altUrl)

            providerHtml = HTML.ElementFromURL(altUrl, sleep=REQUEST_DELAY)
            frontImgUrl = None
            backImgUrl = None

            if provider is 'AEBN':
                frontImgUrl = self.getAnchorUrlFromXPath(providerHtml, '//div[@id="md-boxCover"]/a[1]')
                if frontImgUrl is not None:
                    backImgUrl = frontImgUrl.replace('_xlf.jpg', '_xlb.jpg')
            else:
                frontImgUrl = self.getImageUrlFromXPath(providerHtml, '//div[@id="gallery"]//img')
                if frontImgUrl is not None:
                    backImgUrl = frontImgUrl.replace('h.jpg', 'bh.jpg')

            if frontImgUrl is not None:
                if not frontImgUrl in metadata.posters.keys() or force:
                    self.addTask(queue, self.downloadImage, frontImgUrl, frontImgUrl, altUrl, False, 1, -1, results)

                if not backImgUrl is None and (not backImgUrl in metadata.posters.keys() or force):
                    self.addTask(queue, self.downloadImage, backImgUrl, backImgUrl, altUrl, False, 2, -1, results)
                return True
        return False

    def downloadImage(self, url, referenceUrl, referer, isPreview, index, sceneIndex, results):
        results.append({'url': referenceUrl, 'image': HTTP.Request(url, cacheTime=0, headers={'Referer': referer}, sleep=REQUEST_DELAY).content, 'isPreview': isPreview, 'index': index, 'scene': sceneIndex})

    ### Writes metadata information to log.
    def writeInfo(self, header, url, metadata):
        self.Log(header)
        self.Log('-----------------------------------------------------------------------')
        self.Log('* ID:              %s', metadata.id)
        self.Log('* URL:             %s', url)
        self.Log('* Title:           %s', metadata.title)
        self.Log('* Release date:    %s', str(metadata.originally_available_at))
        self.Log('* Year:            %s', metadata.year)
        self.Log('* Studio:          %s', metadata.studio)
        self.Log('* Director:        %s', metadata.directors[0] if len(metadata.directors) > 0  else '')
        self.Log('* Tagline:         %s', metadata.tagline)
        self.Log('* Summary:         %s', metadata.summary)

        if len(metadata.collections) > 0:
            self.Log('|\\')
            for i in range(len(metadata.collections)):
                self.Log('| * Collection:    %s', metadata.collections[i])

        if len(metadata.roles) > 0:
            self.Log('|\\')
            for i in range(len(metadata.roles)):
                self.Log('| * Starring:      %s (%s)', metadata.roles[i].name, metadata.roles[i].photo)

        if len(metadata.genres) > 0:
            self.Log('|\\')
            for i in range(len(metadata.genres)):
                self.Log('| * Genre:         %s', metadata.genres[i])

        if len(metadata.posters) > 0:
            self.Log('|\\')
            for poster in metadata.posters.keys():
                self.Log('| * Poster URL:    %s', poster)

        if len(metadata.art) > 0:
            self.Log('|\\')
            for art in metadata.art.keys():
                self.Log('| * Fan art URL:   %s', art)

        self.Log('***********************************************************************')

def safe_unicode(s, encoding='utf-8'):
    if s is None:
        return None
    if isinstance(s, basestring):
        if isinstance(s, types.UnicodeType):
            return s
        else:
            return s.decode(encoding)
    else:
        return str(s).decode(encoding)
