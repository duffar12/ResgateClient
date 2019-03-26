
import asyncio
from websocket import WebSocketApp
import json
import threading
import logging
import time

from CacheItem import CacheItem
from resmodel import ResModel
from TypeList import TypeList
from ResCollection import ResCollection
from ResError import ResError

def defaultModelFactory(api, rid):
    return ResModel(api, rid)
def defaultCollectionFactory(api, rid):
    return ResCollection(api, rid)
def errorFactory(api, rid):
    return ResError(rid)


# Resource types
typeCollection = 'collection'
typeModel = 'model'
typeError = 'error'
resourceTypes = [typeModel, typeCollection, typeError]
# Actions
actionDelete = {'action': 'delete'}
# Default settings
defaultNamespace = 'resclient'
reconnectDelay = 3000
subscribeStaleDelay = 2000
# Traverse states
stateNone = 0
stateDelete = 1
stateKeep = 2
stateStale = 3

def run_loop(loop):
    print('runing loop')
    loop.run_forever()

# ResClient is a client implementing the RES-Client protocol.

class ResClient(object):

    # Creates a ResClient instance
    # @param {string} hostUrl Websocket host path. May be relative to current path.
    # @param {object} [opt] Optional parameters.
    # @param {function} [opt.onConnect] On connect callback called prior resolving the connect promise and subscribing to stale resources. May return a promise.
    # @param {string} [opt.namespace] Event bus namespace. Defaults to 'resclient'.
    # @param {module:modapp~EventBus} [opt.eventBus] Event bus.
    def __init__(self, hostUrl, opt=None):
        self.hostUrl = self._resolvePath(hostUrl)
        self.loop = asyncio.new_event_loop()
        t=threading.Thread(target=run_loop, args=(self.loop,))
        t.start()
        print('thread started')

        self.event_queues =  dict()
        self.subscribe_queues =  dict()
        self.tasks = dict()
        self.ws = WebSocketApp(self.hostUrl
                              ,on_message = self._handleOnmessage
                              ,on_error = self._handleOnerror
                              ,on_close = self._handleOnclose
                              ,on_open = self._handleOnopen)
        self.tryConnect = False
        self.connected = False
        self.requests = {}
        self.reqId = 1 # Incremental request id
        self.cache = {}
        self.stale = None
        self.logger = logging.getLogger()
        self.logger.addHandler(logging.StreamHandler())
        self.logger.setLevel(logging.DEBUG)

        def prepare_model_data(data):
            #create a copy of data called _data
            _data = {k:v for k,v in data.items()}
            for k, v in _data.items():
                if isinstance(v, dict) and 'rid' in v:
                    ci = self.cache[v['rid']]
                    ci.addIndirect()
                    _data[k] = ci.item
            return _data

        def prepare_list_data( data):
            def _f(v):
                # Is the value a reference, get the actual item from cache
                if isinstance(v, dict) and 'rid' in v:
                    ci = self.cache[v['rid']]
                    ci.addIndirect()
                    return ci.item
                return v

            return list(map(_f, data))


        # Types
        self.types = {'model':
                              {'id': typeModel
                              ,'list': TypeList(defaultModelFactory)
                              ,'prepareData': prepare_model_data
                              ,'getFactory': lambda rid: self.types['model']['list'].getFactory(rid)
                              ,'syncronize': self._syncModel}
                     ,'collection': {
                         'id': typeCollection
                         ,'list': TypeList(defaultCollectionFactory)
                         ,'prepareData': prepare_list_data
                         ,'getFactory': lambda rid: self.types['collection']['list'].getFactory(rid)
                         ,'syncronize': self._syncCollection }
                     ,'error': {
                         'id': typeError
                         ,'prepareData': lambda dta: dta
                         ,'getFactory': lambda rid : errorFactory
                         ,'syncronize': lambda : None }
                      }


    # Disconnects any current connection and stops attempts
    # of reconnecting.
    def disconnect(self):
        self.tryConnect = False

        if self.ws:
            self.ws.close()
            #self._connectReject({ 'code': 'system.disconnect', 'message': "Disconnect called" })

    def run(self):
        self.ws.run_forever()
    # Gets the host URL to the RES API
    # @returns {string} Host URL
    def getHostUrl(self):
        return self.hostUrl

    def add_event(self, event, cb):
        if event not in self.event_queues:
            self.event_queues[event] =  asyncio.queues.Queue(maxsize=1000, loop=self.loop)
        async def handle(q):
            while True:
                result = await q.get()
                cb(result)
        task = asyncio.run_coroutine_threadsafe(handle(self.event_queues[event]), self.loop)
        self.tasks[event] = task

    # Attach an  event handler function for one or more instance events.
    # @param {?string} events One or more space-separated events. Null means any event.
    # @param {eventCallback} handler A function to execute when the event is emitted.
    def on(self, events, handler):
        events = events.split(' ')
        for event in  events:
            print('adding handler for ', event)
            self.add_event(event, handler)

    # Remove an instance event handler.
    # @param {?string} events One or more space-separated events. Null means any event.
    # @param {eventCallback} [handler] An optional handler function. The handler will only be remove if it is the same handler.
    def off(self, events, handler):
        for event in events.split(' '):
            try:
                self.tasks[event].cancel()
            except:
                self.logger.exception('Error turning off resource handler for {}'.format(event))

    # Sets the onConnect callback.
    # @param {?function} onConnect On connect callback called prior resolving the connect promise and subscribing to stale resources. May return a promise.
    def setOnConnect(self, onConnect):
        self.onConnect = onConnect
        return self

    # Register a model type.
    # The pattern may use the following wild cards:
    # # The asterisk (#) matches any part at any level of the resource name.
    # # The greater than symbol (>) matches one or more parts at the end of a resource name, and must be the last part.
    # @param {string} pattern Pattern of the model type.
    # @param {resourceFactoryCallback} factory Model factory callback
    def registerModelType(self, pattern, factory):
        self.types['model']['list'].addFactory(pattern, factory)

    # Unregister a previously registered model type pattern.
    # @param {string} pattern Pattern of the model type.
    # @returns {resourceFactoryCallback} Unregistered model factory callback
    def unregisterModelType(self, pattern):
        return self.types['model']['list'].removeFactory(pattern)

    # Register a collection type.
    # The pattern may use the following wild cards:
    # # The asterisk (#) matches any part at any level of the resource name.
    # # The greater than symbol (>) matches one or more parts at the end of a resource name, and must be the last part.
    # @param {string} pattern Pattern of the collection type.
    # @param {ResClient~resourceFactoryCallback} factory Collection factory callback
    def registerCollectionType(self, pattern, factory):
        self.types['collection']['list'].addFactory(pattern, factory)


    # Unregister a previously registered collection type pattern.
    # @param {string} pattern Pattern of the collection type.
    # @returns {resourceFactoryCallback} Unregistered collection factory callback
    def unregisterCollectionType(self, pattern):
        return self.types['model']['list'].removeFactory(pattern)


    # Get a resource from the API
    # @param {string} rid Resource ID
    # @param {function} [collectionFactory] Collection factory function.
    # @return {Promise.<(ResModel|ResCollection)>} Promise of the resource.
    async def get(self, rid):
        # Check for resource in cache
        if rid in self.cache:
            ci = self.cache[rid]
            return ci.item

        ci = CacheItem(rid, self._unsubscribe, self.loop)
        self.cache[rid] = ci
        print('await subscribe')
        await self._subscribe(ci, True)
        print('finished subscribe')
        return ci.item


    # Calls a method on a resource.
    # @param {string} rid Resource ID.
    # @param {string} method Method name
    # @param {#} params Method parameters
    # @returns {Promise.<object>} Promise of the call result.
    async def call(self, rid, method, params):
        if method == None:
            method = ''
        await self._send('call', rid, method, params)


    # Invokes a authentication method on a resource.
    # @param {string} rid Resource ID.
    # @param {string} method Method name
    # @param {#} params Method parameters
    # @returns {Promise.<object>} Promise of the authentication result.
    async def authenticate(self, rid, method, params):
        if method == None:
            method = ''
        await self._send('auth', rid, method , params)


    # Creates a new resource by calling the 'new' method.
    # @param {#} rid Resource ID
    # @param {#} params Method parameters
    # @return {Promise.<(ResModel|ResCollection)>} Promise of the resource.
    async def create(self, rid, params):
        response = await self._send('new', rid, None, params)
        self._cacheResources(response)
        ci = self.cache[response.rid]
        ci.setSubscribed(True)
        return ci.item


    # Calls the set method to update model properties.
    # @param {string} modelId Model resource ID.
    # @param {object} props Properties. Set value to undefined to delete a property.
    # @returns {Promise.<object>} Promise of the call being completed.
    async def setModel(self, modelId, props):
        _props = {k:v for k,v in props.items()}
       # Replace undefined with actionDelete object
        for k,v in _props.items():
            if v == 'undefined':
                _props[k] = 'actionDelete'
        return await  self._send('call', modelId, 'set', props)

    def resourceOn(self, rid, events, handler):
        cacheItem = self.cache[rid]
        if not cacheItem:
            raise Exception("Resource not found in cache")
        cacheItem.addDirect()
        for event in events.split(' '):
            self.add_handler(event, cacheItem, handler)

    def add_handler(self, event, cacheItem, handler):
        if event not in cacheItem.queues:
            cacheItem.queues[event] = asyncio.Queue(1000, loop=self.loop)
        async def handle(q):
            while True:
                result = await q.get()
                #asyncio.run_coroutine_threadsafe(handler(result), loop=self.loop)
                handler(result)
        task = asyncio.run_coroutine_threadsafe(handle(cacheItem.queues[event]), loop=self.loop)
        cacheItem.tasks[event] = task

    def remove_handler(self, event, cacheItem):
        if event not in cacheItem.tasks:
            raise Exception('Resourse has no handler')
        try:
            cacheItem.tasks[event].cancel()
        except:
            pass

    def resourceOff(self, rid, events):
        cacheItem = self.cache[rid]
        if  not cacheItem:
            raise Exception("Resource not found in cache")

        cacheItem.removeDirect()
        for event in events.split(' '):
            self.remove_handler(event, cacheItem)


    # Sends a JsonRpc call to the API
    # @param {string} action Action name
    # @param {string} rid Resource ID
    # @param {?string} method Optional method name
    # @param {?object} params Optional parameters
    # @returns {Promise.<object>} Promise to the response
    # @private
    async def _send(self, action, rid, method, params):
        if not rid:
            raise Exception("Invalid resource ID")

        if method == "":
            raise Exception("Invalid method")

        if method is None:
            method = ''

        method = action + '.' + rid + method
        if self.connected:
            print('awaiting _sendNow')
            return await self._sendNow(method, params)

        else:
            raise Exception('New ResError {} {} {}'.format(rid, method, params))

    async def _sendNow(self, method, params):
        #return new Promise((resolve, reject) => {
        # Prepare request object
        self.reqId += 1
        req = { 'id': self.reqId, 'method': method, 'params':params}
        self.requests[req['id']] = {'method': method, 'params': req['params'], 'resolve': asyncio.Future(loop=self.loop)}
        keys = [k for k in req.keys()]
        for k in keys:
            if req[k] is None:
                del req[k]

        self.ws.send(json.dumps(req))
        self.logger.debug('waitng to resolve req id {}'.format(req['id']))
        ret = await self.requests[req['id']]['resolve']
        del self.requests[req['id']]
        return ret


    # Recieves a incoming json encoded data string and executes the appropriate functions/callbacks.
    # @param {string} json Json encoded data
    # @private
    def _receive(self, data):
        data = json.loads(data)
        print('datat received from server')

        if 'id' in data:
           # Find the stored request
            req = self.requests[data['id']]
            print('resolve id = ', data['id'])
            if not req:
                raise Exception("Server response without matching request")

            if 'error' in data:
                self._handleErrorResponse(req, data)
            else:
                self._handleSuccessResponse(req, data)

        elif 'event'in data:
            self._handleEvent(data)
        else:
            raise Exception("Invalid message from server: {}".format(data))

    def _handleErrorResponse(self, req, data):
        m = req['method']
       # Extract the rid if possible
        rid = ""
        split_message = m.split('.')
        if len(split_message) > 0:
            rid = m[1]
            a =  m[0]
            if a == 'call' or a == 'auth':
                rid = '.'.join(m[1:-1])

        err = ResError(rid.strip(), m, req['params'])
        err._init(data['error'])
        self._emit('error', err)

        # Execute error callback bound to calling object
        req['resolve'].set_exception(err)

    def _handleSuccessResponse(self, req, data):
        # Execute success callback bound to calling object
        if 'result' in data:
            self.loop.call_soon_threadsafe(req['resolve'].set_result, data['result'])
        else:
            self.loop.call_soon_threadsafe(req['resolve'].set_result, data)
        print('resolving future for ', req['resolve'])

    def _handleEvent(self, data):
        # Event
        print('handle event')
        idx = data['event'].rfind('.')
        if idx < 0 or idx == len(data['event']) - 1:
            raise Exception("Malformed event name: " + data.event)

        rid = data['event'][0: idx]

        cacheItem = self.cache[rid]
        if not cacheItem:
            raise Exception("Resource not found in cache")

        event = data['event'][idx + 1:]
        handled = False

        if event == 'change':
            print('handle change event')
            handled = self._handleChangeEvent(cacheItem, event, data['data'])
        elif event == 'add':
            handled = self._handleAddEvent(cacheItem, event, data['data'])
        elif event == 'remove':
            handled = self._handleRemoveEvent(cacheItem, event, data['data'])
        elif event == 'unsubscribe':
            handled = self._handleUnsubscribeEvent(cacheItem, event)

        if not handled:
            if event in cacheItem.queues:
                asyncio.run_coroutine_threadsafe(cacheItem.queues[event].put(data['data']), loop=self.loop)


    def _handleChangeEvent(self, cacheItem, event, data):
        if cacheItem.type != typeModel:
            return False
        self._cacheResources(data)

       # Set deleted properties to undefined
        item = cacheItem.item
        rm = {}
        vals = data['values']
        for k,v in vals.items():
            if v is not None and isinstance(v, dict):
                if v.get('action') == 'delete':
                    vals[k] = None
                elif v.get('rid') is not None:
                    ci = self.cache[v.get('rid')]
                    vals[k] = ci.item
                    if v['rid'] in rm:
                        rm[v['rid']] -= 1
                    else:
                        rm[v['rid']] = -1
                else:
                    raise Exception("Unsupported model change value: ", v)

            ov = item.data.get(k)
            if self._isResource(ov):
                rid = ov.getResourceId()
                if 'rid' in rm:
                    rm[rid] += 1
                else:
                    rm[rid] = 1

       # Remove indirect reference to resources no longer referenced in the model
        for rid, resource in rm.items():
            ci = self.cache[rid]
            ci.removeIndirect(resource)
            if resource > 0:
                self._tryDelete(ci)

       # Update the model with new values
        changed = cacheItem.item._update(vals)
        if changed:
            if event in cacheItem.queues:
                print('data has changed putting  to  queue')
                asyncio.run_coroutine_threadsafe(cacheItem.queues[event].put(cacheItem.item), loop=self.loop)
        return True

    def _handleAddEvent(self, cacheItem, event, data):
        if cacheItem.type != typeCollection:
            return False

        idx = data['idx']

        # Get resource if value is a resource reference
        if data.get('value') is not None and data.get('value').get('rid') is not None:
            self._cacheResources(data)
            ci = self.cache[data['value']['rid']]
            ci.addIndirect()
            data['value'] = ci.item

        cacheItem.item._add(data.get('value'), idx)
        if event in cacheItem.queues:
            asyncio.run_coroutine_threadsafe(cacheItem.queues[event].put({'item': data.get('value'), 'idx': idx}), loop=self.loop)
        return True


    def _handleRemoveEvent(self, cacheItem, event, data):
        if cacheItem.type != typeCollection:
            return False
        idx = data['idx']
        item = cacheItem.item._remove(idx)
        if event in cacheItem.queues:
            asyncio.run_coroutine_threadsafe(cacheItem.queues[event].put({'item': item, 'idx': idx}), loop=self.loop)

        if self._isResource(item):
            refItem = self.cache[item.getResourceId()]
            if not refItem:
                raise Exception("Removed model is not in cache")

            refItem.removeIndirect()
            self._tryDelete(refItem)
        return True

    def _handleUnsubscribeEvent(self, cacheItem, event):
        cacheItem.setSubscribed(False)
        self._tryDelete(cacheItem)
        if event in cacheItem.queues:
            asyncio.run_coroutine_threadsafe(cacheItem.queues[event].put({'item': cacheItem.item}), loop=self.loop)
        return True

    async def _setStale(self,  rid):
        self._addStale(rid)
        if self.connected:
            await asyncio.sleep(subscribeStaleDelay/1000)
            self._subscribeToStale(rid)

    def _addStale(self,rid):
        if not self.stale:
            self.stale = {}
        self.stale[rid] = True

    def _removeStale(self, rid):
        if self.stale:
            del self.stale[rid]
            for k in self.stale:
                return
            self.stale = None

    async def _subscribe(self, ci, throwError):
        rid = ci.rid
        ci.setSubscribed(True)
        self._removeStale(rid)
        try:
            response = await self._send('subscribe', rid, None, None)
            self._cacheResources(response)
        except:
            self.logger.exception('error subscribing to resource '+ str(rid))
            self._handleFailedSubscribe(ci, None)
            if throwError:
                raise Exception

    def _subscribeToStale(self,rid):
        if not self.connected or not self.stale or not self.stale[rid]:
            return
        self._subscribe(self.cache[rid])

    def _subscribeToAllStale(self):
        if (not self.stale):
            return

        for rid in self.stale:
            self._subscribeToStale(rid)


    # Handles the websocket onopen event
    # @param {object} e Open event object
    # @private
    def _handleOnopen(self, ws):
        self.logger.debug('Connection to {} opened'.format(self.hostUrl))
        self.connected = True
        try:
            asyncio.run_coroutine_threadsafe(self.onConnect(), self.loop)
            self._subscribeToAllStale()
        except:
            if self.ws:
               self.ws.close()


    # Handles the websocket onerror event
    # @param {object} e Error event object
    # @private
    def _handleOnerror(self, ws, error):
        self.logger.debug(json.dumps({ 'code': 'system.connectionError', 'message': "Connection error", 'data': str(error)}))


    # Handles the websocket onmessage event
    # @param {object} e Message event object
    # @private
    def _handleOnmessage(self, ws, msg):
        self.logger.debug('new message - {}'.format(msg))
        #msg = json.loads(msg)
        self._receive(msg)


    # Handles the websocket onclose event
    # @param {object} e Close event object
    # @private
    def _handleOnclose(self, ws):
        self.logger.debug('websocket closed')
        self.ws = None
        if self.connected:
            self.connected = False

           # Set any subscribed item in cache to stale
            for rid, ci in self.cache.items():
                if ci.subscribed:
                    ci.setSubscribed(False)
                    self._addStale(rid)
                    self._tryDelete(ci)

            self._emit('close', ws)

        hasStale = False
        for _ in self.cache:
            hasStale = True
            break

        self.tryConnect = hasStale and self.tryConnect

        if self.tryConnect:
            self._reconnect()


    def _emit(self, event, data):
        if event not in self.event_queues:
            self.event_queues[event] = asyncio.Queue(1000, loop=self.loop)
        asyncio.run_coroutine_threadsafe(self.event_queues[event].put(data), loop=self.loop)


    # Tries to delete the cached item.
    # It will delete if there are no direct listeners, indirect references, or any subscription.
    # @param {object} ci Cache item to delete
    # @private
    def _tryDelete(self,ci):
        try:
            refs = self._getRefState(ci)

            for rid, r in refs.items():
                if r['st'] == stateStale:
                    self._setStale(rid)
                    self.logger.debug('{} set to stale'.format(rid))
                elif r['st'] == stateDelete:
                    self._deleteRef(r['ci'])
                    self.logger.debug('references to {} deleted'.format(rid))
        except:
            self.logger.exception('exception in trying to delete cached item {}'.format(ci.rid))



    # Gets the reference state for a cacheItem and all its references
    # if the cacheItem was to be removed.
    # @param {CacheItem} ci Cache item
    # @return {Object.<string, RefState>} A key value object with key being the rid, and value being a RefState array.
    # @private
    def _getRefState(self, ci):
        refs = {}
       # Quick exit
        if (ci.subscribed):
            return refs
        refs[ci.rid] = { 'ci': ci, 'rc': ci.indirect, 'st': stateNone }
        self._traverse(ci, refs, self._seekRefs, 0, True)
        self._traverse(ci, refs, self._markDelete, stateDelete)
        return refs


    # Seeks for resources that no longer has any reference and may
    # be deleted.
    # Callback used with _traverse.
    # @param {#} refs References
    # @param {#} ci Cache item
    # @param {#} state State as returned from parent's traverse callback
    # @returns {#} State to pass to children. False means no traversing to children.
    # @private
    def _seekRefs(self, refs, ci, state):
       # Quick exit if it is already subscribed
        if (ci.subscribed):
            return False

        rid = ci.rid
        r = refs.get(rid)
        if not r:
            refs[rid] = { 'ci': ci, 'rc': ci.indirect - 1, 'st': stateNone }
            return True

        r['rc'] -= 1
        return False


    # Marks reference as stateDelete, stateKeep, or stateStale, depending on
    # the values returned from a _seekRefs traverse.
    # @param {#} refs References
    # @param {#} ci Cache item
    # @param {#} state State as returned from parent's traverse callback
    # @return {#} State to pass to children. False means no traversing to children.
    # @private
    def _markDelete(self, refs, ci, state):
       # Quick exit if it is already subscribed
        if (ci.subscribed):
            return False

        rid = ci.rid
        r = refs[rid]

        if (r['st'] == stateKeep):
            return False

        if (state == stateDelete):

            if (r['rc'] > 0):
                r['st'] = stateKeep
                return rid

            if (r['st'] != stateNone):
                return False

            if (r['ci'].direct):
                r['st'] = stateStale
                return rid

            r['st'] = stateDelete
            return stateDelete

       # A stale item can never cover itself
        if (rid == state):
            return False

        r['st'] = stateKeep
        return rid if r['rc'] > 0 else state

    def _deleteRef(self, ci):
        item = ci.item
        if ci.type == typeCollection:
            for v in item:
                ri = self._getRefItem(v)
                if (ri):
                    ri.removeIndirect()
        elif ci.type == typeModel:
            for k in item.data:
                ri = self._getRefItem(item.data[k])
                if (ri):
                    ri.removeIndirect()
        del self.cache[ci.rid]
        self._removeStale(ci.rid)

    def _isResource(self, v):
        return v != None and hasattr(v, 'getResourceId') and callable(v.getResourceId)

    def _getRefItem(self, v):
        if not self._isResource(v):
            return None
        rid = v.getResourceId()
        refItem = self.cache[rid]
        # refItem not in cache means
        # item has been deleted as part of
        # a refState object.
        if not refItem:
            return None

        return refItem

    def _cacheResources(self, resources):
        if not resources:
            return
        sync = dict()
        for t in resourceTypes:
            if t + 's' in resources:
                sync[t] = self._createItems(resources[t +  's'], self.types[t])
                self._initItems(resources[t + 's'], self.types[t])
                self._syncItems(sync[t], self.types[t])


    def _createItems(self, refs, _type):
        if not refs:
            return
        sync = {}
        for rid in refs:
            ci = self.cache.get(rid)
            if ci is None:
                self.cache[rid] = CacheItem(rid, self._unsubscribe , self.loop)
                ci = self.cache[rid]
            else:
               # Remove item as stale if needed
                self._removeStale(rid)
            # If an item is already set,
            # it has gone stale and needs to be syncronized.
            if ci.item:
                if ci.type != _type.id:
                    self.logger.error("Resource type inconsistency")
                else:
                    sync[rid] = refs[rid]
                del refs[rid]
            else:
                f = _type['getFactory'](rid)
                ci.setItem(f(self, rid), _type['id'])
        return sync

    def _initItems(self, refs, _type):
        if refs == None:
            return

        for rid in refs:
            cacheItem = self.cache[rid]
            cacheItem.item._init(_type['prepareData'](refs[rid]))

    def _syncItems(self,refs,_type):
        if refs == None:
            return

        for rid in refs:
            ci = self.cache[rid]
            _type.syncronize(ci, refs[rid])

    def _syncModel(self, cacheItem, data):
        self._handleChangeEvent(cacheItem, 'change', {'values': data })

    def _syncCollection(self,  cacheItem, data):
        collection = cacheItem.item
        i = len(collection)
        a = [0]*i
        for j in range(i):
            a[j] = collection.atIndex(j)


        def _f(v):
            if v is not None and hasattr(v, 'rid') and v.rid != None:
                # Is the value a reference, get the actual item from cache
                return self.cache[v.rid].item
            return v

        b = list(map(_f, data))

        def _onKeep(id, m, n, idx):
            return None
        def _onAdd(id, n, idx):
            self._handleAddEvent(cacheItem, 'add', {'value': data[n], idx: idx })
        def _onRemove(id, m, idx):
            self._handleRemoveEvent(cacheItem, 'remove', { idx })


        self._patchDiff(a, b, _onKeep, _onAdd, _onRemove)


    def _patchDiff(self, a, b, onKeep, onAdd, onRemove):
        # Do a LCS matric calculation
        # https:#en.wikipedia.org/wiki/Longest_common_subsequence_problem
        t = i = j = aa = bb = None
        s = 0
        m = len(a)
        n = len(b)

        # Trim of matches at the start and end
        while s < m and s < n and a[s] == b[s]:
            s += 1

        if s == m and s == n:
            return
        while s < m and s < n and a[m - 1] == b[n - 1]:
            m -=1
            n -=1

        if s > 0 or m < len(a):
            aa = a[s: m]
            m = len(aa)
        else:
            aa = a
        if s > 0 or n < len(b):
            bb = b[s: n]
            n = len(bb)
        else:
            bb = b

       # Create matrix and initialize it
        c = []
        for i in range(m+1):
            c.append([0]*n+1)

        for i in range(m-1):
            for j in range(n-1):
                c[i+1][j+1] = c[i][j] +1 if aa[i] == bb[j] else max(c[i+1][j], c[i][j+1])

        for i in range(s+m, len(a)-1):
            self.onKeep(a[i], i, i-m +n, i)

        idx = m + s
        i = m
        j = n
        r = 0
        adds = []
        while (True):
            m = i - 1
            n = j - 1
            if (i > 0 and j > 0 and aa[m] == bb[n]):
                self.onKeep(aa[m], m + s, n + s, --idx)
                i-=1
                j-=1
            elif j > 0 and (i == 0 or c[i][n] >= c[m][j]):
                adds.append([ n, idx, r ])
                j-= 1
            elif i > 0 and (j == 0 or c[i][n] < c[m][j]):
                self.onRemove(aa[m], m + s, --idx)
                r+=1
                i-=1
            else:
                break

        for i in range(s-1):
            self.onKeep(a[i], i, i, i)

        # Do the adds
        for i in range(len(adds)):
            [ n, idx, j ] = adds[i]
            self.onAdd(bb[n], n + s, idx - r + j + len(adds) - i)

    async def _unsubscribe(self,ci):
        if not ci.subscribed:
            if (self.stale and self.stale[ci.rid]):
                self._tryDelete(ci)
            return

        self._subscribeReferred(ci)

        try:
            await self._send('unsubscribe', ci.rid, None, None)
            ci.setSubscribed(False)
            self._tryDelete(ci)
        except:
            self.logger.exception('unsubscribe exception')
            self._tryDelete(ci)

    def _subscribeReferred(self, ci):
        ci.subscribed = False
        refs = self._getRefState(ci)
        ci.subscribed = True

        for rid, r in refs.items():
            if r['st'] == stateStale:
                self._subscribe(r['ci'])

    def _handleFailedSubscribe(self, cacheItem, err):
        self.logger.warning('subscription for {} failed'.format(cacheItem.rid))
        cacheItem.setSubscribed(False)
        self._tryDelete(cacheItem)

    async def _reconnect(self):
        await asyncio.sleep(reconnectDelay/1000)
        if not self.tryConnect:
            return
        self.logger.debug('attempting to reconnect')
        self.connect()

    def _resolvePath(self, url):
        if 'wss:/' in url or 'ws:/' in url:
            return url
        return url.replace('http', 'ws')

    def _traverse(self, ci, refs, cb, state, skipFirst = False):
        # Call callback to get new state to pass to
        # children. If False, we should not traverse deeper
        if not skipFirst:
            state = cb(refs, ci, state)
            if (state == False):
                return

        item = ci.item
        if ci.type == typeCollection:
            for v in item:
                ci = self._getRefItem(v)
                if (ci):
                    self._traverse(refs, ci, cb, state)
        elif ci.type == typeModel:
            for k in item.data:
                ci = self._getRefItem(item.data[k])
                if (ci):
                    self._traverse(refs, ci, cb, state)


    def isResError(self, o):
        return isinstance(o, ResError)
