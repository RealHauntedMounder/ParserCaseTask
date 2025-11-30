import requests
from bs4 import BeautifulSoup
import urllib.parse
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = 'https://magbo.ru'

headers = {
    "User-Agent": "Mozilla/5.0"
}

def parse_product(product_url):
    product_html = requests.get(product_url, headers=headers)
    product_soup = BeautifulSoup(product_html.text, 'html.parser')

    name = product_soup.find('h1')
    name = name.get_text(strip=True) if name else None

    price = product_soup.find('span', class_='price_value')
    price = price.get_text(strip=True) if price else None

    old_price = product_soup.find('span', class_='discount')
    old_price = old_price.get_text(strip=True) if old_price else None

    article = None
    manufacturer = None
    availability = None

    for item in product_soup.find_all("div", class_="properties__item"):
        title = item.find("div", class_="properties__title")
        value = item.find("div", class_="properties__value")

        if not title or not value:
            continue

        if "Артикул" in title.get_text(strip=True):
            article = value.get_text(strip=True)
            break


    for row in product_soup.find_all("tr", class_="js-prop-replace"):
        title = row.find("span", class_="js-prop-title")
        if not title:
            continue

        if "Производитель" in title.get_text(strip=True):
            value_tag = row.find("span", class_="js-prop-value")

            if value_tag:
                a = value_tag.find("a")
                if a:
                    manufacturer = a.get_text(strip=True)
                else:
                    manufacturer = value_tag.get_text(strip=True)

            break


    stock_row = product_soup.find("div", class_="quantity_block_wrapper")
    if stock_row:
        value_span = stock_row.find("span", class_="value")
        if value_span:
            text = value_span.get_text(strip=True).lower()

            if "в наличии" in text:
                availability = "В наличии"
            else:
                availability = "Нет в наличии"

    return {
        "Название товара": name,
        "Цена со скидкой": price,
        "Цена без скидки": old_price,
        "Артикул": article,
        "Производитель": manufacturer,
        "Доступность": availability,
        "Ссылка на товар": product_url
    }

def search_and_parse(request1):
    encoded = urllib.parse.quote(request1)
    base_search_url = f"{BASE_URL}/catalog/?q={encoded}&s=Найти"

    page = 1
    product_urls = []

    while True:
        url = base_search_url if page == 1 else f"{base_search_url}&PAGEN_2={page}"
        print(f"[+] Парсинг страницы {page}: {url}")

        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        cards = soup.select("div.inner_wrap.TYPE_1")

        for card in cards:
            a = card.find("a", href=True)
            if a:
                product_urls.append(BASE_URL + a["href"])

        # ПРОВЕРКА: есть ли ссылка на следующую страницу?
        next_page = soup.find("a", class_="dark_link", string=str(page+1))
        if not next_page:
            print("[-] Больше страниц нет\n")
            break

        page += 1

    print(f"[✓] Всего товаров найдено: {len(product_urls)}")
    return product_urls

def save_to_csv(items, filename="data.csv"):
    fieldnames = items[0].keys()

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(items)

    print(f"\nДанные сохранены в файл: {filename}")





def main():
    mode = input("Выберите режим:\n1 - Поиск по запросу\n2 - Прямые ссылки\n> ")
    urls = []

    if mode == "1":
        requests_raw = input("Введите запрос или несколько через запятую: ")

        urls = []
        for req in requests_raw.split(","):
            req = req.strip()
            if not req:
                continue

            print(f"\n=== Поиск по запросу: '{req}' ===")
            found = search_and_parse(req)
            urls.extend(found)

        if not urls:
            print("Ничего не найдено")
            return


        urls = list(set(urls))



    elif mode == "2":

        links = input("Введите ссылки через запятую:\n> ")

        urls = []

        for url in links.split(","):

            url = url.strip()

            if not url:
                continue


            if not url.startswith("http"):
                print(f"[!] Пропущено: {url} — неверный формат ссылки")

                continue


            if "/catalog/detail/" not in url:
                print(f"[!] Пропущено: {url} — это не карточка товара")

                continue


            try:

                r = requests.get(url, headers=headers, timeout=10)

                if r.status_code != 200:
                    print(f"[!] Пропущено: {url} — страница недоступна ({r.status_code})")

                    continue


                soup = BeautifulSoup(r.text, "html.parser")

                if not soup.find("h1"):
                    print(f"[!] Пропущено: {url} — не похоже на страницу товара")

                    continue


            except Exception as e:

                print(f"[!] Пропущено: {url} — ошибка при запросе: {e}")

                continue

            urls.append(url)

        if not urls:
            print("\n Нет валидных ссылок. Завершение.")

            return

    else:
        print("Неверный режим.")
        return

    items = []

    print(f"\n Запуск парсинга в 20 потоков...\n")

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(parse_product, url): url for url in urls}

        for future in as_completed(futures):
            url = futures[future]
            try:
                data = future.result()
                items.append(data)
                print(f"[✓] Готово: {url}")
            except Exception as e:
                print(f"[!] Ошибка при обработке {url}: {e}")

    save_to_csv(items)

if __name__ == "__main__":
    main()



