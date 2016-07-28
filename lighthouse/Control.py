from lighthouse.Server import LighthouseServer
from twisted.web import server
from twisted.internet import reactor
import logging.handlers
import sys


DEFAULT_FORMAT = "%(asctime)s %(levelname)-8s %(name)s:%(lineno)d: %(message)s"
DEFAULT_FORMATTER = logging.Formatter(DEFAULT_FORMAT)

log = logging.getLogger()
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(DEFAULT_FORMATTER)
log.addHandler(handler)
log.setLevel(logging.INFO)


def main():
    engine = LighthouseServer()
    engine.start()
    s = server.Site(engine.root)
    reactor.listenTCP(50005, s)
    reactor.run()


if __name__ == "__main__":
    main()