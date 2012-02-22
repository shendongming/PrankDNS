from twisted.python import log
from twisted.names import cache, client, dns, server
from twisted.application import internet, service
from twisted.internet import defer, reactor

class PrankResolver(client.Resolver):

    def __init__(self, database, servers=None):
        client.Resolver.__init__(self, servers=servers)
        self.database = database
        self.ttl = 5
        self.source = '0.0.0.0'

    def set_source_ip(self, source):
        self.source = source

    def lookupAddress(self, name, timeout = None):
        if self.source in self.database:
            if name in self.database[self.source]:
                return self._get_custom_ip(name, timeout)
        return self._lookup(name, dns.IN, dns.A, timeout)

    @defer.inlineCallbacks
    def _get_custom_ip(self, name, timeout):
        ip = yield self.database[self.source][name]
        defer.returnValue([
            (dns.RRHeader(name, dns.A, dns.IN, self.ttl, dns.Record_A(ip, self.ttl)),), (), ()
        ]) 


class CustomDNSServerFactory(server.DNSServerFactory):

    def handleQuery(self, message, protocol, address):
        (host, test) = address
        self.prank_resolver.set_source_ip(host)
        return server.DNSServerFactory.handleQuery(self, message, protocol, address)

    def __init__(self, clients, caches):
        self.prank_resolver = clients[0]
        return server.DNSServerFactory.__init__(self, clients=clients, caches=caches)

application = service.Application('pranky', 1, 1)

resolver = PrankResolver({'127.0.0.1':{'www.google.com': '184.72.115.86', 'test.com': '184.72.115.86'}}, [('8.8.8.8', 53)])
service_collection = service.IServiceCollection(application)

dns_factory = CustomDNSServerFactory(clients=[resolver], caches=[cache.CacheResolver()])
udp = dns.DNSDatagramProtocol(dns_factory)

internet.TCPServer(53, dns_factory).setServiceParent(service_collection)
internet.UDPServer(53, udp).setServiceParent(service_collection)
