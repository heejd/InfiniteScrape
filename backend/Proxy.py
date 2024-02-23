import logging
import time

# from backend.Worker import Worker
from backend.exceptions import *
from backend.tools import *

# Protocols
SOCKS5 = "socks5h"
SOCKS4 = "socks4h"
HTTPS = "https"
PROTOCOLS = [SOCKS5, SOCKS4, HTTPS]

# Valid states

UNCHECKED = 0
VALID = 1
INVALID = -1

# Penalties

CONNECTION_PENALTY = 300  # 5 minutes if we can't connect
READ_PENALTY = 60  # 1 minute if we can't read the data


class Proxy:
    def __init__(self, ip: str | None, port: str | int | None, protocol: str, log_level: int = logging.INFO):

        if protocol not in PROTOCOLS:  # Ensure protocol validity
            raise InvalidProxyProtocol(f"The protocol {protocol} isn't valid! Expected one of: {' ,'.join(PROTOCOLS)}")

        if ip is not None or port is not None:
            self.local = False
            if not verify_ip(ip):  # Ensure IP validity
                raise InvalidProxyIP(f"The provided IP address ({ip}) isn't valid!")

            if not verify_port(port):  # Ensure port validity
                raise InvalidProxyPort(f"The provided port ({port}) isn't valid!")
        else:
            self.local = True
        self.ip = ip
        self.protocol = protocol
        if self.local:
            self.port = None
        else:
            self.port = str(port)
        self.worker = None  # The worker using this proxy
        self.disabled_until = 0  # The time that the code should be disabled to (0 is not disabled)
        self.status = UNCHECKED
        self.average_response = 0
        self.total_submissions = 0
        self.total_successes = 0
        if self.local:
            self.parsed = None
        else:
            self.parsed = self.protocol + "://" + self.ip + ":" + self.port
        self.logger = logging.getLogger(f"Proxy({self.parsed})")
        self.logger.setLevel(log_level)

    def submit(self, success: bool, time_elapsed: float | int | None = 0, did_connect: bool = True, did_respond: bool = True, retry_after=0):
        self.logger.debug(f"Received proxy use submission: success: {success}, time_elapsed: {time_elapsed},"
                          f" did_connect: {did_connect}, did_respond: {did_respond}, retry_after: {retry_after}")
        if success:
            if self.total_successes == 0:
                self.average_response = time_elapsed
                self.total_submissions += 1
                self.total_successes = 1
                self.status = VALID
            else:
                total_seconds = self.average_response * self.total_successes
                new_total_seconds = total_seconds + time_elapsed
                self.total_submissions += 1
                self.total_successes += 1
                self.average_response = new_total_seconds / self.total_successes
        else:
            self.status = INVALID
            self.total_submissions += 1
            if did_connect and not did_respond:  # ReadTimeout
                if retry_after == 0:
                    self.disabled_until = time.time() + READ_PENALTY
                else:
                    self.disabled_until = time.time() + retry_after
            elif not did_connect:  # ConnectionTimeout
                self.disabled_until = time.time() + CONNECTION_PENALTY
            else:
                self.disabled_until = time.time() + CONNECTION_PENALTY  # Default penalty

    def withdraw(self, w):
        """

        :param w:
        :return:
        """

        if self.worker == w:
            self.logger.debug(f"Worker {str(w)} successfully withdrew!")
            self.worker = None
            return True
        self.logger.debug(f"Worker {str(w)} was unable to withdraw (lock held by worker {self.worker})")
        return False

    def grab(self, w):
        if self.worker is None:
            self.logger.debug(f"Worker {str(w)} successfully connected!")
            self.worker = w
            return True
        self.logger.debug(f"Worker {str(w)} was unable to connect (lock held by worker {self.worker})")
        return False

    def __eq__(self, other):
        if self.ip == other.ip and self.protocol == other.protocl and self.port == other.port:
            return True
        return False

    def __str__(self):
        if self.local:
            return "no proxy"
        else:
            return self.parsed

    def __repr__(self):
        return (f"Proxy({self.__str__()}): average_response: {self.average_response},"
                f" total_successes: {self.total_successes}, total_submissions: {self.total_submissions},"
                f" status: {self.status}, disabled_until: {self.disabled_until}")
