from lighthouse.Server import LBRYanServer

from twisted.web import server
from twisted.internet import reactor
from jsonrpc.proxy import JSONRPCProxy


def main():
    engine = LBRYanServer()
    engine.start()
    s = server.Site(engine.root)
    reactor.listenTCP(8080, s, interface="localhost")
    reactor.run()


def stop():
    api = JSONRPCProxy("http://localhost:8080")
    try:
        api.stop()
    except:
        print "Api wasn't running"


if __name__ == "__main__":
    main()