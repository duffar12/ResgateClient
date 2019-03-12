#import { obj } from 'modapp-utils'
import json

 # ResModel represents a model provided over the RES API.
 # @implements {module:modapp~Model}
class ResModel(object):

    # Creates a ResModel instance
    # @param {ResClient} api ResClient instance
    # @param {string} rid Resource id.
    # @param {object} [opt] Optional parameters.
    # @param {object} [opt.definition] Object definition. If not provided, any value will be allowed.
    def __init__(self, api, rid, opt=None):
        self.data = opt
        self._rid = rid
        self._api = api

    # Model resource ID
    # @returns {string} Resource ID
    def getResourceId(self):
        return self._rid

    # Attach a model event handler function for one or more events.
    # If no event or handler is provided, the model will still be considered listened to,
    # until a matching off call without arguments is made.
    # Available event is 'change'.
    # @param {?string} [events] One or more space-separated events. Null means any event.
    # @param {eventCallback} [handler] Handler function to execute when the event is emitted.
    # @returns {self}
    def on(self, events, handler):
        print('adding event handler ', events)
        self._api.resourceOn(self._rid, events, handler)
        return self

    # Remove a model event handler function.
    # Available event is 'change'.
    # @param {?string} events One or more space-separated events. Null means any event.
    # @param {eventCallback} [handler] Handler function to remove.
    # @returns {self}
    def off(self, events, handler):
        self._api.resourceOff(self._rid, events, handler)
        return self

    # Calls the set method to update model properties.
    # @param {object} props Properties. Set value to undefined to delete a property.
    # @returns {Promise.<object>} Promise of the call being completed.
    def set(self, props):
        return self._api.setModel(self._rid, props)

    # Calls a method on the model.
    # @param {string} method Method name
    # @param {*} params Method parameters
    # @returns {Promise.<object>} Promise of the call result.
    def call(self, method, params):
        return self._api.call(self._rid, method, params)

    # Initializes the model with a data object.
    # Should only be called by the ResClient instance.
    # @param {object} data Data object
    # @private
    def _init(self, data):
        self._update(data)

    # Updates the model.
    # Should only be called by the ResClient instance.
    # @param {object} props Properties to update
    # @returns {?object} Changed properties
    # @private
    def _update(self, props):
        if props is not None:
            self.data = props
            return True

    def toJSON(self):
        return json.dumps(self.data)


