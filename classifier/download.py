from duckduckgo_search import ddg_images
from fastcore.all import *
from fastdownload import download_url
from fastai.vision.all import *
from time import sleep


def search_images(term, max_images=100):
    print(f"Searching for '{term}'")
    return L(ddg_images(term, max_results=max_images)).itemgot('image')

searches = 'ok hand gesture', 'peace hand gesture'
path = Path('ok_or_peace')

for o in searches:
    dest = (path/o)
    dest.mkdir(exist_ok=True, parents=True)
    urls = search_images(f'{o} photo')
    print(f"Number of images for '{o}': {len(urls)}")
    download_images(dest, urls=urls)
    sleep(10)  # Pause between searches to avoid over-loading server
    resize_images(path/o, max_size=400, dest=path/o)

failed = verify_images(get_image_files(path))
failed.map(Path.unlink)
len(failed)
