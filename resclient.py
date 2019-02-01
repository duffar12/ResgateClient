


def get_subscribe_msg(channel, id=1):
    '''Returns a resgate protocol subscription message for channel'''
    return {"id":id,"method":"subscribe.{}".format(channel)}

def get_unsubscribe_msg(channel, id=1):
    '''Returns a resgate protocol unsubscribe message for channel'''
    return {"id":id,"method":"unsubscribe.{}".format(channel)}

def __handle_subscription(message):
    result = []
    if 'models' in message:
        for k, v in message['models'].items():
            result.append([k, 'subscribed', v])
    if 'collections' in message:
        for k, v in message['collections'].items():
            result.append([k, 'subscribed', v])
    if 'errors' in message:
        for k, v in message['collections'].items():
            result.append([k, 'subscribe failed', v])
    return result

def parse_message(message):
    ''' Parses messages from resgate websocket and converts them to a more readable format

       subscription confirmation messages may contain multiple subscriptions and will be of the format:
       [[channel, 'subscribed', model-schema], [channel, 'subscribed', model-schema]]
       For example
       [['news.today', 'subscribed', {'message': 'Hello world'}] ,['news.tomorrow', 'subscribed', {'message': 'Hello world'}]]

       Event messages will be of the format:
       [channel, event, {'values': model}]
       E.g.
       ['news.today', 'change', {'values': {'message': 'news today'}}]
    '''
    if 'result' in message:
        return __handle_subscription(message['result'])
    elif 'error' in message:
        return message
    elif 'event' in message:
        channel = '.'.join(message['event'].split('.')[:-1])
        event = message['event'].split('.')[-1]
        payload = message['data']
        return [channel, event, payload]


