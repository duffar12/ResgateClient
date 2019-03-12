 # ResError represents a RES API error.
class ResError(Exception):

    def __init__(self, rid, method, params=None):
        self.rid = rid
        self._code = None
        if (method):
            self.method = method
            self.params = params

    def _init(self, err):
        self._code = err['code'] if err.get('code') else 'system.unknownError'
        self._message = err['message'] if err.get('message') else 'Unknown error'
        self._data = err['data'] if err.get('data') else None
        return self

    # Error code
    # @type {string}
    @property
    def code(self):
        return self._code


    # Error message
    # @type {string}
    @property
    def message(self):
        return self._message


    # Error data object
    # @type {#}
    @property
    def data(self):
        return self._data


    # Error resource ID
    # @returns {string} Resource ID
    def getResourceId(self):
        return self.rid
