import json
import os

from twisted.internet import defer, reactor
from twisted.internet.task import LoopingCall
from jsonrpc.proxy import JSONRPCProxy
from lbrynet.conf import API_CONNECTION_STRING
from lbrynet.core.LBRYMetadata import Metadata, verify_name_characters
import logging.handlers
import sys

DEFAULT_FORMAT = "%(asctime)s %(levelname)-8s %(name)s:%(lineno)d: %(message)s"
DEFAULT_FORMATTER = logging.Formatter(DEFAULT_FORMAT)

log = logging.getLogger()
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(DEFAULT_FORMATTER)
log.addHandler(handler)
log.setLevel(logging.INFO)


class MetadataUpdater(object):
    def __init__(self):
        reactor.addSystemEventTrigger('before', 'shutdown', self.stop)
        self.api = JSONRPCProxy.from_url(API_CONNECTION_STRING)
        self.cache_file = os.path.join(os.path.expanduser("~/"), ".lighthouse_cache")
        self.claimtrie_updater = LoopingCall(self._update_claimtrie)
        self.bad_uris = []

        if os.path.isfile(self.cache_file):
            log.info("Loading cache")
            f = open(self.cache_file, "r")
            r = json.loads(f.read())
            f.close()
            self.claimtrie, self.metadata = r['claimtrie'], r['metadata']
        else:
            log.info("Rebuilding metadata cache")
            self.claimtrie = None
            self.metadata = {}

    def _filter_claimtrie(self):
        claims = self.api.get_nametrie()
        r = []
        for claim in claims:
            if claim['txid'] not in self.bad_uris:
                try:
                    verify_name_characters(claim['name'])
                    r.append(claim)
                except:
                    self.bad_uris.append(claim['txid'])
                    log.info("Bad name for claim %s" % claim['txid'])
        return r

    def _update_claimtrie(self):
        claimtrie = self._filter_claimtrie()
        if claimtrie != self.claimtrie:
            for claim in claimtrie:
                if claim['name'] not in self.metadata:
                    self._update_metadata(claim)
                elif claim['txid'] != self.metadata[claim['name']]['txid']:
                    self._update_metadata(claim)

    def _save_metadata(self, claim, metadata):
        log.info("Updating metadata for lbry://%s" % claim['name'])
        m = Metadata(metadata)
        self.metadata[claim['name']] = m
        self.metadata[claim['name']]['txid'] = claim['txid']
        if claim not in self.claimtrie:
            self.claimtrie.append(claim)
        return self._cache_metadata()

    def _notify_bad_metadata(self, claim):
        log.info("Bad metadata: " + str(claim['name']))
        if claim['txid'] not in self.bad_uris:
            self.bad_uris.append(claim['txid'])
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
        log.info("Starting updater")
        self.claimtrie_updater.start(30)

    def stop(self):
        log.info("Stopping updater")
        if self.claimtrie_updater.running:
            self.claimtrie_updater.stop()