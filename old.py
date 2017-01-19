"""scraper.py

Scrapes subreddits for images and stuff.

TODO:
    - Rehaul the code to be more functional? Maybe use a more OO approach.
    - Logging improvements (VERBOSE logging levels)
    - Filtering for upvotes
    - Filtering for hosts
    - Log unsupported hosts
    - Trim: "https://i.imgur.com/YwFLa4g.jpg?..", or "https://i.imgur.com/bIiSUzK.jpg?8"
    - Function to purge folder
    - Add support for streamable
    - log failures to a file
    - more modularity, be able to pass a object to a downloader
    - support multi reddits
    - use search: 'https://www.reddit.com/r/funny/search?q=(and ups:800..)&syntax=cloudsearch&restrict_sr=on&sort=new'
    - special handling for albums

"""

import time
import os

import praw
import requests

from functools import partial
from pprint import pprint

from imgurpython import ImgurClient
from slugify import slugify


imgur = ImgurClient(
    client_id=os.getenv('IMGUR_CLIENT_ID')
    client_secret=os.getenv('IMGUR_CLIENT_SECRET')
)

reddit = praw.Reddit(
    client_id=os.getenv('REDDIT_CLIENT_ID')
    client_secret=os.getenv('REDDIT_CLIENT_SECRET')
    user_agent='this is a test app:{'.format(os.getenv('REDDIT_USERNAME')
)


# choices: all, day, hour, month, week, year
DEFAULT_SORT = 'top'
DEFAULT_TIME_FILTER = 'hour'
DEFAULT_LIMIT = 1000

IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif']

MAX_FILENAME_LENGTH = 200

class ScraperException(Exception):
    pass


def parse_imgur_url(imgur_url):
    """Parse a Imgur link and return image data about the link.

    Possible link formats:
    - http://imgur.com/BCR6f68 (Image ID URL)
    - http://i.imgur.com/uHc6jXh.jpg (Direct Image URL)
    - http://imgur.com/a/Jjnmu (Album ID URL)
    """
    images = []

    if 'imgur.com/a/' in imgur_url or 'imgur.com/gallery' in imgur_url:
        # parse album (strip id from end of the URL)
        for image in imgur.get_album(imgur_url.split('/')[-1]).images:
            images.append({
                'title': image['title'] if image['title'] else '',
                'link': image['link'],
                'extension': image['link'].split('.')[-1]
            })
    elif 'i.imgur.com' in imgur_url:
        # use the direct image URL
        images.append({
            'title': '',
            'link': imgur_url,
            'extension': imgur_url.split('.')[-1]
        })
    elif 'imgur.com' in imgur_url and '.' in imgur_url.split('/')[-1]:
        # for special cases like 'http://imgur.com/uxgHsCA.jpg'
        images.append({
            'title': '',
            'link': imgur_url,
            'extension': imgur_url.split('.')[-1]
        })
    else:
        # construct direct image URL if it is a "new" Imgur URL
        image = imgur.get_image(imgur_url.split('/')[-1])
        images.append({
            #'title': image.title,
            'title': image.title if image.title else '',
            'link': image.link,
            'extension': image.link.split('.')[-1]
        })

    return images


def get_reddituploads_file_type(redditupload_url):
    """Re-request an i.reddituploads.com link to find the right file type."""

    image_resp = requests.get(redditupload_url)
    extension = image_resp.headers['content-type'].split('/')[-1]

    return extension


def scrape_subreddit(subreddit_name,
    sort_type=DEFAULT_SORT,
    time_filter=DEFAULT_TIME_FILTER,
    limit=DEFAULT_LIMIT):

    subreddit = reddit.subreddit(subreddit_name)

    # make a folder
    image_dir = 'r-{}'.format(subreddit_name)
    if not os.path.exists(image_dir):
        os.makedirs(image_dir)

    # validate 'sort_type' parameter
    if not getattr(subreddit, sort_type, None):
        raise ScraperException(
            'You used an invalid sort type: {sort_type}'.format(sort_type))

    # use getattr to get the appropriate 'sort_type' function
    submissions_f = partial(getattr(subreddit, sort_type), limit=limit)

    if sort_type == 'top':
        submissions_f(time_filter=time_filter)

    submissions = submissions_f()

    for submission in submissions:
        try:
            images = [{
                'title': '',
                'link': '',
                'extension': '',
            }]
            if 'imgur' in submission.url:
                images = parse_imgur_url(submission.url)
            elif 'reddituploads' in submission.url:
                images[0]['link'] = submission.url
                images[0]['extension'] = get_reddituploads_file_type(submission.url)
            elif 'i.redd.it' in submission.url:
                images[0]['link'] = submission.url
                images[0]['extension'] = submission.url.split('.')[-1]
            elif any(extension in submission.url for extension in IMAGE_EXTENSIONS):
                images[0]['link'] = submission.url
                images[0]['extension'] = submission.url.split('.')[-1]
            else:
                print('unknown type for submission url: {url}'.format(url=submission.url))

                # using the submission ID you can visit something like
                # https://www.reddit.com/r/<subreddit>/comments/<submission.id>
                # and you will be redirected to the actual submission (HTTP 301)
                # print(submission.id, submission.title)
                continue

            for image in images:
                image['filename'] = slugify(submission.title,
                    separator='_',
                    max_length=MAX_FILENAME_LENGTH,
                    save_order=True,
                    word_boundary=True
                )

        except:
            print('failed to get submission url: {url}'.format(url=submission.url))
            print('submission subreddit: {subreddit_name} id: {id}'.format(
                subreddit_name=subreddit_name,
                id=submission.id))
            continue

        # TODO: special handling for albums!
        for image in images:
            image_data = requests.get(image['link']).content
            with open('{image_dir}/[{post_id}][{ups}] {filename}.{extension}'.format(
                image_dir=image_dir,
                post_id=submission.id,
                ups=submission.ups,
                filename=image['filename'] if image['filename'] else 'fooobar',
                extension=image['extension']),
                'wb') as handler:

                handler.write(image_data)


def generate_download_link(submission):
    raise NotImplementedError

def generate_filename(submission):
    raise NotImplementedError


if __name__ == '__main__':
    scrape_subreddit(
        subreddit_name='pics',
        sort_type='hot',
        time_filter='hour',
        limit=200
)
