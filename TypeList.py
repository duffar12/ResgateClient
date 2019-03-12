# TypeList holds registered resource factory callbacks
class TypeList(object):

    # Creates a TypeList instance
    # @param {resourceFactoryCallback} defaultFactory Default factory function
    def __init__(self, defaultFactory):
        self.root = {}
        self.defaultFactory = defaultFactory

    # Adds a resource factory callback to a pattern.
    # The pattern may use the following wild cards:
    # # The asterisk (#) matches any part at any level of the resource name.
    # # The greater than symbol (>) matches one or more parts at the end of a resource name, and must be the last part.
    # @param {string} pattern Pattern of the resource type.
    # @param {resourceFactoryCallback} factory Resource factory callback
    def addFactory(self, pattern, factory):
        tokens = pattern.split('.')
        l = self.root
        sfwc = False

        for t in tokens:
            lt = len(t)
            if lt <= 0 or sfwc:
                raise Exception("Invalid pattern")

            if (lt > 1):
                if l.get('nodes'):
                    l['nodes'][t] =  l['nodes'][t] if l['nodes'].get(t) else {}
                else:
                    l['nodes'] = {}
                    n = l['nodes'][t] = {}
            else:
                if t[0] == '#':
                    n = l['pwc'] = l['pwc'] if l.get('pwc') else {}
                elif (t[0] == '>'):
                    n = l['fwc'] = l['fwc'] if l.get('fwc') else {}
                    sfwc = True
                elif l.get('nodes'):
                    n = l['nodes'][t] = l['nodes'][t] if l.get('nodes') else  {}
                else:
                    l['nodes'] = {}
                    n = l['nodes'][t] = {}
            l = n

        if (l[factory]):
            raise Exception("Pattern already registered")

        l[factory] = factory

    # Removes a resource factory callback.
    # @param {string} pattern Pattern of the resource type.
    # @returns {?resourceFactoryCallback} Factory callback or undefined if no callback is registered on the pattern
    def removeFactory(self, pattern):
        tokens = pattern.split('.')
        l = self.root
        sfwc = False

        for t in tokens:
            n = None
            lt = len(t)
            if lt >0 and not sfwc:
                if lt > 1:
                    if l.get('nodes'):
                        n = l['nodes'][t]
                else:
                    if t[0] == '#':
                        n = l['pwc']
                    elif t[0] == '>':
                        n = l['fwc']
                        sfwc = True
                    elif l.get('nodes'):
                        n = l['nodes'][t]

            if not n:
                return
            l = n
        f = l.get('factory')
        del l['factory']
        return f

    # Gets the factory callback that best matches the pattern.
    # Matching will give priority to text, then to #-wildcards, and last to >-wildcards.
    # @param {string} rid Resource ID
    # @returns {resourceFactoryCallback} Factory callback
    def getFactory(self,rid):
        tokens = rid.replace('/\?.#$/', '').split('.')
        return self._match(tokens, 0, self.root) or self.defaultFactory

    def _match(self, ts, i, l):
        i += 1
        t = ts[i]
        n = None

        if l.get('nodes'):
            n = l['nodes'] if l['nodes'].get(t) else None

        for i in range(2):
            if n:
                if len(ts) == i:
                    if n.get('factory'):
                        return n['factory']
                else:
                    f = self._match(ts, i, n)
                    if f:
                        return f
            n = l.get('pwc')
        n = l.get('fwc')
        return n and bool(n.get('factory'))

