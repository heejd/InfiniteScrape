import ipaddress
import json
import random
import sys
import threading
import time

import fake_useragent
import js2py
import requests
import urllib3.exceptions
from bs4 import BeautifulSoup

ua = fake_useragent.UserAgent()


def verify_ip(ip: str):
    """
    Check if a given IP is valid
    :param ip:
    :return: is it valid?
    """
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def verify_port(port: str | int):
    """
    Check if a port is valid.
    :param port:
    :return: is it valid?
    """
    if type(port) is int:
        return port > 0
    else:
        return port.isnumeric()


def craft(one: str, two: str, proxy=None, timeout: int = 15, session: requests.Session | None = None):
    """
    This function, using the proxy IP passed, will attempt to craft two elements together
    :param session:
    :param one:
    :param two: The second element to craft
    :param proxy: The proxy IP
    :param timeout: The amount of time to wait (maximum)
    :return: None if the attempt failed, or the JSON if it succeeded.
    """

    # Request headers
    headers = {
        'User-Agent': ua.random,
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://neal.fun/infinite-craft/',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-GPC': '1',
    }

    # Parameters
    params = {
        'first': one,
        'second': two,
    }


    # Proxy
    proxy_argument = {"https": proxy.parsed}

    try:
        # Are we using a session?
        if session is None:
            getter = requests
        else:
            getter = session


        response: requests.Response = getter.get('https://neal.fun/api/infinite-craft/pair', params=params,
                                                 headers=headers,
                                                 proxies=proxy_argument, verify=False, timeout=(timeout, timeout * 2))

    # Catch errors
    except requests.exceptions.ConnectTimeout:
        return {"status": "error", "type": "connection"}  # Failure
    except requests.exceptions.ConnectionError as e:
        return {"status": "error", "type": "connection"}  # Failure
    except requests.exceptions.ReadTimeout:
        return {"status": "error", "type": "read"}  # Failure
    except urllib3.exceptions.ProtocolError:
        return {"status": "error", "type": "read"}  # :(
    except requests.exceptions.ChunkedEncodingError:
        return {"status": "error", "type": "read"}  # :(((
    except requests.exceptions.RequestException:
        return {"status": "error", "type": "read"}  # :((((((((((
    string_response: str = response.content.decode('utf-8')  # Format byte response
    if "Retry-After" in response.headers:
        return {"status": "error", "type": "ratelimit", "penalty": int(response.headers["Retry-After"])}
    try:
        json_resp: dict = json.loads(string_response)
    except json.JSONDecodeError:  # If the response received was invalid return a ReadTimeout penalty
        return {"status": "error", "type": "read"}  # Failure

    json_resp.update(
        {"status": "success", "time_elapsed": response.elapsed.total_seconds()})  # Add success field before returning

    return json_resp


def score_proxy(p):
    """
    Get a number representing the usefulness of the proxy based on its data. Higher is better.
    :param p: The proxy to score
    :return: The score of the proxy
    """

    salt = random.random()/5
    if p.disabled_until > time.time():  # INVALID PROXY WOOT WOOT
        return -100 + salt
    if p.worker is not None:
        return -100 + salt  # We can't use the proxy anyway :(
    if p.ip is None:
        return 100  # No proxy - very fast - high priority
    if p.total_submissions == 0:
        return 0 + salt

    if p.average_response != 0:
        return (1 / p.average_response) * (p.total_successes / p.total_submissions) + salt
    # Only possible case for this is a proxy that (a) has never functioned (b) whose timeout has expired
    # and (c) whose status is -1. Send unchecked in this case.
    return 0 + salt


def rank_proxies(proxies: list):
    """
    Rank the proxies from best to worst
    :return:
    """
    ranked = sorted(proxies, key=score_proxy, reverse=True)
    return ranked


class ImprovedThread(threading.Thread):
    """
    A very similar version of threading.Thread that returns the value of the thread process
    with Thread.join().
    This allows for batch processing to work.

    It also prints exceptions when they are thrown.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the ImprovedThread
        :param args:
        :param kwargs:
        """
        super().__init__(*args, **kwargs)
        self.result = None

    def run(self):
        """
        Run the ImprovedThread.
        :return:
        """
        if self._target is None:
            return  # could alternatively raise an exception, depends on the use case
        try:
            self.result = self._target(*self._args, **self._kwargs)
        except Exception as exc:
            print(f'{type(exc).__name__}: {exc}', file=sys.stderr)  # properly handle the exception
            raise exc

    def join(self, *args, **kwargs):
        """
        The highlight of the class. Returns the thread result upon ending.
        :param args:
        :param kwargs:
        :return:
        """
        super().join(*args, **kwargs)
        return self.result


def get_proxies():
    """
    This function is really complex. Here's how it works:

    1. gets the proxy list from spys
    2. obtains the randomly generated variables used for the hidden port numbers
    3. goes through each proxy and gets the calculation for the port number
    4. performs the calculation
    5. saves data

    This monstrosity could have been avoided if they had just let me scrape.


    This is what you get.
    :return:
    """
    proxies = []
    proxies_doc = (requests.get('https://spys.one/en/socks-proxy-list',
                               headers={"User-Agent": ua.random, "Content-Type": "application/x-www-form-urlencoded"})
                   .text)

    # Get the parser
    soup = BeautifulSoup(proxies_doc, 'html.parser')
    tables = list(soup.find_all("table"))  # Get ALL the tables

    # Variable definitions
    variables_raw = str(soup.find_all("script")[6]).replace('<script type="text/javascript">', "").replace('</script>',
                                                                                                           '').split(
        ';')[:-1]

    # Define the variables
    variables = {}
    for var in variables_raw:
        name = var.split('=')[0]
        value = var.split("=")[1]
        if '^' not in value:
            variables[name] = int(value)
        else:
            prev_var = variables[var.split("^")[1]]
            variables[name] = int(value.split("^")[0]) ^ int(prev_var)  # Gotta love the bit math


    # Get each row of the giant table
    trs = tables[2].find_all("tr")[2:]
    for tr in trs:
        # Try to find the area where the IP and encoded port are
        address = tr.find("td").find("font")

        if address is None:  # This row doesn't have an IP/port on it
            continue

        # I've blanked out the sheer amount of weirdness that happens here
        raw_port = [i.replace("(", "").replace(")", "") for i in
                    str(address.find("script")).replace("</script>", '').split("+")[1:]]


        # Calculate the prot
        port = ""
        for partial_port in raw_port:
            first_variable = variables[partial_port.split("^")[0]]
            second_variable = variables[partial_port.split("^")[1]]
            port += "(" + str(first_variable) + "^" + str(second_variable) + ")+"
        port = js2py.eval_js('function f() {return "" + ' + port[:-1] + '}')()

        proxies.append(
            {"ip": address.get_text(), "port": port, "protocol": "socks5h"})
    proxies.append({"ip": None, "port": None, "protocol": "socks5h"})  # The "local" worker

    return proxies


def parse_crafts_into_tree(raw_crafts):
    """
    Parse raw crafts into a craft tree.
    :param raw_crafts: the input crafts
    :return: the parsed tree
    """
    out = {}

    for c in raw_crafts:
        input_craft = c[0]

        output_result = c[1]
        key = output_result["result"] + "`" + output_result["emoji"]
        if key not in out.keys():
            out.update({key: [input_craft]})
        else:
            if input_craft not in out[key] and [input_craft[1], input_craft[0]] not in out[key]:
                out[key].append(input_craft)
    return out
