import cherryproxy
import requests
from urlparse import urlparse, parse_qs

class ProxyReferer(cherryproxy.CherryProxy):
    def filter_request_headers(self):        
        query = parse_qs(urlparse(self.req.full_url).query)
        if 'url' not in query.keys():
            self.set_response(404)
            return

        requested_url = query['url'][0]

        referer = None
        if 'referer' in query.keys():
            referer = query['referer'][0]

        response = self.makeRequest(requested_url, referer)

        if response.status_code == 304:
            self.set_response(304)
            return

        self.set_response(response.status_code, data=response.raw.read(), content_type=response.headers['content-type'])
        self.resp.headers = []
        for header in response.headers.keys():
            self.resp.headers.append((header, response.headers[header]))

    def makeRequest(self, url, referer):        
        headers = {}
        for header in self.req.headers.keys():
            if header == "host":
                continue

            headers[header] = self.req.headers[header]

        if not referer is None:
            headers['Referer'] = referer

        return requests.get(url, headers=headers, stream=True)

cherryproxy.main(ProxyReferer)