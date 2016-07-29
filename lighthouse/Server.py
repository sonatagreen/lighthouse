from txjsonrpc import jsonrpclib
from txjsonrpc.web.jsonrpc import Handler
from decimal import Decimal
from twisted.web import resource
from twisted.internet import defer, reactor
from twisted.web import server
from txjsonrpc.web import jsonrpc
from fuzzywuzzy import process
from lighthouse.Updater import MetadataUpdater
import logging.handlers

log = logging.getLogger()

DEFAULT_SEARCH_KEYS = ['title', 'description', 'author']


class Lighthouse(jsonrpc.JSONRPC):
    def __init__(self):
        jsonrpc.JSONRPC.__init__(self)
        reactor.addSystemEventTrigger('before', 'shutdown', self.shutdown)
        self.metadata_updater = MetadataUpdater()
        self.fuzzy_name_cache = []
        self.fuzzy_ratio_cache = {}

    def render(self, request):
        request.content.seek(0, 0)
        # Unmarshal the JSON-RPC data.
        content = request.content.read()
        parsed = jsonrpclib.loads(content)
        functionPath = parsed.get("method")
        args = parsed.get('params')
        id = parsed.get('id')
        version = parsed.get('jsonrpc')
        log.info("%s %s " % (request.getClientIP(), functionPath) + str(args))
        assert functionPath == "search", "only search allowed"
        if version:
            version = int(float(version))
        elif id and not version:
            version = jsonrpclib.VERSION_1
        else:
            version = jsonrpclib.VERSION_PRE1
        # XXX this all needs to be re-worked to support logic for multiple
        # versions...
        try:
            function = self._getFunction(functionPath)
        except jsonrpclib.Fault, f:
            self._cbRender(f, request, id, version)
        else:
            request.setHeader("content-type", "text/json")
            d = defer.maybeDeferred(function, *args)
            d.addErrback(self._ebRender, id)
            d.addCallback(self._cbRender, request, id, version)
        return server.NOT_DONE_YET

    def _cbRender(self, result, request, id, version):
        def default_decimal(obj):
            if isinstance(obj, Decimal):
                return float(obj)

        if isinstance(result, Handler):
            result = result.result

        if isinstance(result, dict):
            result = result['result']

        if version == jsonrpclib.VERSION_PRE1:
            if not isinstance(result, jsonrpclib.Fault):
                result = (result,)
            # Convert the result (python) to JSON-RPC
        try:
            s = jsonrpclib.dumps(result, version=version, default=default_decimal)
        except:
            f = jsonrpclib.Fault(self.FAILURE, "can't serialize output")
            s = jsonrpclib.dumps(f, version=version)
        request.setHeader("content-length", str(len(s)))
        request.write(s)
        request.finish()

    def start(self):
        self.metadata_updater.start()

    def shutdown(self):
        self.metadata_updater.stop()

    def _process_search(self, search, keys):
        log.info("Processing search: %s" % search)
        results = []
        for search_by in keys:
            r = process.extract(search, [self.metadata_updater.metadata[m][search_by] for m in self.metadata_updater.metadata], limit=10)
            r2 = [i[0] for i in r]
            r3 = [{'name': m, 'value': self.metadata_updater.metadata[m]} for m in self.metadata_updater.metadata
                                                                          if self.metadata_updater.metadata[m][search_by] in r2]
            results += [next(i for i in r3 if i['value'][search_by] == n) for n in r2]

        final_results = []
        for result in results:
            if result['value'] not in [v['value'] for v in final_results]:
                final_results.append(result)
            if len(final_results) >= 10:
                break

        return final_results

    def jsonrpc_search(self, search, search_by=DEFAULT_SEARCH_KEYS):
        if search not in self.fuzzy_name_cache and len(self.fuzzy_name_cache) > 1000:
            del self.fuzzy_ratio_cache[self.fuzzy_name_cache.pop()]
            self.fuzzy_name_cache.reverse()
            self.fuzzy_name_cache.append(search)
            self.fuzzy_name_cache.reverse()
            self.fuzzy_ratio_cache[search] = self._process_search(search, search_by)
        elif search in self.fuzzy_name_cache:
            self.fuzzy_name_cache.remove(search)
            self.fuzzy_name_cache.reverse()
            self.fuzzy_name_cache.append(search)
            self.fuzzy_name_cache.reverse()
        else:
            self.fuzzy_name_cache.reverse()
            self.fuzzy_name_cache.append(search)
            self.fuzzy_name_cache.reverse()
            self.fuzzy_ratio_cache[search] = self._process_search(search, search_by)

        return self.fuzzy_ratio_cache[search]

    def jsonrpc_get_name_trie(self):
        return self.metadata_updater.claimtrie


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
