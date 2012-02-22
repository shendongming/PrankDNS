from twisted.names import cache, client, dns, server
from twisted.application import internet, service
from twisted.internet import defer, reactor

class PrankResolver(client.Resolver):

    def __init__(self, servers=None):
        client.Resolver.__init__(self, servers=servers)
        self.database = {'www.google.com': '72.21.214.128', 'google.com': '72.21.214.128'}
        self.ttl = 10

    def lookupAddress(self, name, timeout = None):
        if name in self.database:
            return self._get_custom_ip(name, timeout)
        else:
            return self._lookup(name, dns.IN, dns.A, timeout)

    @defer.inlineCallbacks
    def _get_custom_ip(self, name, timeout):
        ip = yield self.database[name]
        #Build a return a DNS query with the correct A Record
        defer.returnValue([
            (dns.RRHeader(name, dns.A, dns.IN, self.ttl, dns.Record_A(ip, self.ttl)),), (), ()
        ]) 

application = service.Application('pranky', 1, 1)

resolver = PrankResolver([('8.8.8.8', 53)])
service_collection = service.IServiceCollection(application)

dns_factory = server.DNSServerFactory(clients=[resolver], caches=[cache.CacheResolver()])
udp = dns.DNSDatagramProtocol(dns_factory)

internet.TCPServer(53, dns_factory).setServiceParent(service_collection)
internet.UDPServer(53, udp).setServiceParent(service_collection)
