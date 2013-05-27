# Data18-Content
import re

# this code was borrowed from the Excalibur Films Agent. April 9 2013
# URLS
VERSION_NO = '1.2013.05.22.1'
EXC_BASEURL = 'http://www.data18.com/'
EXC_SEARCH_MOVIES = EXC_BASEURL + 'search/?k=%s&t=0'
EXC_MOVIE_INFO = EXC_BASEURL + 'content/%s'

titleFormats = r'DVD|Blu-Ray|BR|Combo|Pack'

def Start():
  HTTP.CacheTime = CACHE_1DAY
  HTTP.SetHeader('User-agent', 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.2; Trident/4.0; SLCC2; .NET CLR 2.0.50727; .NET CLR 3.5.30729; .NET CLR 3.0.30729; Media Center PC 6.0)')

class EXCAgent(Agent.Movies):
  name = 'Data18-Content'
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

    query = String.URLEncode(String.StripDiacritics(title.replace('-','')))
    searchUrl = EXC_SEARCH_MOVIES % query
    Log('search url: ' + searchUrl)
    searchResults = HTML.ElementFromURL(searchUrl)
    searchTitle = searchResults.xpath('//title')[0].text_content()
    count = 0
    for movie in searchResults.xpath('//div[@class="gen"]//p[@class="gen12"]//a[contains(@href,"update")]'):
      movieHREF = movie.get("href").strip()
      Log('MovieHREF: ' + movieHREF)     
      curName = movie.text_content().strip()
      Log('newTitle: ' + curName)
      curID = movie.get('href').split('/',4)[4]
      Log('newID: ' + curID)
      try:
        movieResults = HTML.ElementFromURL(movieHREF)
        curyear = movieResults.xpath('//p[contains(text(),"Release date")]//a')[0].get('href')
        curyear_group = re.search(r'(\d{8})',curyear)
        curdate = curyear_group.group(0)
        curdate = Datetime.ParseDate(curdate).date()
        curyear = str(curdate.year)
        curmonth = str(curdate.month)
        curday = str(curdate.day)
        #curdate = curyear + "-" + curmonth + "-" + curday 
        curdate = str(curdate)
        Log('Found Date = ' + curdate)
        score = 100 - Util.LevenshteinDistance(title.lower(), curName.lower()) - Util.LevenshteinDistance(year, curyear)
        Log('It Worked ************************************************************')
      except (IndexError):
        score = 100 - Util.LevenshteinDistance(title.lower(), curName.lower())
        curyear = ''
        curdate = ''
      if score >= 45:
        if curName.count(', The'):
          curName = 'The ' + curName.replace(', The','',1)
        if curdate:
          curName = curName + ' [' + curdate + ']'

        #Log('Found:')
        #Log('    Date: ' + curdate)
        #Log('    ID: ' + curID)
        #Log('    Title: ' + curName)
        #Log('    URL: ' + movieHREF)
        results.Append(MetadataSearchResult(id = curID, name = curName, score = score, lang = lang))
      count += 1
    results.Sort('score', descending=True)

  def update(self, metadata, media, lang):
    Log('Data18 Version : ' + VERSION_NO)
    Log('**************UPDATE****************')
    contentURL = EXC_MOVIE_INFO % metadata.id
    html = HTML.ElementFromURL(contentURL)
    metadata.title = re.sub(titleFormats,'',media.title).strip(' .-+')

    Log('Current:')
    Log('    Title: ' + metadata.title)
    Log('    ID: ' + metadata.id)
    Log('    Release Date: ' + str(metadata.originally_available_at))
    Log('    Year: ' + str(metadata.year))
    Log('    URL: ' + contentURL)
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

    # Get Official Poster if available
    i = 1
    try:
      posterimg = html.xpath('//img[@alt="poster"]')[0]
      posterUrl = posterimg.get('src').strip()
      Log('Official posterUrl: ' + posterUrl)
      metadata.posters[posterUrl] = Proxy.Media(HTTP.Request(posterUrl, headers={'Referer': contentURL}).content, sort_order = i)
      i += 1
      Log('Poster Sequence Updated')
    except: pass

    # Get First Photo Set Pic if available
    try:
      imageURL =  html.xpath('//img[contains(@alt,"image")]/..')[0].get('href')
      imagehtml = HTML.ElementFromURL(imageURL)
      posterimg = imagehtml.xpath('//img[@alt= "image"]')[0]
      posterUrl = posterimg.get('src').strip()
      Log('imageUrl: ' + posterUrl)
      metadata.posters[posterUrl] = Proxy.Media(HTTP.Request(posterUrl, headers={'Referer': imageURL}).content, sort_order = i)
      i += 1
      Log('Poster - Photoset - Sequence Updated')
    except: pass

    # Get alternate Poster - Video
    try:
      posterimg = html.xpath('//div//a//img[@alt="Play this Video"]')[0]
      posterUrl = posterimg.get('src').strip()
      Log('Video Postetr Url: ' + posterUrl)
      metadata.posters[posterUrl] = Proxy.Media(HTTP.Request(posterUrl, headers={'Referer': contentURL}).content)
      Log('Video Poster Sequence Updated')
    except: pass

    # Get Art
    try:
      posterimg = html.xpath('//div//a//img[@alt="Play this Video"]')[0]
      posterUrl = posterimg.get('src').strip()
      Log('ArtUrl: ' + posterUrl)
      metadata.art[posterUrl] = Proxy.Media(HTTP.Request(posterUrl, headers={'Referer': contentURL}).content)
      Log('Art Sequence Updated')
    except: pass

    # Genre.
    try:
      metadata.genres.clear()
      genres = html.xpath('//*[b[contains(text(),"Categories:")]]//a[contains(@href, ".html")]')
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
      paragraph = html.xpath('//*[b[contains(text(),"Story:")]]')[0]
      metadata.summary = paragraph.text_content().replace('&13;', '').strip(' \t\n\r"') + "\n\n"
      metadata.summary.strip('\n')
      metadata.summary = re.sub(r'Story:','',metadata.summary)
      Log('Summary Sequence Updated')
    except: pass

    # Starring
    starring = html.xpath('//*[b[contains(text(),"Starring:")]]//a[@class="bold"]')
    metadata.roles.clear()
    for member in starring:
      try:
        role = metadata.roles.new()
        role.actor = member.text_content().strip()
        photo = member.get('href').strip()
        photohtml = HTML.ElementFromURL(photo)
        role.photo = html.xpath('//a[@href="' + photo + '"]//img')[0].get('src')
        Log('Member Photo Url : ' + role.photo)
      except: pass
    Log('Starring Sequence Updated')

    # Studio
    try:
      metadata.studio = html.xpath('//*[contains(text(), "Site:")]//a[contains(@href,"data18.com/sites/")]')[0].text_content().strip()
      Log('Studio Sequence Updated')
    except: pass

    # Collection
    try:
      collection = html.xpath('//*[contains(text(), "Network:")]//a[contains(@href,"data18.com/sites/")]')[0].text_content().strip()
      metadata.collections.clear ()
      metadata.collections.add (collection)
      Log('Collection Sequence Updated')
    except: pass

    Log('Updated:')
    Log('    Title: ' + metadata.title)
    Log('    ID: ' + metadata.id)
    Log('    Release Date: ' + str(metadata.originally_available_at))
    Log('    Year: ' + str(metadata.year))

    for key in metadata.posters.keys():
      Log('    PosterURLs: ' + key)


