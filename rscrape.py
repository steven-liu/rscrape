import os
import string

from pprint import pprint

import praw
import requests
import tqdm

from imgurpython import ImgurClient
from slugify import slugify


reddit = praw.Reddit(
    client_id=os.getenv('REDDIT_CLIENT_ID'),
    client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
    user_agent='this is a test app:{}'.format(os.getenv('REDDIT_USERNAME'))
)

imgur = ImgurClient(
    client_id=os.getenv('IMGUR_CLIENT_ID'),
    client_secret=os.getenv('IMGUR_CLIENT_SECRET')
)


class Result:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):
        return '<Result {data}>'.format(data=self.__dict__)


class Extractor:
    """Extract download info from a reddit submission."""

    class ExtractionError(Exception):
        pass

    class InvalidFormatError(Exception):
        pass

    def __init__(self, raise_exceptions=False, clean_urls=True):
        self.raise_exceptions = raise_exceptions
        self.clean_urls = clean_urls

    def clean_url(self, url, strip_chars=string.punctuation + string.digits):
        return url.strip(strip_chars)

    def slugify(self, url):
        return slugify(url,
            separator='_',
            max_length=200,
            save_order=True,
            word_boundary=True
        )

    def validate_link(self, submission):
        raise NotImplementedError

    def extract_link(self, submission):
        raise NotImplementedError

    def extract(self, submission):
        if not self.validate_link(submission):
            if self.raise_exceptions:
                raise InvalidFormatError(
                    'Could not validate link from submission "{submission_id}"'
                    'using {extractor_type}'.format(
                        submission_id=submission.id,
                        extractor_type=self.__class__.__name__
                ))
            else:
                return
            
        url = self.clean_url(submission.url) if self.clean_urls else submission.url
        try:
            link = self.extract_link(submission, url)
        except:
            if raise_exceptions:
                raise ExtractionError(
                    'Could not extract link from submission "{submission_id}"'
                    'using {extractor_type}'.format(
                        submission_id=submission.id,
                        extractor_type=self.__class__.__name__
                ))
        return link


class RedditExtractor(Extractor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def validate_link(self, submission):
        return 'https://i.reddituploads.com' in submission.url \
            or 'https://i.redd.it' in submission.url

    def extract_link(self, submission, url):
        extension = self.get_file_extension(submission.url)

        return Result(
            reddit_id=submission.id,
            title=self.slugify(submission.title),
            link=submission.url,
            extension=self.get_file_extension(submission.url)
        )

    def get_file_extension(self, url):
        image_resp = requests.get(url)
        extension = image_resp.headers['content-type'].split('/')[-1]
        return extension


class GfycatExtractor(Extractor):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_url = 'https://gfycat.com/cajax/get/{gfycat_id}'

    def validate_link(self, submission):
        return 'https://gfycat.com' in submission.url

    def extract_link(self, submission, url):
        gfycat_id = submission.url.split('/')[-1]
        resp = requests.get(self.api_url.format(gfycat_id=gfycat_id))
        if resp.ok:
            data = resp.json()
            if data.get('gfyItem'):
                return Result(
                    reddit_id=submission.id,
                    title=self.slugify(submission.title),
                    link=data.get('gfyItem').get('mp4Url'),
                    extension='mp4'
                )
            else:
                raise ExtractionError(
                    'Failed to extract gfycat "{gfycat_id}" error: {error}'.format(
                        gfycat_id = gfycat_id,
                        error = data.get('error')
                    )
                )
        raise ExtractionError('Failed to query gfycat API')


class DefaultExtractor(Extractor):

    def __init__(self, *args, **kwargs):
        super(DefaultExtractor, self).__init__(*args, **kwargs)
        if kwargs.get('extensions'):
            self.extensions = kwargs['extensions']
        else:
            self.extensions = ['jpeg', 'jpg', 'png', 'gif']

    def validate_link(self, submission):
        return any([submission.url.endswith(e) for e in self.extensions])

    def extract_link(self, submission, url):
        return Result(
            reddit_id=submission.id,
            title=self.slugify(submission.title),
            link=submission.url,
            extension=submission.url.split('.')[-1],
        )


class ImgurAlbumExtractor(Extractor):

    def __init__(self, *args, **kwargs):
        super(ImgurAlbumExtractor, self).__init__(*args, **kwargs)


class ImgurExtractor(Extractor):

    def __init__(self, *args, **kwargs):
        super(ImgurExtractor, self).__init__(*args, **kwargs)
    
    def validate_link(self, submission):
        return 'imgur.com' in submission.url
    
    def parse_extension(self, imgur_type):
        return imgur_type.split('/')[-1]

    def extract_link(self, submission, url):
        image = imgur.get_image(submission.url.split('/')[-1])
        return Result(
            reddit_id=submission.id,
            title=submission.title,
            link=image.link,
            extension=self.parse_extension(image.type)
        )


class Downloader:
    def __init__(self, dir):
        self.dir = dir

    def _download(self, result):
        """Download a list of Result objects.

        This shouldn't be called directly.
        """
        filename = '[{reddit_id}] {title}.{extension}'.format(**dict(
            reddit_id=result.reddit_id,
            title=result.title,
            extension=result.extension
        ))

        dl = requests.get(result.link, stream=True)
        with open('{dir}/{filename}'.format(
            dir=self.dir, filename=filename), 'wb') as f:
            dl_iter = dl.iter_content(chunk_size=1024)

            content_length = int(dl.headers.get('Content-Length', 0))
            num_chunks = content_length // 1024
    
            for chunk in tqdm.tqdm(dl_iter, total=num_chunks, unit='KB'):
                if chunk:
                    f.write(chunk)
                else:
                    break

    def download(self, results):
        """Download a list of Result objects."""
        self.ensure_dir()
        for result in results:
            self._download(result)

    def ensure_dir(self):
        if not os.path.exists(self.dir):
            os.makedirs(self.dir, exist_ok=True)


def scrape():
    gfycats = reddit.subreddit('gfycats').hot(limit=5)
    trees = reddit.subreddit('pics').hot(limit=50)

    d = DefaultExtractor()
    e = GfycatExtractor()
    i = ImgurExtractor()
    r = RedditExtractor()

    extractors = [d, e, i, r]

    results = []
    invalid = []
    for submission in gfycats:
        for extractor in extractors:
            result = extractor.extract(submission)
            if result:
                results.append(result)
                break
        if not result:
            invalid.append(submission.url)


    dl = Downloader('test')
    dl.download(results)

    pprint(invalid)


if __name__ == '__main__':
    scrape()