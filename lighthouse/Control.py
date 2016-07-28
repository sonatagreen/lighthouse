from lighthouse.Server import LighthouseServer

from twisted.web import server
from twisted.internet import reactor
from jsonrpc.proxy import JSONRPCProxy


def main():
    engine = LighthouseServer()
    engine.start()
    s = server.Site(engine.root)
    reactor.listenTCP(50005, s)
    reactor.run()


if __name__ == "__main__":
    main()