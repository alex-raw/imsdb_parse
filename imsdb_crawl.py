import os
from requests import get
from bs4 import BeautifulSoup

def get_links(url):
    page = BeautifulSoup(get(url).content, 'html.parser')
    return [link.get('href') for link in page.find_all('a')]

def crawl_titles(url, subdir):
    titles = []
    for link in get_links(url):
        if subdir in link:
            titles.append(link)
    return titles

def crawl_episodes(url, subdir):
    titles = []
    for show in crawl_titles(url, '/TV/'):
        episodes = crawl_titles(url + show, subdir)
        titles = titles + episodes
    return titles

def build_path(url, old_dir, new_dir):
    return url.replace(old_dir, new_dir) \
              .replace(' Script', '') \
              .replace(' ', '-')

def get_script_urls():
    url = 'https://www.imsdb.com/'
    movie_dir, tv_dir = 'Movie Scripts/', 'TV Transcripts/'
    movies = crawl_titles(url + 'all-scripts.html', movie_dir)
    series = crawl_episodes(url, tv_dir)
    movies = [url + build_path(movie, movie_dir, 'scripts/')
              for movie in movies]
    series = [url + build_path(episode, tv_dir, 'transcripts/')
              for episode in series]
    return movies + series

def download_scripts(force=False):
    if not os.path.exists('data'):
        os.makedirs('data')

    urls = get_script_urls()
    ln = len(urls)

    for count, url in enumerate(urls):
        filename = 'data/' + url.split('/')[-1]

        if not force and os.path.exists(filename):
            print(f"{filename} exists. skipped")
            continue

        print(f"\r...downloading ({count}/{ln})", end="")

        with get(url, stream=True) as page:
            if page.status_code in [400, 404]:
                print(f"{filename} doesn't exist")
                continue
            with open(filename, 'wb') as f:
                for chunk in page.iter_content(chunk_size=8192):
                    f.write(chunk)

download_scripts()

