import json
import os

from twisted.web import resource
from twisted.internet import defer, reactor
from twisted.internet.task import LoopingCall
from txjsonrpc.web import jsonrpc
from jsonrpc.proxy import JSONRPCProxy
from lbrynet.conf import API_CONNECTION_STRING
from fuzzywuzzy import process
from lighthouse.Metadata import Metadata


class MetadataUpdater(object):
    def __init__(self):
        reactor.addSystemEventTrigger('before', 'shutdown', self.stop)
        self.api = JSONRPCProxy.from_url(API_CONNECTION_STRING)
        self.cache_file = os.path.join(os.path.expanduser("~/"), ".lighthouse_cache")
        self.claimtrie_updater = LoopingCall(self._update_claimtrie)

        if os.path.isfile(self.cache_file):
            print "Loading cache"
            f = open(self.cache_file, "r")
            r = json.loads(f.read())
            f.close()
            self.claimtrie, self.metadata = r['claimtrie'], r['metadata']
        else:
            print "Rebuilding metadata cache"
            self.claimtrie = None
            self.metadata = {}

    def _update_claimtrie(self):
        print "Updating claimtrie"
        claimtrie = self.api.get_nametrie()
        if claimtrie != self.claimtrie:
            for claim in claimtrie:
                if claim['name'] not in self.metadata:
                    self._update_metadata(claim)
                elif claim['txid'] != self.metadata[claim['name']]['txid']:
                    self._update_metadata(claim)
            self.claimtrie = claimtrie
        else:
            print "No new claims"

    def _save_metadata(self, claim, metadata):
        print "Saving metadata for ", claim['name']
        m = Metadata(metadata)
        self.metadata[claim['name']] = m
        self.metadata[claim['name']]['txid'] = claim['txid']
        return self._cache_metadata()

    def _notify_bad_metadata(self, claim):
        print "Bad metadata: ", claim['name']
        return defer.succeed(None)

    def _update_metadata(self, claim):
        d = defer.succeed(None)
        d.addCallback(lambda _: self.api.resolve_name({'name': claim['name']}))
        d.addCallback(lambda metadata: self._save_metadata(claim, metadata))
        d.addErrback(lambda _: self._notify_bad_metadata(claim))
        return d

    def _cache_metadata(self):
        r = {'metadata': self.metadata, 'claimtrie': self.claimtrie}
        f = open(self.cache_file, "w")
        f.write(json.dumps(r))
        f.close()
        return defer.succeed(None)

    def start(self):
        self.claimtrie_updater.start(30)

    def stop(self):
        if self.claimtrie_updater.running:
            self.claimtrie_updater.stop()


class Lighthouse(jsonrpc.JSONRPC):
    def __init__(self):
        jsonrpc.JSONRPC.__init__(self)
        self.metadata_updater = MetadataUpdater()
        self.fuzzy_name_cache = []
        self.fuzzy_ratio_cache = {}

    def setup(self):
        pass

    def start(self):
        self.metadata_updater.start()

    def shutdown(self):
        pass

    def _process_search(self, search, search_by):
        r = process.extract(search, [self.metadata_updater.metadata[m][search_by] for m in self.metadata_updater.metadata], limit=10)
        r2 = [i[0] for i in r]
        r3 = [self.metadata_updater.metadata[m] for m in self.metadata_updater.metadata if self.metadata_updater.metadata[m][search_by] in r2]
        r4 = [next(i for i in r3 if i[search_by] == n) for n in r2]
        return r4

    def jsonrpc_search(self, search, search_by='title'):
        print "Search: ", search
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

    def jsonrpc_stop(self):
        print "Stopping"
        reactor.callLater(1, reactor.stop)
        return "Stopping"


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
