import json
import os

from twisted.internet import defer, reactor
from twisted.internet.task import LoopingCall
from jsonrpc.proxy import JSONRPCProxy
from lbrynet.conf import API_CONNECTION_STRING
from lbrynet.core.LBRYMetadata import Metadata, verify_name_characters


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

    def _filter_claimtrie(self):
        claims = self.api.get_nametrie()
        r = []
        for claim in claims:
            try:
                verify_name_characters(claim['name'])
                r.append(claim)
            except:
                print "Bad claim: ", claim['name']
        return r

    def _update_claimtrie(self):
        print "Updating claimtrie"
        claimtrie = self._filter_claimtrie()
        if claimtrie != self.claimtrie:
            for claim in claimtrie:
                if claim['name'] not in self.metadata:
                    self._update_metadata(claim)
                elif claim['txid'] != self.metadata[claim['name']]['txid']:
                    self._update_metadata(claim)
            self.claimtrie = claimtrie
            print "Update complete"
        else:
            print "No new claims"

    def _save_metadata(self, claim, metadata):
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
        print "Starting updater"
        self.claimtrie_updater.start(30)

    def stop(self):
        print "Stopping updater"
        if self.claimtrie_updater.running:
            self.claimtrie_updater.stop()