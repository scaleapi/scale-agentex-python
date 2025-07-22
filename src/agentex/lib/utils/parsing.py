from urllib.parse import urlsplit, urlunsplit


def remove_query_params(url):
    split_url = urlsplit(url)
    scheme, netloc, path, query, fragment = split_url

    if query:
        query = ''
    else:
        amp_index = path.find('&')
        if amp_index != -1:
            path = path[:amp_index]

    return urlunsplit((scheme, netloc, path, query, fragment))
