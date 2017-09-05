"""
Supports flushing metrics to graphite
"""
import argparse
import re
import sys
import socket
import logging
import pickle
import struct


# Initialize the logger
logging.basicConfig()

SPACES = re.compile(r"\s+")
SLASHES = re.compile(r"\/+")
NON_ALNUM = re.compile(r"[^a-zA-Z_\-0-9\.\:]")


def read_arguments(args=None):
        p = argparse.ArgumentParser(description=__doc__)
        p.add_argument('--host', default='localhost')
        p.add_argument('--port', default=2003, type=int)
        p.add_argument('--prefix', default='')
        p.add_argument('--attempts', default=3, type=int)
        p.add_argument('--protocol', default='lines')
        p.add_argument('--normalize', action='store_true')
        p.add_argument('--socket-timeout', default=2, type=int)

        args = p.parse_args()

        return args

class GraphiteStore(object):
    def __init__(self, **kwargs):
        """
        Implements an interface that allows metrics to be persisted to Graphite.
        Raises a :class:`ValueError` on bad arguments.

        :Parameters:
            - `host` : The hostname of the graphite server.
            - `port` : The port of the graphite server
            - `prefix` (optional) : A prefix to add to the keys. Defaults to 'statsite.'
            - `attempts` (optional) : The number of re-connect retries before failing.
            - `normalize` (optional) : If set, attempt to sanitize/normalize keys to be more
               generally compliant with graphite/carbon expectations.
        """
        # Convert the port to an int since its coming from a configuration file
        for key, value in kwargs.iteritems():
            setattr(self, key, value)

        if self.port <= 0:
            raise ValueError("Port must be positive!")
        if self.attempts < 1:
            raise ValueError("Must have at least 1 attempt!")
        if self.protocol not in ["pickle", "lines"]:
            raise ValueError("Supported protocols are pickle, lines")

        if self.normalize is True:
            self.normalize_func = self.normalize_key
        else:
            self.normalize_func = lambda k: "%s%s" % (self.prefix, k)

        self.logger = logging.getLogger("statsite.graphitestore")
        self.socket_timeout = None if self.socket_timeout == 0 else self.socket_timeout
        self.sock = self._create_socket()
        self.flush = self.flush_pickle if self.protocol == "pickle" else self.flush_lines
        self.metrics = []

    def normalize_key(self, key):
        """
        Take a single key string and return the same string with spaces, slashes and
        non-alphanumeric characters subbed out and prefixed by self.prefix.
        """
        key = SPACES.sub("_", key)
        key = SLASHES.sub("-", key)
        key = NON_ALNUM.sub("", key)
        key = "%s%s" % (self.prefix, key)
        return key

    def append(self, metric):
        """
        Add one metric to queue for sending. Addtionally modify key to be compatible with txstatsd
        format.

        :Parameters:
         - `metric` : A single statsd metric string in the format "key|value|timestamp".
        """
        if metric and metric.count("|") == 2:
            k, v, ts = metric.split("|")
            k = self.normalize_func(k)
            self.metrics.append(((k), v, ts))

    def flush_lines(self):
        """
        Flushes the metrics provided to Graphite.
        """
        if not self.metrics:
            return

        lines = ["%s %s %s" % metric for metric in self.metrics]
        data = "\n".join(lines) + "\n"

        # Serialize writes to the socket
        try:
            self._write_metric(data)
        except StandardError:
            self.logger.exception("Failed to write out the metrics!")

    def flush_pickle(self):
        """
        Flushes the metrics provided to Graphite.
        """
        if not self.metrics:
            return

        # transform a list of strings into the list of tuples that
        # pickle graphite interface supports, in the form of
        # (key, (timestamp, value))
        # http://graphite.readthedocs.io/en/latest/feeding-carbon.html#the-pickle-protocol
        metrics_fmt = []
        for (k, v, ts) in self.metrics:
            metrics_fmt.append((k, (ts, v)))

        # do pickle the list of tuples
        # add the header the pickle protocol wants
        payload = pickle.dumps(metrics_fmt, protocol=2)
        header = struct.pack("!L", len(payload))
        message = header + payload

        try:
            self._write_metric(message)
        except StandardError:
            self.logger.exception("Failed to write out the metrics!")

    def close(self):
        """
        Closes the connection. The socket will be recreated on the next
        flush.
        """
        try:
            if self.sock:
                self.sock.close()
        except StandardError:
            self.logger.warning("Failed to close connection!")

    def _create_socket(self):
        """Creates a socket and connects to the graphite server"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.socket_timeout)
        try:
            sock.connect((self.host, self.port))
        except StandardError:
            self.logger.error("Failed to connect!")
            sock = None
        return sock

    def _write_metric(self, metric):
        """Tries to write a string to the socket, reconnecting on any errors"""
        for _ in xrange(self.attempts):
            if self.sock:
                try:
                    self.sock.sendall(metric)
                    return
                except socket.error:
                    self.logger.exception("Error while flushing to graphite. Reattempting...")

            self.sock = self._create_socket()

        self.logger.critical("Failed to flush to Graphite! Gave up after %d attempts.",
                             self.attempts)


def main():

    args = read_arguments()

    # Intialize from our arguments
    graphite = GraphiteStore(**args.__dict__)

    # Get all the inputs
    while True:
        try:
            graphite.append(raw_input().strip())
        except EOFError:
            break

    # Flush
    graphite.logger.info("Outputting %d metrics", len(graphite.metrics))
    graphite.flush()
    graphite.close()


if __name__ == "__main__":
    main()
