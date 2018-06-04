import asyncio
from ftplib import FTP
from pathlib import Path
import hashlib
from asyncio import sleep

from aiohttp import ClientSession
from bs4 import BeautifulSoup
from python_rucaptcha import ImageCaptcha
from rarfile import RarFile

from config import RUCAPTCHA_API_KEY, \
    D_INFORM_LOGIN, D_INFORM_PASSWORD, \
    FTP_URL, FTP_USER, FTP_PASSWORD, FTP_DIR, URL

headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US, en;',
    'Cache-Control': 'max-age = 0',
    'Connection': 'keep-alive',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Host': 'client.d-inform.com',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0(X11; Linux x86_64) AppleWebKit/537.36(KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36'
}


class WrongCaptcha(Exception):
    pass


async def save_captcha(session, captcha):
    async with session.get(f"{URL}/{captcha['src']}", headers=headers) as response:
        with open('captcha.gif', 'wb') as file:
            file.write(await response.read())


async def resolve_captcha():
    user_answer = await ImageCaptcha \
        .aioImageCaptcha(rucaptcha_key=RUCAPTCHA_API_KEY,
                         service_type='rucaptcha') \
        .captcha_handler(captcha_file='captcha.gif')

    if user_answer['errorId'] == 0:
        return user_answer['captchaSolve']
    else:
        return await resolve_captcha()


def analyze_login_response(page_text):
    if page_text.find("Неверный проверочный код") != -1:
        raise WrongCaptcha()


async def d_inform_login(session, login_page):
    captcha_img = BeautifulSoup(login_page, "lxml").find('img')
    await save_captcha(session, captcha_img)
    captcha_text = await resolve_captcha()
    payload = {
        'user': D_INFORM_LOGIN,
        'password': D_INFORM_PASSWORD,
        'keystring': captcha_text,
        'submit': 'Войти'
    }
    response = await session.post(f"{URL}/fileboard.php", data=payload, headers=headers)
    response_text = await response.text()
    with open('response.html', 'w') as file:
        file.write(response_text)
    try:
        analyze_login_response(response_text)
        return response
    except WrongCaptcha:
        return await d_inform_login(session, login_page)


def get_d_inform_files_list(soup):
    file_names = []
    table = soup.find("table")
    for form in table.find_all("form"):
        file_names.append(form.tr.td.input.next_sibling.next_sibling['value'])

    return file_names


async def get_ftp_files_list():
    with FTP(FTP_URL) as ftp:
        ftp.login(user=FTP_USER, passwd=FTP_PASSWORD)
        ftp.cwd(FTP_DIR)
        return ftp.nlst()


def check_archive(archive_name):
    with RarFile(archive_name) as archive:
        pass


async def load_files(set_for_loading, session):
    """ Загрузка выполняется путём отправки POST-запроса с
    параметрами [username, md5(password), filename]
    """
    m = hashlib.md5()
    m.update(D_INFORM_PASSWORD.encode('utf-8'))
    archives_dir = Path("archives")
    for file_name in set_for_loading:
        file_form = {
            'user': D_INFORM_LOGIN,
            'password': m.hexdigest(),
            'file': file_name
        }
        async with session.post(f"{URL}/fileboard.php", data=file_form, headers=headers) as resp:
            with open(archives_dir / file_name, 'wb') as file:
                async for data, end_of_http_chunk in resp.content.iter_chunks():
                    file.write(data)
            # check_archive(archives_dir / file_name)


def load_archives_to_ftp():
    archives_dir = Path("archives")
    with FTP(FTP_URL) as ftp:
        ftp.login(user=FTP_USER, passwd=FTP_PASSWORD)
        ftp.cwd(FTP_DIR)
        ftp.set_debuglevel(2)
        for archive_name in archives_dir.iterdir():
            with open(archive_name, "rb") as file:
                ftp.storbinary("STOR " + str(archive_name), file)


async def main():
    async with ClientSession() as session:
        async with session.get(f"{URL}/fileboard.php", headers=headers) as login_page:
            main_page = await d_inform_login(session, await login_page.text())

            main_page_soup = BeautifulSoup(await main_page.text(), 'lxml')

            d_inform_files_list = get_d_inform_files_list(main_page_soup)
            ftp_files_list = await get_ftp_files_list()

            set_for_loading = set(d_inform_files_list) - set(ftp_files_list)
            await load_files(set_for_loading, session)

            load_archives_to_ftp()

            for entry in Path('archives').iterdir():
                entry.unlink()


if __name__ == "__main__":
    event_loop = asyncio.get_event_loop()
    event_loop.run_until_complete(main())
    event_loop.close()
