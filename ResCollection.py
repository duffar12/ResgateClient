import json

 # ResCollection represents a collection provided over the RES API.
 # @implements {module:modapp~Collection}
class ResCollection(object):

    # Creates an ResCollection instance
    # @param {ResClient} api ResClient instance
    # @param {string} rid Resource id.
    # @param {object} [opt] Optional settings
    # @param {function} [opt.idCallback] Id callback function.
    def __init__(self, api, rid, opt=None):
       #opt = obj.copy(opt, {
       #    idCallback: { type: '?function' }
       #})

        self._data = opt
        self._api = api
        self._rid = rid

        self._idCallback = opt.get('idCallback') if opt else None
        self._map = {} if opt and opt.get('idCallback') else None
        self._list = None

    # Collection resource ID
    # @returns {string} Resource ID
    def getResourceId(self):
        return self._rid

    # Length of the collection
    @property
    def length(self):
        return self._list.length

    # Attach a collection event handler function for one or more events.
    # If no event or handler is provided, the collection will still be considered listened to,
    # until a matching off call without arguments is made.
    # Available events are 'add' and 'remove'.
    # @param {?string} [events] One or more space-separated events. Null means any event.
    # @param {eventCallback} [handler] Handler function to execute when the event is emitted.
    # @returns {self}
    def on(self,events, handler):
        self._api.resourceOn(self._rid, events, handler)
        return self

    # Remove a collection event handler function.
    # Available events are 'add' and 'remove'.
    # @param {?string} [events] One or more space-separated events. Null means any event.
    # @param {eventCallback} [handler] Handler function to remove.
    # @returns {self}
    def off(self,events, handler):
        self._api.resourceOff(self._rid, events, handler)
        return self

    # Get an item from the collection by id.
    # Requires that id callback is defined for the collection.
    # @param {string} id Id of the item
    # @returns {#} Item with the id. Undefined if key doesn't exist
    def get(self,id):
        self._hasId()
        return self._map[id]

    # Retrieves the order index of an item.
    # @param {#} item Item to find
    # @returns {number} Order index of the first matching item. -1 if the item doesn't exist.
    def indexOf(self, item):
        return self._list.index(item)

    # Gets an item from the collection by index position
    # @param {number} idx  Index of the item
    # @returns {#} Item at the given index. Undefined if the index is out of bounds.
    def atIndex(self,idx):
        return self._list[idx]

    # Calls a method on the collection.
    # @param {string} method Method name
    # @param {#} params Method parameters
    # @returns {Promise.<object>} Promise of the call result.
    def call(self, method, params):
        return self._api.call(self._rid, method, params)

    # Returns a shallow clone of the internal array.
    # @returns {Array.<#>} Clone of internal array
    def toArray(self):
        return self._list.slice()

    # Initializes the collection with a data array.
    # Should only be called by the ResClient instance.
    # @param {Array.<#>} data ResCollection data array
    # @private
    def _init(self,data):

        self._list = data if data else []

        if self._idCallback:
            self._map = {}
            for e in self._list:
                id = str(self._idCallback(e))
                if self._map.get(id) != None:
                    raise Exception("Duplicate id - " + id)
                self._map[id] = e

    # Add an item to the collection.
    # Should only be called by the ResClient instance.
    # @param {#} item Item
    # @param {idx} [idx] Index value of where to insert the item.
    # @private
    def _add(self,item, idx):
        self._list.insert(idx, item)

        if self._idCallback:
            id = str(self._idCallback(item))
            if self._map.get(id):
                raise Exception("Duplicate id - " + id)
            self._map[id] = item

    # Remove an item from the collection.
    # Should only be called by the ResClient instance.
    # @param {number} idx Index of the item to remove
    # @returns {#} Removed item or undefined if no item was removed
    # @private
    def _remove(self, idx):
        item = self._list[idx]
        del self._list[idx]

        if self._idCallback:
            del self._map[self._idCallback(item)]
        return item

    def _hasId(self):
        if not self._idCallback:
            raise Exception("No id callback defined")

    def toJSON(self):
        def _f(e):
            if hasattr(e, 'toJSON'):
                return e.toJSON()
            return e
        _list = list(map(_f, self._list))
        return json.dumps(_list)
