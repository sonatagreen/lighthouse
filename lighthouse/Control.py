from lighthouse.Server import LighthouseServer, LighthouseControllerServer
from twisted.web import server
from twisted.internet import reactor
import logging.handlers
import sys
import os


DEFAULT_FORMAT = "%(asctime)s %(levelname)-8s %(name)s:%(lineno)d: %(message)s"
DEFAULT_FORMATTER = logging.Formatter(DEFAULT_FORMAT)

log = logging.getLogger()
console_handler = logging.StreamHandler(sys.stdout)
file_handler = logging.FileHandler(os.path.join(os.path.expanduser("~/"), "lighthouse.log"))
console_handler.setFormatter(DEFAULT_FORMATTER)
file_handler.setFormatter(DEFAULT_FORMATTER)
log.addHandler(console_handler)
log.addHandler(file_handler)
log.setLevel(logging.INFO)


def main():
    engine = LighthouseServer()
    ecu = LighthouseControllerServer(engine.search_engine)
    engine.start()
    s = server.Site(engine.root)
    e = server.Site(ecu.root)

    reactor.listenTCP(50005, s)
    reactor.listenTCP(50004, e, interface="localhost")
    reactor.run()


if __name__ == "__main__":
    main()