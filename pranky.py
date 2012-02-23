from twisted.python import log
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

    def get_mapping(self, source):
        """Finds all mappings for a matching IP in the database. Prefers
        mappings from the most specific match, starting with the full IP
        and ending with a wildcard.
        """
        mappings = {}
        if source in self.database:
            mappings = dict(self.database[source], **mappings)
        parts = source.split(".")
        for i in xrange(0, 4):
            sub = ".".join(parts[0:(4 - i)]) + ".*"
            if sub in self.database:
                mappings = dict(self.database[sub], **mappings)
        if '*' in self.database:
            mappings = dict(self.database['*'], **mappings)
        log.msg("Rules: " + str(mappings))
        return mappings

    def search_mapping(self, mapping, name):
        """Searches a mapping for a match to the name. Goes from most
        specific to least specific, starting with the full domain and
        ending with a wildcard.
        """
        if name in mapping:
            return mapping[name]
        parts = name.split(".")
        for i in xrange(0, len(parts)):
            sub = "*." + ".".join(parts[i:len(parts)])
            if sub in mapping:
                return mapping[sub]
        if '*' in mapping:
            return mapping['*']

    def lookupAddress(self, name, timeout=None, source='0.0.0.0'):
        """Checks the source ip and destination, and returns a custom
        resolution if they are in the database. Else, falls back to
        another DNS server. Checks for specific domains before wildcards.
        """
        log.msg("Source: " + source)
        mapping = self.get_mapping(source)
        if mapping:
            log.msg(mapping)
            log.msg("Domain: " + name)
            ip = self.search_mapping(mapping, name)
            if ip:
                return self._get_custom_ip(name, timeout, ip)
        return self._lookup(name, dns.IN, dns.A, timeout)

    @defer.inlineCallbacks
    def _get_custom_ip(self, name, timeout, ip):
        """Return custom A record"""
        log.msg("Custom IP: " + ip)
        ip = yield ip
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


def populateDatabase():
    f = open('mapping.txt', 'r')
    mapping = {}
    ip = None
    for line in f:
        line = line.rstrip()
        if line == '' or line[0] == '#':
            continue
        if ' ' not in line or not ip:
            ip = line
            mapping[ip] = {}
        else:
            parts = line.split(' ')
            mapping[ip][parts[0]] = parts[1]
    f.close()
    return mapping


def getFallbacks():
    f = open('fallbacks.txt', 'r')
    return [(line.rstrip(), 53) for line in f]
    f.close()

application = service.Application('pranky', 1, 1)

resolver = PrankResolver(populateDatabase(), getFallbacks())
service_collection = service.IServiceCollection(application)

dns_factory = CustomDNSServerFactory(clients=[resolver],
                                        caches=[cache.CacheResolver()])
udp = dns.DNSDatagramProtocol(dns_factory)

internet.TCPServer(53, dns_factory).setServiceParent(service_collection)
internet.UDPServer(53, udp).setServiceParent(service_collection)

if __name__ == "__main__":
    print "Usage: twistd -y pranky.py"
    print "Customize via mapping.txt and fallbacks.txt"
