from aiohttp import ClientSession
import asyncio
from bs4 import BeautifulSoup
from python_rucaptcha import ImageCaptcha

from config import RUCAPTCHA_API_KEY, D_INFORM_LOGIN, D_INFORM_PASSWORD

url = "http://client.d-inform.com"
headers = {
	'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
	'Accept-Encoding': 'gzip, deflate',
	'Accept-Language': 'en-US, en;',
	'Cache-Control': 'max-age = 0',
	'Connection': 'keep-alive',
	'Content-Type': 'application/x-www-form-urlencoded',
	'Host': 'client.d-inform.com',
	'Origin': 'http://client.d-inform.com',
	'Referer': 'http://client.d-inform.com/fileboard.php',
	'Upgrade-Insecure-Requests': '1',
	'User-Agent': 'Mozilla/5.0(X11; Linux x86_64) AppleWebKit/537.36(KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36'
}


async def save_captcha(session, captcha_url):
	async with session.get(f"{url}/{captcha_url}", headers=headers) as response:
		with open('captcha.gif', 'wb') as file:
			file.write(await response.read())


async def resolve_captcha(img_url):
	user_answer = await ImageCaptcha \
		.aioImageCaptcha(rucaptcha_key=RUCAPTCHA_API_KEY,
	                     service_type='rucaptcha') \
		.captcha_handler(captcha_file='captcha.gif')

	if user_answer['errorId'] == 0:
		return user_answer['captchaSolve']
	else:
		return await resolve_captcha(img_url)


async def d_inform_login(session, captcha):
	payload = {
		'user': D_INFORM_LOGIN,
		'password': D_INFORM_PASSWORD,
		'keystring': captcha,
		'submit': 'Войти'
	}
	return await session.post(f"{url}/fileboard.php", data=payload, headers=headers)


def get_d_inform_files_list(soup):
	return


async def get_ftp_files_list():
	return


async def main():
	async with ClientSession() as session:

		async with session.get(f"{url}/fileboard.php", headers=headers) as login_page:
			soup = BeautifulSoup(await login_page.text(), "lxml")

			captcha_img = soup.find("img")
			await save_captcha(session, captcha_img['src'])

			captcha = soup.find('img')
			captcha_text = await resolve_captcha(captcha['src'])

			main_page = await d_inform_login(session, captcha_text)

			main_page_soup = await main_page.text()

			with open('response.html', 'w') as file:
				file.write(main_page_soup)

			d_inform_files_list = get_d_inform_files_list(main_page_soup)
			for i in d_inform_files_list:
				print(i)
			# ftp_files_list = await get_ftp_files_list()


if __name__ == "__main__":
	event_loop = asyncio.get_event_loop()
	event_loop.run_until_complete(main())
	event_loop.close()
