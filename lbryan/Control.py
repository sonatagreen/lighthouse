from lbryan.Server import LBRYanServer

from twisted.web import server
from twisted.internet import reactor


def main():
    engine = LBRYanServer()
    engine.start()
    s = server.Site(engine.root)
    reactor.listenTCP(8080, s, interface="localhost")
    reactor.run()

if __name__ == "__main__":
    main()