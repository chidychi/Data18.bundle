# Data18
import re, types, traceback

# URLS
VERSION_NO = '1.2013.07.24.1'
D18_BASE_URL = 'http://www.data18.com/'
D18_MOVIE_INFO = D18_BASE_URL + 'movies/%s'
D18_SEARCH_URL = D18_BASE_URL + 'search/?t=2&k=%s&b=1'
D18_STAR_PHOTO = D18_BASE_URL + 'img/stars/120/%s.jpg'

REQUEST_DELAY = 0       # Delay used when requesting HTML, may be good to have to prevent being banned from the site

INITIAL_SCORE = 100     # Starting value for score before deductions are taken.
GOOD_SCORE = 98         # Score required to short-circuit matching and stop searching.
IGNORE_SCORE = 45       # Any score lower than this will be ignored.

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
        return Datetime.ParseDate(string).date()

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
            date = self.getDateFromString(self.getStringContentFromXPath(r, 'i/text()'))
            title = self.getStringContentFromXPath(r, 'a[2]')
            murl = self.getAnchorUrlFromXPath(r, 'a[2]')
            thumb = self.getImageUrlFromXPath(r, 'a/img')

            found.append({'url': murl, 'title': title, 'date': date, 'thumb': thumb})

        return found

    def search(self, results, media, lang, manual=False):
        # Clean up year.
        if media.year:
            searchYear = u' (' + safe_unicode(media.year) + u')'
        else:
            searchYear = u''

        # Normalize the name
        normalizedName = String.StripDiacritics(media.name)
        if len(normalizedName) == 0:
            normalizedName = media.name

        self.Log('***** SEARCHING FOR "%s"%s - DATA18CONTENT v.%s *****', normalizedName, searchYear, VERSION_NO)

        # Make the URL
        searchUrl = D18_SEARCH_URL % (String.Quote((normalizedName).encode('utf-8'), usePlus=True))
        found = self.doSearch(searchUrl)

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

            # Get the id
            itemId = url[:-1].split('/', 4)[4]

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
            self.Log('    [%s]    %s. %s (%s) [%s]', r['score'], i, r['title'], r['id'], r['thumb'])
            results.Append(MetadataSearchResult(id = r['id'], name  = r['title'] + ' [' + str(r['date']) + ']', score = r['score'], thumb = r['thumb'], lang = lang))

            # If there are more than one result, and this one has a score that is >= GOOD SCORE, then ignore the rest of the results
            if not manual and len(info) > 1 and r['score'] >= GOOD_SCORE:
                self.Log('            *** The score for this result is great, so we will use it, and ignore the rest. ***')
                break
            i += 1

    def update(self, metadata, media, lang):
        self.Log('***** UPDATING "%s" ID: %s - DATA18CONTENT v.%s *****', media.title, metadata.id, VERSION_NO)

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
            metadata.title = self.getStringContentFromXPath(html, '//h1[@class="h1big"]')

            # Set the summary
            paragraph = html.xpath('//p[b[contains(text(),"Description:")]]')
            if len(paragraph) > 0:
                summary = paragraph[0].text_content().strip('\n').strip()
                summary = re.sub(r'Description:', '', summary.strip())
                metadata.summary = summary

            # Set the studio and series
            studio_and_series = html.xpath('//p[b[contains(text(),"Studio:")]]')
            if len(studio_and_series) > 0:
                metadata.studio = self.getStringContentFromXPath(studio_and_series[0], 'a[1]')
                metadata.collections.clear()
                metadata.collections.add(self.getStringContentFromXPath(studio_and_series[0], 'a[2]'))

            # Add the genres
            metadata.genres.clear()
            genres = html.xpath('//div[b[contains(text(),"Categories:")]]/a/text()')
            for genre in genres:
                genre = genre.strip()
                if len(genre) > 0 and re.match(r'View Complete List', genre) is None:
                    metadata.genres.add(genre)

            # Add the director
            director = html.xpath('//p[b[contains(text(),"Director:")]]/a/text()')
            if len(director) > 0:
                metadata.directors.clear()
                metadata.directors.add(director[0].strip())

            # Add the performers
            metadata.roles.clear()
            for performer in html.xpath('//p[@class="line1"]/a/img[@class="yborder"]'):
                role = metadata.roles.new()
                role.actor = performer.get('alt').strip()

                # Get the url for performer photo
                role.photo = performer.get('src')

            # Get posters and fan art.
            self.getImages(url, html, metadata)
        except Exception, e:
            Log.Error('Error obtaining data for item with id %s (%s) [%s] ', metadata.id, url, e.message)

        self.writeInfo('New data', url, metadata)

    def getImages(self, url, mainHtml, metadata):
        proxies = []

        posterPageUrl = self.getAnchorUrlFromXPath(mainHtml, '//a[img[@alt="Enlarge Cover"]]')
        posterHtml = HTML.ElementFromURL(posterPageUrl, sleep=REQUEST_DELAY)
        i = 1
        skipNormalPoster = False

        get_poster_alt = Prefs['posteralt']
        if get_poster_alt and len(posterHtml.xpath('//div[@id="post_view2"]')) > 0:
            skipNormalPoster = True

            if self.getPosterFromAlternate(url, mainHtml, metadata):
                i += 1

        if not skipNormalPoster:
            for poster in posterHtml.xpath('//div[@id="post_view"]/img/@src'):
                if poster in metadata.posters.keys():
                    continue

                metadata.posters[poster] = Proxy.Media(HTTP.Request(poster, cacheTime = 0, headers = {'Referer': posterPageUrl}, sleep=REQUEST_DELAY), sort_order = i)
                i += 1

        scene_image_count = 0
        try:
            scene_image_count = int(Prefs['sceneimg'])
        except:
            Log.Error('Unable to parse the Scene image count setting as an integer.')

        if scene_image_count < 0:
            return

        i = 1
        for scene in mainHtml.xpath('//div[p//b[contains(text(),"Scene ")]]'):
            sceneName = self.getStringContentFromXPath(scene, 'p//b[contains(text(),"Scene ")]')
            sceneUrl = self.getAnchorUrlFromXPath(scene, './/a[not(contains(@href, "download")) and img]')

            if sceneUrl is None:
                continue

            self.Log('Found scene (%s) - Trying to get fan art from [%s]', sceneName, sceneUrl)

            sceneHtml = HTML.ElementFromURL(sceneUrl, sleep=REQUEST_DELAY)
            sceneTitle = self.getStringContentFromXPath(sceneHtml, '//h1[@class="h1big"]')
            firstImageUrl = self.getAnchorUrlFromXPath(sceneHtml, '//a[img[@alt="image 1"]]')

            if firstImageUrl is not None:
                self.Log('Scene is "%s" - Found link to image viewer to be [%s]', sceneTitle, firstImageUrl)

                imageViewerHtml = HTML.ElementFromURL(firstImageUrl, sleep=REQUEST_DELAY)

                # Find the actual image
                imageUrl = self.getImageUrlFromXPath(imageViewerHtml, '//div[@id="post_view"]//img')

                # Go through the thumbnails replacing the id of the previous image in the imageUrl on each iteration.
                prev = None
                j = 1
                for thumb in imageViewerHtml.xpath('//div[a[@href="' + firstImageUrl + '"]]/a'):
                    thumbTarget = thumb.get('href')
                    imgId = thumbTarget[-2:]

                    if prev is not None:
                        imageUrl = imageUrl.replace('/' + prev + '.jpg', '/' + imgId + '.jpg')

                    prev = imgId
                    order = i
                    i += 1

                    if scene_image_count > 0:
                        if j > scene_image_count:
                            break
                        j += 1

                    if imageUrl in metadata.art.keys():
                        continue

                    self.Log('Found image (%s) [%s]', sceneTitle, imageUrl)
                    proxies.append((imageUrl, Proxy.Media(HTTP.Request(imageUrl, cacheTime = 0, headers = { 'Referer': thumbTarget }, sleep=REQUEST_DELAY), sort_order = order)))

            # Use the player image from the scene page as a backup
            playerImg = self.getImageUrlFromXPath(sceneHtml, '//img[@alt="Play this Video"]')
            if playerImg is not None:
                if not playerImg in metadata.art.keys():
                    proxies.append((playerImg, Proxy.Media(HTTP.Request(playerImg, cacheTime = 0, headers = { 'Referer': url }, sleep=REQUEST_DELAY), sort_order = i + 999)))

        for proxy in proxies:
            metadata.art[proxy[0]] = proxy[1]

    def getPosterFromAlternate(self, url, mainHtml, metadata):
        provider = ''

        # Prefer AEBN, since the poster seems to be better quality there.
        altUrl = self.getAnchorUrlFromXPath(mainHtml, '//a[b[contains(text(),"AEBN")]]')
        if altUrl is not None:
            provider = 'AEBN'
        else:
            provider = 'Data18Store'
            altUrl = self.getAnchorUrlFromXPath(mainHtml, '//a[b[contains(text(),"Official Store")]]')


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
                if not frontImgUrl in metadata.posters.keys():
                    metadata.posters[frontImgUrl] = Proxy.Media(HTTP.Request(frontImgUrl, cacheTime = 0, headers = {'Referer': altUrl}, sleep=REQUEST_DELAY), sort_order = 1)

                if not backImgUrl is None and not backImgUrl in metadata.posters.keys():
                    metadata.posters[backImgUrl] = Proxy.Media(HTTP.Request(backImgUrl, cacheTime = 0, headers = {'Referer': altUrl}, sleep=REQUEST_DELAY), sort_order = 2)
                return True
        return False

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
                self.Log('| * Starring:      %s (%s)', metadata.roles[i].actor, metadata.roles[i].photo)

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