# Data18
import re
import random

# this code was borrowed from the Excalibur Films Agent. April 9 2013
# URLS
VERSION_NO = '1.2013.06.02.1'
EXC_BASEURL = 'http://www.data18.com/'
EXC_SEARCH_MOVIES = EXC_BASEURL + 'search/?t=0&k=%s'
EXC_MOVIE_INFO = EXC_BASEURL + 'movies/%s'
EXC_STAR_PHOTO = EXC_BASEURL + 'img/stars/120/%s.jpg'

titleFormats = r'DVD|Blu-Ray|BR|Combo|Pack'

def Start():
  HTTP.CacheTime = CACHE_1DAY
  HTTP.SetHeader('User-agent', 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.2; Trident/4.0; SLCC2; .NET CLR 2.0.50727; .NET CLR 3.5.30729; .NET CLR 3.0.30729; Media Center PC 6.0)')

class EXCAgent(Agent.Movies):
  name = 'Data18'
  languages = [Locale.Language.English]
  accepts_from = ['com.plexapp.agents.localmedia']
  primary_provider = True

  def search(self, results, media, lang):
    Log('Data18 Version : ' + VERSION_NO)
    Log('**************SEARCH****************')
    title = media.name
    if media.primary_metadata is not None:
      title = media.primary_metadata.title

    year = media.year
    if media.primary_metadata is not None:
      year = media.primary_metadata.year
      Log('Searching for Year: ' + year)

    Log('Searching for Title: ' + title)
    if title.startswith('The '):
      if title.count(':'):
        title = title.split(':',1)[0].replace('The ','',1) + ', The:' + title.split(':',1)[1]
      else:
        title = title.replace('The ','',1) + ', The'

    query = String.URLEncode(String.StripDiacritics(title))
    searchUrl = EXC_SEARCH_MOVIES % query
    Log('Search url: ' + searchUrl)
    searchResults = HTML.ElementFromURL(searchUrl)
    searchTitle = searchResults.xpath('//title')[0].text_content()
    years = searchResults.xpath(
      '//i[re:match(text(), "\d+-\d+-\d+")]',
      namespaces={"re": "http://exslt.org/regular-expressions"})

    count = 0
    for movie in searchResults.xpath('//a[.//img[@class="yborder"]]'):
      movieHREF = movie.get("href").strip()
      movieName = searchResults.xpath('//a[@href="' + movieHREF + '"]//img[@class="yborder"]')[0] 
      curName = movieName.get('title').strip()
      curID = movie.get('href').split('/',4)[4]
      curID = curID.rstrip('/')
      try:
        curdate = years[count].text_content().strip(',. ')
        curyear = re.sub(r'([-]\d{2})','',curdate).strip(' ')
        score = 100 - Util.LevenshteinDistance(title.lower(), curName.lower()) - Util.LevenshteinDistance(year, curyear)
      except (IndexError):
        score = 100 - Util.LevenshteinDistance(title.lower(), curName.lower())
        curyear = ''
        curdate = ''
      if score >= 45:
        if curName.count(', The'):
          curName = 'The ' + curName.replace(', The','',1)
        if curdate:
          curName = curName + ' [' + curdate + ']'

        Log('Found:')
        Log('    Date: ' + curdate)
        Log('    ID: ' + curID)
        Log('    Title: ' + curName)
        Log('    URL: ' + movieHREF)
        results.Append(MetadataSearchResult(id = curID, name = curName, score = score, lang = lang))
      count += 1
    results.Sort('score', descending=True)

  def update(self, metadata, media, lang):
    Log('Data18 Version : ' + VERSION_NO)
    Log('**************UPDATE****************')
    html = HTML.ElementFromURL(EXC_MOVIE_INFO % metadata.id)
    coversextension = metadata.id + "/covers.html"
    coversURL = EXC_MOVIE_INFO % coversextension
    covershtml = HTML.ElementFromURL(coversURL)
    metadata.title = re.sub(titleFormats,'',media.title).strip(' .-+')

    Log('Current:')
    Log('    Title: ' + metadata.title)
    Log('    ID: ' + metadata.id)    
    Log('    Release Date: ' + str(metadata.originally_available_at))
    Log('    Year: ' + str(metadata.year))

    for key in metadata.posters.keys():
      Log('    PosterURLs: ' + key)

    # Release Date
    try:
      release_date_group = re.search(r'(\d+-\d+-\d+)', metadata.title)
      release_date = release_date_group.group(0)
      metadata.originally_available_at = Datetime.ParseDate(release_date).date()
      metadata.year = metadata.originally_available_at.year
      metadata.title = re.sub(r'\[\d+-\d+-\d+\]','',metadata.title).strip(' ')
      Log('Title Updated')
      Log('Release Date Sequence Updated')
    except: pass

    # Get Posters
    i = 1
    try:
      posterimg = covershtml.xpath('//img[@alt="front cover"]')[0]
      posterUrl = posterimg.get('src').strip()
      metadata.posters[posterUrl] = Proxy.Media(HTTP.Request(posterUrl, headers={'Referer': coversURL}).content,sort_order=i)
      i += 1
      Log('Poster-Front Sequence Updated')
    except: pass
    try:
      posterimg = covershtml.xpath('//img[@alt="back cover"]')[0]
      posterUrl = posterimg.get('src').strip()
      metadata.posters[posterUrl] = Proxy.Media(HTTP.Request(posterUrl, headers={'Referer': coversURL}).content,sort_order=i)
      i += 1
      Log('Poster-Back Sequence Updated')
    except: pass
    Log (' i = ' + str(i))
    if i == 1:
      Log (' i = ' + str(i))
      try:
        img = html.xpath('//img[@class="yborder" and @alt="Enlarge Cover" and contains(@src, "/covers/")]')[0]
        thumbUrl = img.get('src')
        metadata.posters[thumbUrl] = Proxy.Media(HTTP.Request(thumbUrl, headers={'Referer': EXC_MOVIE_INFO % metadata.id}).content,sort_order=i)
        i += 1
        posterimg = covershtml.xpath('//img[@alt="cover"]')[0]
        posterUrl = posterimg.get('src').strip()
        metadata.posters[posterUrl] = Proxy.Media(HTTP.Request(posterUrl, headers={'Referer': coversURL}).content,sort_order=i)
        Log('Poster-Front-Back-Combined Sequence Updated')
      except: pass
    
    # Get Art
    # Get First Photo Set Pic if available
    i = 1
    try:
      photoSetIndex = 0
      imageURL =  html.xpath('//img[contains(@alt,"image")]/..')[photoSetIndex].get('href')
      imagehtml = HTML.ElementFromURL(imageURL)
      if 'content' in imageURL:
        photoSetIndex = random.randint(0,len(html.xpath('//img[contains(@alt,"image")]/..'))-1)
        imageURL =  html.xpath('//img[contains(@alt,"image")]/..')[photoSetIndex].get('href')
        imagehtml = HTML.ElementFromURL(imageURL)
        photoSetIndex = 0
        imageURL =  imagehtml.xpath('//img[contains(@alt,"image")]/..')[photoSetIndex].get('href')
        imagehtml = HTML.ElementFromURL(imageURL)       
      posterimg = imagehtml.xpath('//img[@alt= "image"]')[0]
      posterUrl = posterimg.get('src').strip()
      Log('imageUrl: ' + posterUrl)
      metadata.art[posterUrl] = Proxy.Media(HTTP.Request(posterUrl, headers={'Referer': imageURL}).content, sort_order = i)
      i += 1
      #Random PhotoSet image incase first image isn't desired
      photoSetIndex = random.randint(1,len(html.xpath('//img[contains(@alt,"image")]/..'))-1)
      imageURL =  html.xpath('//img[contains(@alt,"image")]/..')[photoSetIndex].get('href')
      imagehtml = HTML.ElementFromURL(imageURL)
      if 'content' in imageURL:
        photoSetIndex = random.randint(1,len(imagehtml.xpath('//img[contains(@alt,"image")]/..'))-1)
        imageURL =  imagehtml.xpath('//img[contains(@alt,"image")]/..')[photoSetIndex].get('href')
        imagehtml = HTML.ElementFromURL(imageURL)
      posterimg = imagehtml.xpath('//img[@alt= "image"]')[0]
      posterUrl = posterimg.get('src').strip()
      Log('imageUrl: ' + posterUrl)
      metadata.art[posterUrl] = Proxy.Media(HTTP.Request(posterUrl, headers={'Referer': imageURL}).content, sort_order = i)
      i += 1
      Log('Art - Photoset - Sequence Updated')
    except: pass

    # Genre.
    try:
      metadata.genres.clear()
      genres = html.xpath('//div[@class="gen12"]//a[contains(@href, ".html")]')
      if len(genres) > 0:
        for genreLink in genres:
          genreName = genreLink.text_content().strip('\n')
          if len(genreName) > 0 and re.match(r'View Complete List', genreName) is None:
            metadata.genres.add(genreName)
      Log('Genre Sequence Updated')
    except: pass

    # Summary.
    try:
      metadata.summary = ""
      summary = html.xpath('//p[@class="gen12" and @style="margin-top: 3px;"]')
      if len(summary) > 0:
        for paragraph in summary:
          metadata.summary = metadata.summary + paragraph.text_content().replace('&13;', '').strip('. \t\n\r"') + "\n\n"
        metadata.summary.strip('\n')
      else:
        metadata.summary = html.xpath('//font[@color="000000"]')[0].text_content().replace('&13;', '').strip(' \t\n\r"')
      metadata.summary = re.sub(r'Description:','',metadata.summary)
      Log('Summary Sequence Updated')
    except: pass

    # Starring
    try:
      starring = html.xpath('//p[@class="line1"]//img[@class="yborder"]')
      metadata.roles.clear()
      for member in starring:
        role = metadata.roles.new()
        role.actor = member.get('alt').strip()
        role.photo = html.xpath('//p[@class="line1"]//img[@class="yborder" and @alt="' + role.actor + '"]')[0].get('src')
        Log('Member Photo Url : ' + role.photo)
      Log('Starring Sequence Updated')
    except: pass

    # Director
    try:
      director = html.xpath('//p[contains(., "Director:")]//a[@rel="nofollow"]')[0].text_content().strip()
      metadata.directors.clear()
      metadata.directors.add(director)
      Log('Director Sequence Updated')
    except: pass

    # Studio
    try:
      metadata.studio = html.xpath('//p[contains(., "Studio:")]//a[contains(@href,"data18.com/studios/")]')[0].text_content().strip()
      Log('Studio Sequence Updated')
    except: pass

    # Collection
    try:
      collection = html.xpath('//a[contains(text(),"Series")]')[0].text_content().strip()
      metadata.collections.clear ()      
      metadata.collections.add (collection)
      Log('Collection Sequence Updated')
    except: pass

   # Tagline
    try:
      metadata.tagline = EXC_MOVIE_INFO % metadata.id
      Log('Tagline Sequence Updated')
    except: pass


    Log('Updated:')
    Log('    Title:...............' + metadata.title)
    Log('    ID:..................' + metadata.id)
    Log('    Release Date:........' + str(metadata.originally_available_at))
    Log('    Year:................' + str(metadata.year))
    Log('    TagLine:.............' + str(metadata.tagline))
    Log('    Studio:..............' + str(metadata.studio))

    try:
      for key in metadata.posters.keys():
        Log('    PosterURLs:..........' + key)
    except: pass
    try:
      for key in metadata.art.keys():
        Log('    BackgroundArtURLs:...' + key)
    except: pass
    try:
      for x in range (len(metadata.collections)):
        Log('    Network:.............' + metadata.collections[x])
    except: pass
    try:
      for x in range (len(metadata.roles)):
        Log('    Starring:............' + metadata.roles[x].actor)
    except: pass

    try:
      for x in range (len(metadata.genres)):
        Log('    Genres:..............' + metadata.genres[x])
    except: pass
