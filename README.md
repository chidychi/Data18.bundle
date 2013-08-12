# Data18 metadata agent

This metadata agent will receive data from [Data18.com](http://www.data18.com/).

To get the best results, follow the [standard plex naming convention for movies](http://wiki.plexapp.com/index.php/Media_Naming_and_Organization_Guide#Movie_Content).

A few options are available from the agent configuration:
* **Ouput debugging info in logs** - This is for debugging purposes. Off by default.
* **Allow alternate poster source if Data18 poster is not split in front/back** - Some of the posters provided on Data18 seems to be a combination of front/back which is not very good for our purposes, so enabling this setting will allow the agent to go to alternate sources, if they are found on the movie page. This can either be AEBN or the Data18 store, where AEBN is preferred.
* **Fan art scene image count (-1 = none, 0 = all)** The agent can follow links to scenes from the movie page, and download scene images to use as fan art. By default this is set to 0 meaning that it will get all images. Setting it to -1 will disable the functionality, and setting it to any other positive value will limit the number of images from each scene to the given number.
* **Image proxy url** - The images on Data18 are not receivable without a proper referer in the request. This means that we cannot use the preview functionality that Plex provides, so we cannot use thumbnail previews. This setting specifies a URL to a proxy that can be used to add a referer to the request. If this URL is not specified, the images will be downloaded without thumbnails (note that this is alot slower, and will take up more harddisk space). See below for more information.

## Image proxy

The included `referer-proxy.py` can be used to allow getting images where a referer is required, by providing it in the URL.
The proxy is built using [CherryProxy](http://www.decalage.info/python/cherryproxy) and [Requests](http://docs.python-requests.org/en/latest/).
See those pages for installation instructions.

Once the prerequisites are installed, run the proxy with this command:

`python referer-proxy.py -a HOST -p PORT`

Replace HOST and PORT with appropriate values (eg. HOST = 0.0.0.0, PORT = 1234)

The proxy will not run as a daemon. I'll let people more familiar with python assist with that part.