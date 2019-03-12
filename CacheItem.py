import asyncio
import logging
unsubscribeDelay = 5000 # ms

class CacheItem(object):

    # Creates a CacheItem instance
    # @param {string} rid Resource ID
    # @param {function} unsubscribe Unsubscribe callback
    def __init__(self, rid, unsubscribe, loop):
        self.rid = rid
        self._unsubscribe = unsubscribe
        self.type = None
        self.item = None
        self.direct = 0
        self.indirect = 0
        self.subscribed = False
        self.promise = None
        self.queues = dict()
        self.tasks = dict()
        self.loop = loop
        self.unsubTimeout =  None
        self.logger = logging.getLogger()


    def setSubscribed(self, isSubscribed):
        self.subscribed = isSubscribed
        if not isSubscribed and self.unsubTimeout:
            self.unsubTimeout = None
        return self

    def setPromise(self, promise):
        if not self.item:
            self.promise = promise
        return promise

    def setItem(self, item, type):
        self.item = item
        self.type = type
        self.promise = None
        self._checkUnsubscribe()
        return self

    def setType(self, modelType):
        self.type = modelType
        return self

    def addDirect(self):
        if self.unsubTimeout:
            self.unsubTimeout = None
        self.direct += 1

    def removeDirect(self):
        self.direct -=1
        if self.direct < 0:
            raise Exception("Direct count reached below 0")
        if self.subscribed:
            self._checkUnsubscribe()
        else:
            # The subscription might be stale and should then be removed directly
            self._unsubscribe(self)

    def _checkUnsubscribe(self):
        if not self.subscribed or self.direct or self.unsubTimeout:
            return
        self.unsubTimeout = True

        async def f():
            await asyncio.sleep(unsubscribeDelay/1000)
            if self.unsubTimeout:
                self._unsubscribe()

        asyncio.run_coroutine_threadsafe(f(), self.loop)

    def addIndirect(self, n = 1):
        self.indirect += n

    def removeIndirect(self, n = 1):
        self.indirect -= n
        if self.indirect < 0:
            raise Exception("Indirect count reached below 0")

