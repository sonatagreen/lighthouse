from lighthouse.Server import LighthouseServer

from twisted.web import server
from twisted.internet import reactor
from jsonrpc.proxy import JSONRPCProxy


def main():
    engine = LighthouseServer()
    engine.start()
    s = server.Site(engine.root)
    reactor.listenTCP(8080, s, "")
    reactor.run()


def stop():
    api = JSONRPCProxy("http://localhost:8080")
    try:
        api.stop()
    except:
        print "Api wasn't running"


if __name__ == "__main__":
    main()