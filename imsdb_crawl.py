import os
from itertools import chain
import asyncio
import aiohttp
import aiofiles
import requests
from bs4 import BeautifulSoup


def get_titles(url, subdir):
    page = BeautifulSoup(requests.get(url).content, 'html.parser')
    for link in page.find_all('a'):
        link = link.get('href')
        if subdir in link:
            yield link


def build_path(url, title, old_dir, new_dir):
    return url + title.replace(old_dir, new_dir) \
              .replace(' Script', '') \
              .replace(' ', '-') \
              .replace(':', '') \
              .replace('&', '%2526')


def get_script_urls():
    url = 'https://www.imsdb.com/'
    movie_dir, tv_dir = 'Movie Scripts/', 'TV Transcripts/'

    movies = [build_path(url, movie, movie_dir, 'scripts/')
              for movie in get_titles(url + 'all-scripts.html', movie_dir)]
    series = [get_titles(url + show, tv_dir) for show in get_titles(url, 'TV/')]
    series = [build_path(url, episode, tv_dir, 'transcripts/')
              for episode in chain(*series)]
    return movies + series


async def download_script(url, session, outdir='data'):
    if not os.path.exists(outdir):
        os.makedirs(outdir)

    title = url.split('/')[-1]
    filename = os.path.join(outdir, title)

    async with session.get(url) as page:
        if page.status in [400, 404]:
            print(f"...skipping {url}: doesn't exist")
        else:
            data = await page.content.read()
            async with aiofiles.open(filename, 'wb') as outfile:
                await outfile.write(data)
                print(f"{url} written")


async def main():
    async with aiohttp.ClientSession() as session:
        await asyncio.gather(
            *[download_script(url, session) for url in get_script_urls()]
        )


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
