import logging

from lighthouse.Server import LighthouseServer
from twisted.web import server
from twisted.internet import reactor

log = logging.getLogger(__name__)
logging.getLogger(__name__).addHandler(logging.NullHandler())
log.setLevel(logging.INFO)


def main():
    engine = LighthouseServer()
    engine.start()
    s = server.Site(engine.root)
    reactor.listenTCP(50005, s)
    reactor.run()


if __name__ == "__main__":
    main()