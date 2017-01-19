import praw
import requests
from pprint import pprint

reddit = praw.Reddit(
    client_id=os.getenv('REDDIT_CLIENT_ID')
    client_secret=os.getenv('REDDIT_CLIENT_SECRET')
    user_agent='this is a test app:{'.format(os.getenv('REDDIT_USERNAME')
)


class Result:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):
        return '<Result {data}>'.format(data=self.__dict__)


class ExtractionError(Exception):
    pass


class InvalidFormatError(Exception):
    pass


class Extractor:

    def __init__(self, raise_on_format_error=False):
        self.raise_on_format_error = raise_on_format_error

    def validate_link(self, submission):
        raise NotImplementedError

    def extract_link(self, submission):
        raise NotImplementedError

    def extract(self, submission):
        if not self.validate_link(submission):
            if self.raise_on_format_error:
                raise InvalidFormatError(
                    'Could not validate submission {}'.format(submission.id))
            else:
                return
        return self.extract_link(submission)


class RedditUploads(Extractor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def validate_link(self, submission):
        return 'https://i.reddituploads.com' in submission.url \
            or 'https://i.redd.it' in submission.url

    def extract_link(self, submission):
        extension = self.get_file_extension(submission.url)

        return Result(
            reddit_id=submission.id,
            title=submission.title,
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

    def extract_link(self, submission):
        gfycat_id = submission.url.split('/')[-1]
        resp = requests.get(self.api_url.format(gfycat_id=gfycat_id))
        if resp.ok:
            data = resp.json()
            if data.get('gfyItem'):
                return Result(
                    reddit_id=submission.id,
                    title=submission.title,
                    link=data.get('gfyItem').get('mp4Url'),
                    extension='mp4'
                )
            else:
                raise ExtractionError(
                    'gfycat id: {gfycat_id} extraction error: {error}'.format(
                        gfycat_id = gfycat_id,
                        error = data.get('error')
                    )
                )
        raise ExtractionError('failed to query gfycat API')


class ImageExtractor(Extractor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if kwargs.get('extensions'):
            self.extensions = kwargs['extensions']
        else:
            self.extensions = ['jpeg', 'jpg', 'png', 'gif']

    def validate_link(self, submission):
        return any([submission.url.endswith(e) for e in self.extensions])

    def extract_link(self, submission):
        return Result(
            reddit_id=submission.id,
            title=submission.title,
            link=submission.url,
            extension=submission.url


gfycats = list(reddit.subreddit('gfycats').hot(limit=5))
trees = list(reddit.subreddit('trees').hot(limit=5))

e = GfycatExtractor(raise_on_format_error=False)
r = RedditUploads(raise_on_format_error=False)

pprint([e.extract(g) for g in gfycats])
pprint([r.extract(t) for t in trees])
