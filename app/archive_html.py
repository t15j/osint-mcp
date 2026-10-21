"""Safe, bounded extraction of archived HTML pages, without resource loading."""
from html.parser import HTMLParser

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = []
        self.parts = []
        self.links = []
        self.ignored = 0
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript', 'svg'):
            self.ignored += 1
        if tag == 'title':
            self.in_title = True
        if tag == 'a' and len(self.links) < 40:
            href = dict(attrs).get('href', '')
            if isinstance(href, str) and href.startswith(('https://', 'http://')):
                self.links.append(href[:400])

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript', 'svg') and self.ignored:
            self.ignored -= 1
        if tag == 'title':
            self.in_title = False

    def handle_data(self, data):
        value = ' '.join(data.split())
        if not value or self.ignored:
            return
        if self.in_title:
            self.title.append(value)
        elif sum(map(len, self.parts)) < 12000:
            self.parts.append(value)

    def result(self):
        body = ' '.join(self.parts)
        return {'title': ' '.join(self.title)[:300], 'text': body[:12000],
                'links': self.links, 'text_truncated': len(body) > 12000}
