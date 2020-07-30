from tldextract import tldextract

EMAIL_RGX = r'''(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])'''


def filter_scraped_links(keywords, url_list):
    output = []
    for url in url_list:
        url = get_root_url(url)
        for keyword in keywords:
            if keyword in url:
                output.append(url)
                break
    return output


def get_root_url(url):
    x = tldextract.extract(url)
    if x.subdomain:
        output = f'{x.subdomain}.{x.domain}.{x.suffix}'
    else:
        output = f'{x.domain}.{x.suffix}'
    if 'https' in url:
        output = 'https://' + output
    else:
        output = 'http://' + output
    return output


if __name__ == '__main__':
    root = get_root_url('https://www.expertise.com/co/denver/lawn-service')
    print(root)
