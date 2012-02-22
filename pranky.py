from twisted.names import cache, client, dns, server
from twisted.application import internet, service
from twisted.internet import defer


class PrankResolver(client.Resolver):

    def __init__(self, database, servers=None):
        client.Resolver.__init__(self, servers=servers)
        self.database = database
        self.ttl = 5

    def custom_query(self, query, timeout=None, source='0.0.0.0'):
        """Bypass query() if A record lookup to pass on  source IP"""
        if query.type == dns.A:
            return self.lookupAddress(str(query.name), timeout, source)
        return client.Resolver.query(self, query, timeout)

    def lookupAddress(self, name, timeout=None, source='0.0.0.0'):
        """Check the source ip and destination, and return a custom
        resolution if they are in the database. Else, fall back to
        another DNS server
        """
        if source in self.database:
            if name in self.database[source]:
                return self._get_custom_ip(name, timeout, source)
        return self._lookup(name, dns.IN, dns.A, timeout)

    @defer.inlineCallbacks
    def _get_custom_ip(self, name, timeout, source):
        """Return custom A record"""
        ip = yield self.database[source][name]
        defer.returnValue([
            (dns.RRHeader(
                name,
                dns.A,
                dns.IN,
                self.ttl,
                dns.Record_A(ip, self.ttl)),
            ), (), ()
        ])


class CustomDNSServerFactory(server.DNSServerFactory):

    def __init__(self, clients, caches):
        return server.DNSServerFactory.__init__(
                    self,
                    clients=clients,
                    caches=caches
            )

    def handleQuery(self, message, protocol, address):
        """Get peer IP address, and pass it on to the custom Resolver
        query method.
        """
        (host, test) = address
        query = message.queries[0]

        return self.resolver.resolvers[1].custom_query(
            query,
            source=host
        ).addCallback(
            self.gotResolverResponse, protocol, message, address
        ).addErrback(
            self.gotResolverError, protocol, message, address
        )


application = service.Application('pranky', 1, 1)

mapping = {'127.0.0.1': {'www.google.com': '184.72.115.86', 'test.com': '184.72.115.86'}}
fallback = [('8.8.8.8', 53)]
resolver = PrankResolver(mapping, fallback)
service_collection = service.IServiceCollection(application)

dns_factory = CustomDNSServerFactory(clients=[resolver],
                                        caches=[cache.CacheResolver()])
udp = dns.DNSDatagramProtocol(dns_factory)

internet.TCPServer(53, dns_factory).setServiceParent(service_collection)
internet.UDPServer(53, udp).setServiceParent(service_collection)
