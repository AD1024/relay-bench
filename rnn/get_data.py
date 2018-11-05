import unicodedata

DATA_URL = 'https://download.pytorch.org/tutorial/data.zip'
DATA_PATH = 'data'

ALL_LETTERS = string.ascii_letters + " .,;'"

# Turn a Unicode string to plain ASCII, thanks to http://stackoverflow.com/a/518232/2809427
def unicode_to_ascii(s):
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
        and c in ALL_LETTERS
    )

def get_data():
    if not os.path.exists(DATA_PATH):
        resp = requests.get(DATA_URL)
        with open('data.zip', 'wb') as zip_file:
            zip_file.write(resp.content)

        zip_file = zipfile.ZipFile('data.zip')
        zip_file.extractall('.')

    languages = {}
    for language in glob.glob(os.path.join(DATA_PATH , 'names', "*")):
        with open(language, encoding='utf-8') as language_file:
            category = os.path.splitext(os.path.basename(language))[0]
            lines = language_file.read().strip().split('\n')
            names = [unicode_to_ascii(line) for line in lines]
            languages[category] = names

    return languages
