from twisted.web import resource
from twisted.internet import defer, reactor
from txjsonrpc.web import jsonrpc
from fuzzywuzzy import process

from lighthouse.Updater import MetadataUpdater


class Lighthouse(jsonrpc.JSONRPC):
    def __init__(self):
        jsonrpc.JSONRPC.__init__(self)
        reactor.addSystemEventTrigger('before', 'shutdown', self.shutdown)
        self.metadata_updater = MetadataUpdater()
        self.fuzzy_name_cache = []
        self.fuzzy_ratio_cache = {}

    def start(self):
        self.metadata_updater.start()

    def shutdown(self):
        self.metadata_updater.stop()

    def _process_search(self, search, search_by):
        r = process.extract(search, [self.metadata_updater.metadata[m][search_by] for m in self.metadata_updater.metadata], limit=10)
        r2 = [i[0] for i in r]
        r3 = [self.metadata_updater.metadata[m] for m in self.metadata_updater.metadata if self.metadata_updater.metadata[m][search_by] in r2]
        r4 = [next(i for i in r3 if i[search_by] == n) for n in r2]
        return r4

    def jsonrpc_search(self, search, search_by='title'):
        if search not in self.fuzzy_name_cache and len(self.fuzzy_name_cache) > 1000:
            del self.fuzzy_ratio_cache[self.fuzzy_name_cache.pop()]
            self.fuzzy_name_cache.reverse()
            self.fuzzy_name_cache.append(search)
            self.fuzzy_name_cache.reverse()
            self.fuzzy_ratio_cache[search] = self._process_search(search, search_by)
            return self.fuzzy_ratio_cache[search]
        elif search in self.fuzzy_name_cache:
            self.fuzzy_name_cache.remove(search)
            self.fuzzy_name_cache.reverse()
            self.fuzzy_name_cache.append(search)
            self.fuzzy_name_cache.reverse()
            return self.fuzzy_ratio_cache[search]
        else:
            self.fuzzy_name_cache.reverse()
            self.fuzzy_name_cache.append(search)
            self.fuzzy_name_cache.reverse()
            self.fuzzy_ratio_cache[search] = self._process_search(search, search_by)
            return self.fuzzy_ratio_cache[search]


class Index(resource.Resource):
    def __init__(self):
        resource.Resource.__init__(self)

    isLeaf = False

    def _delayed_render(self, request, results):
        request.write(str(results))
        request.finish()

    def getChild(self, name, request):
        if name == '':
            return self
        return resource.Resource.getChild(self, name, request)


class LighthouseServer(object):
    def _setup_server(self):
        self.root = Index()
        self._search_engine = Lighthouse()
        self.root.putChild("", self._search_engine)
        return defer.succeed(True)

    def start(self):
        d = self._setup_server()
        d.addCallback(lambda _: self._search_engine.start())
        return d
